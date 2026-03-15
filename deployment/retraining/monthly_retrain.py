"""
Monthly Model Retraining Pipeline
Automated retraining with validation and rollback capabilities
"""

import sys
import os
import pandas as pd
import numpy as np
import joblib
import json
from pathlib import Path
from datetime import datetime, timedelta
import logging
from sklearn.model_selection import train_test_split
from sklearn.metrics import roc_auc_score, precision_score, recall_score, f1_score
import psycopg2

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent / 'app'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ModelRetrainingPipeline:
    """Handles automated monthly model retraining"""
    
    def __init__(self):
        self.models_dir = Path('../../models')
        self.db_config = {
            'host': os.getenv('DB_HOST', 'localhost'),
            'port': os.getenv('DB_PORT', '5432'),
            'database': os.getenv('DB_NAME', 'anomaly_detection'),
            'user': os.getenv('DB_USER', 'postgres'),
            'password': os.getenv('DB_PASSWORD', 'postgres')
        }
        self.min_auc_improvement = 0.02  # Minimum AUC improvement to deploy
        self.random_seed = 42
    
    def extract_training_data(self, days_back=30):
        """Extract last N days of transaction data from database"""
        logger.info(f"Extracting training data from last {days_back} days...")
        
        try:
            conn = psycopg2.connect(**self.db_config)
            
            query = f"""
                SELECT 
                    t.*,
                    ap.is_anomaly as label
                FROM anomaly_detection.transactions t
                LEFT JOIN anomaly_detection.anomaly_predictions ap 
                    ON t.transaction_id = ap.transaction_id
                WHERE t.transaction_date >= NOW() - INTERVAL '{days_back} days'
                    AND ap.is_anomaly IS NOT NULL
                ORDER BY t.transaction_date
            """
            
            df = pd.read_sql(query, conn)
            conn.close()
            
            logger.info(f"✓ Extracted {len(df)} transactions")
            return df
            
        except Exception as e:
            logger.error(f"Error extracting data: {e}")
            raise
    
    def retrain_model(self, fund_name, X_train, y_train, current_model_path):
        """Retrain model with new data"""
        logger.info(f"Retraining model for {fund_name}...")
        
        # Load current model metadata
        metadata_path = current_model_path / 'latest' / 'metadata.json'
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        model_name = metadata['model_name']
        tuned_params = metadata.get('tuned_parameters', {})
        
        # Retrain based on model type
        if model_name == 'Isolation Forest':
            from sklearn.ensemble import IsolationForest
            model = IsolationForest(
                contamination=tuned_params.get('contamination', 0.05),
                random_state=self.random_seed,
                **{k: v for k, v in tuned_params.items() if k != 'contamination'}
            )
            model.fit(X_train)
            
        elif model_name == 'One-Class SVM':
            from sklearn.svm import OneClassSVM
            model = OneClassSVM(**tuned_params)
            model.fit(X_train)
            
        elif model_name == 'Local Outlier Factor':
            from sklearn.neighbors import LocalOutlierFactor
            model = LocalOutlierFactor(**tuned_params)
            model.fit(X_train)
            
        else:
            logger.warning(f"Retraining not implemented for {model_name}")
            return None
        
        logger.info(f"✓ Model retrained successfully")
        return model
    
    def validate_model(self, new_model, old_model, X_val, y_val):
        """Validate new model against old model"""
        logger.info("Validating new model...")
        
        # Get predictions from both models
        try:
            new_pred = new_model.predict(X_val)
            new_pred = np.where(new_pred == -1, 1, 0)
            
            old_pred = old_model.predict(X_val)
            old_pred = np.where(old_pred == -1, 1, 0)
            
            # Calculate metrics
            new_metrics = {
                'precision': precision_score(y_val, new_pred),
                'recall': recall_score(y_val, new_pred),
                'f1': f1_score(y_val, new_pred)
            }
            
            old_metrics = {
                'precision': precision_score(y_val, old_pred),
                'recall': recall_score(y_val, old_pred),
                'f1': f1_score(y_val, old_pred)
            }
            
            # Compare
            improvement = new_metrics['f1'] - old_metrics['f1']
            
            logger.info(f"  Old model F1: {old_metrics['f1']:.4f}")
            logger.info(f"  New model F1: {new_metrics['f1']:.4f}")
            logger.info(f"  Improvement: {improvement:+.4f}")
            
            # Decision
            should_deploy = improvement > self.min_auc_improvement
            
            return should_deploy, new_metrics, old_metrics
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False, {}, {}
    
    def deploy_model(self, new_model, fund_name, metrics):
        """Deploy new model if validation passes"""
        logger.info(f"Deploying new model for {fund_name}...")
        
        fund_dir = self.models_dir / self._sanitize_filename(fund_name)
        
        # Create new version directory
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        version_dir = fund_dir / f'v_{timestamp}'
        version_dir.mkdir(parents=True, exist_ok=True)
        
        # Save model
        model_path = version_dir / 'model.joblib'
        joblib.dump(new_model, model_path)
        
        # Save metadata
        metadata = {
            'fund_name': fund_name,
            'timestamp': timestamp,
            'created_at': datetime.now().isoformat(),
            'retrained': True,
            'performance_metrics': metrics,
            'model_path': str(model_path)
        }
        
        metadata_path = version_dir / 'metadata.json'
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        # Update latest symlink
        latest_dir = fund_dir / 'latest'
        if latest_dir.exists():
            latest_dir.unlink()
        latest_dir.symlink_to(version_dir, target_is_directory=True)
        
        logger.info(f"✓ New model deployed to {version_dir}")
        return True
    
    def run_retraining(self):
        """Execute complete retraining pipeline"""
        logger.info("\n" + "="*80)
        logger.info("STARTING MONTHLY RETRAINING PIPELINE")
        logger.info("="*80 + "\n")
        
        # Extract data
        df = self.extract_training_data(days_back=30)
        
        if len(df) < 1000:
            logger.warning("Insufficient data for retraining. Skipping.")
            return False
        
        # Process each fund
        funds = df['fund_name'].unique()
        
        for fund_name in funds:
            logger.info(f"\n--- Processing {fund_name} ---")
            
            # Filter fund data
            fund_data = df[df['fund_name'] == fund_name].copy()
            
            # Prepare features
            X = fund_data.drop(['label', 'fund_name', 'transaction_id', 'created_at', 'updated_at'], axis=1)
            y = fund_data['label']
            
            # Split
            X_train, X_val, y_train, y_val = train_test_split(
                X, y, test_size=0.3, random_state=self.random_seed
            )
            
            # Load current model
            current_model_path = self.models_dir / self._sanitize_filename(fund_name)
            if not current_model_path.exists():
                logger.warning(f"No existing model for {fund_name}. Skipping.")
                continue
            
            old_model = joblib.load(current_model_path / 'latest' / 'model.joblib')
            
            # Retrain
            new_model = self.retrain_model(fund_name, X_train, y_train, current_model_path)
            
            if new_model is None:
                continue
            
            # Validate
            should_deploy, new_metrics, old_metrics = self.validate_model(
                new_model, old_model, X_val, y_val
            )
            
            # Deploy if improvement
            if should_deploy:
                self.deploy_model(new_model, fund_name, new_metrics)
                logger.info(f"✓ {fund_name} model updated")
            else:
                logger.info(f"✗ {fund_name} model not improved, keeping current version")
        
        logger.info("\n" + "="*80)
        logger.info("RETRAINING PIPELINE COMPLETE")
        logger.info("="*80)
        
        return True
    
    @staticmethod
    def _sanitize_filename(name):
        import re
        return re.sub(r'[^a-zA-Z0-9_]', '_', str(name).lower().replace(' ', '_'))


if __name__ == '__main__':
    pipeline = ModelRetrainingPipeline()
    success = pipeline.run_retraining()
    sys.exit(0 if success else 1)

