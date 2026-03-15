"""
Kafka Producer - Simulates transaction stream for testing
In production, this would be replaced by actual banking system integration
"""

from kafka import KafkaProducer
import json
import time
import random
from datetime import datetime, timedelta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TransactionProducer:
    """Produces simulated transactions for testing"""
    
    def __init__(self, bootstrap_servers='localhost:9092', topic='transactions'):
        self.producer = KafkaProducer(
            bootstrap_servers=bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.topic = topic
        logger.info(f"Producer initialized for topic: {topic}")
    
    def generate_transaction(self, fund_name='Money Market Fund'):
        """Generate a realistic transaction"""
        return {
            'fund_name': fund_name,
            'clientid': f'CLIENT-{random.randint(1000, 9999)}',
            'transactiondate': (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat(),
            'inflows': round(random.uniform(0, 10000), 2) if random.random() > 0.3 else 0,
            'outflows': round(random.uniform(0, 5000), 2) if random.random() > 0.5 else 0,
            'balance': round(random.uniform(1000, 50000), 2),
            'dailyincome': round(random.uniform(0, 500), 2),
            'reversals': 1 if random.random() > 0.95 else 0,
            'incomedistribution': round(random.uniform(0, 1000), 2) if random.random() > 0.9 else 0,
            'cumulativeincome': round(random.uniform(0, 10000), 2),
            'timestamp': time.time()
        }
    
    def produce_stream(self, rate=10, duration=None):
        """
        Produce continuous transaction stream
        
        Args:
            rate: Transactions per second
            duration: Duration in seconds (None for infinite)
        """
        logger.info(f"Starting transaction stream at {rate} txn/sec")
        
        start_time = time.time()
        count = 0
        
        try:
            while True:
                # Check duration
                if duration and (time.time() - start_time) > duration:
                    break
                
                # Generate and send transaction
                transaction = self.generate_transaction()
                self.producer.send(self.topic, transaction)
                count += 1
                
                if count % 100 == 0:
                    logger.info(f"Produced {count} transactions")
                
                # Control rate
                time.sleep(1.0 / rate)
                
        except KeyboardInterrupt:
            logger.info("Stream stopped by user")
        finally:
            self.producer.flush()
            self.producer.close()
            logger.info(f"Total transactions produced: {count}")
    
    def produce_batch(self, num_transactions=1000):
        """Produce a batch of transactions"""
        logger.info(f"Producing batch of {num_transactions} transactions")
        
        for i in range(num_transactions):
            transaction = self.generate_transaction()
            self.producer.send(self.topic, transaction)
            
            if (i + 1) % 100 == 0:
                logger.info(f"Progress: {i + 1}/{num_transactions}")
        
        self.producer.flush()
        logger.info(f"Batch complete: {num_transactions} transactions produced")


if __name__ == '__main__':
    import sys
    
    # Get configuration
    bootstrap_servers = sys.argv[1] if len(sys.argv) > 1 else 'localhost:9092'
    topic = sys.argv[2] if len(sys.argv) > 2 else 'transactions'
    
    # Create producer
    producer = TransactionProducer(bootstrap_servers, topic)
    
    # Produce test batch
    producer.produce_batch(1000)
    
    # Or stream continuously
    # producer.produce_stream(rate=10)  # 10 txn/sec

