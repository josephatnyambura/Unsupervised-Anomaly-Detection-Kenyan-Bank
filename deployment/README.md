# Anomaly Detection System - Deployment Guide
## Real-Time Transaction Monitoring for Kenyan Banking

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/docker-ready-brightgreen.svg)](https://www.docker.com/)
[![Kubernetes](https://img.shields.io/badge/kubernetes-ready-brightgreen.svg)](https://kubernetes.io/)

---

## Table of Contents
1. [Overview](#overview)
2. [Architecture](#architecture)
3. [System Requirements](#system-requirements)
4. [Quick Start](#quick-start)
5. [**Step-by-step testing (API + Streamlit)**](TESTING_STEP_BY_STEP.md) — command-line tests and run order
6. [Production Deployment](#production-deployment)
7. [Configuration](#configuration)
8. [Monitoring & Alerting](#monitoring--alerting)
9. [Compliance & Security](#compliance--security)
10. [Maintenance](#maintenance)
11. [Troubleshooting](#troubleshooting)

---

## Overview

This system provides real-time anomaly detection for banking transactions in Kenya, designed to meet regulatory requirements and handle 50,000+ transactions per day with < 100ms latency.

### Key Features
- ✅ **Real-time Processing**: < 100ms latency per transaction
- ✅ **Scalable Architecture**: Handles 50,000+ transactions/day
- ✅ **Multiple ML Models**: AutoEncoders, Isolation Forest, One-Class SVM, LOF
- ✅ **Risk Classification**: Low, Medium, High risk tiers
- ✅ **Automated Retraining**: Monthly model updates
- ✅ **Compliance Ready**: Kenyan banking regulations, audit trails
- ✅ **Production Monitoring**: Grafana dashboards, Prometheus metrics
- ✅ **Model Reproducibility**: Versioned models with metadata

### Performance Targets
| Metric | Target | Implementation |
|--------|--------|----------------|
| Latency | < 100ms | Model caching, batch inference |
| Throughput | 50,000 txn/day | Horizontal scaling with K8s HPA |
| Availability | 99.9% | Multi-replica deployment |
| Model Refresh | Monthly | Automated retraining pipeline |

---

## Architecture

```
┌─────────────────┐         ┌──────────────┐         ┌──────────────────┐
│ Transaction     │─────────>│ Apache Kafka │─────────>│ Kafka Consumer   │
│ Source (Bank)   │         └──────────────┘         └──────────────────┘
└─────────────────┘                                            │
                                                                v
                                                    ┌──────────────────────┐
                                                    │ FastAPI Microservice │
                                                    │ (Anomaly Detection)  │
                                                    └──────────────────────┘
                                                       │           │
                          ┌────────────────────────────┴───────────┴────────────────┐
                          v                            v                             v
                  ┌───────────────┐          ┌──────────────┐            ┌────────────────┐
                  │ PostgreSQL    │          │ Prometheus   │            │ Alert System   │
                  │ (Logging)     │          │ (Metrics)    │            │ (High Risk)    │
                  └───────────────┘          └──────────────┘            └────────────────┘
                                                      │
                                                      v
                                              ┌──────────────┐
                                              │ Grafana      │
                                              │ (Dashboard)  │
                                              └──────────────┘
```

### Components
- **Apache Kafka**: Transaction stream ingestion
- **FastAPI** (see also **`fastapi_app/`** in project root for standalone API with **Pydantic** validation): Real-time anomaly detection service
- **Kubernetes**: Container orchestration and auto-scaling
- **PostgreSQL**: Transaction logging and audit trails
- **Prometheus + Grafana**: Monitoring and visualization
- **Monthly Retraining**: Automated model updates

---

## System Requirements

### Minimum Requirements
- **CPU**: 4 cores
- **RAM**: 8 GB
- **Storage**: 50 GB SSD
- **OS**: Linux (Ubuntu 20.04+), macOS, Windows 10+

### Recommended for Production
- **CPU**: 8+ cores
- **RAM**: 16+ GB
- **Storage**: 100+ GB SSD
- **Kubernetes Cluster**: 3+ nodes

### Software Dependencies
- Docker 20.10+
- Docker Compose 2.0+ (for local dev)
- Kubernetes 1.25+ (for production)
- Python 3.10+

---

## Quick Start

### 1. Local Development Setup

```bash
# Clone repository
git clone <repository-url>
cd deployment

# Start all services
docker-compose up -d

# Check service health
docker-compose ps

# View logs
docker-compose logs -f anomaly-detector
```

### 2. Initialize Database

```bash
# Run database initialization
docker-compose exec postgresql psql -U postgres -d anomaly_detection -f /docker-entrypoint-initdb.d/schema.sql

# Or run init script
python database/init_db.py
```

### 3. Test API

```bash
# Health check
curl http://localhost:5000/health

# Test prediction (use feature names from GET /models for the chosen fund)
curl -X POST http://localhost:5000/predict \
  -H "Content-Type: application/json" \
  -d '{
    "fund_name": "Money Market Fund",
    "transactions": [{
      "clientid": "TEST001",
      "transactiondate": "2024-01-01",
      "inflows": 1000.0,
      "outflows": 0.0,
      "balance": 5000.0,
      "dailyincome": 50.0,
      "cumulativeincome": 500.0
    }]
  }'
# Response includes per prediction: anomaly_score, risk_tier, features_used, explanation
```

### 4. Run the Streamlit demo UI (optional)

The Streamlit app is the **production demo UI** for the API: it uses **only the best model and top features** per fund and includes an **Explainability (SHAP/LIME)** tab. It fetches the model name and **feature list** from **GET /models**, then lets you submit single or batch transactions. Each prediction shows **risk tier**, **anomaly score**, **features used**, and an **explanation**. The **Explainability (SHAP/LIME)** tab shows LIME-style feature contributions from the last prediction and can load SHAP/fusion/risk plots from the notebook output path (`ml/plots/explainability`).

**Prerequisites:** Python 3.8+ with the API already running (e.g. `docker-compose up -d`).

```bash
# From the deployment folder
cd deployment/streamlit_app
pip install -r requirements.txt
streamlit run app.py
```

Or from the **deployment** folder:

```bash
pip install -r streamlit_app/requirements.txt
streamlit run streamlit_app/app.py
```

Then open **http://localhost:8501** in your browser.

**In the app:** Set the API URL (default `http://localhost:5000`) and click **Check connection** to see the loaded model name and feature list per fund. Use the tabs to score a single transaction (with **features used** and **explanation**), compare preset scenarios (Normal / High value / Zero activity), run a batch from JSON, or view **Explainability (SHAP/LIME)** (LIME-style feature chart and SHAP plots from notebook output). The **How it works** tab describes the flow from UI → FastAPI → best model and top features.

### 5. Access Dashboards

- **Streamlit (demo UI)**: http://localhost:8501 (after running `streamlit run streamlit_app/app.py`)
- **API / Swagger**: http://localhost:5000/docs
- **Grafana**: http://localhost:3000 (admin/admin)
- **Prometheus**: http://localhost:9090

---

## Production Deployment

### Prerequisites
1. Kubernetes cluster (EKS, GKE, or on-premise)
2. `kubectl` configured
3. Docker registry access
4. Trained models in `models/` directory

### Step 1: Build and Push Images

```bash
# Build Docker image
cd deployment/app
docker build -t your-registry/anomaly-detector:latest .

# Push to registry
docker push your-registry/anomaly-detector:latest
```

### Step 2: Create Kubernetes Namespace

```bash
kubectl create namespace banking-services
```

### Step 3: Deploy Secrets and ConfigMaps

```bash
# Update secrets (use proper values in production!)
kubectl apply -f kubernetes/secrets.yaml
kubectl apply -f kubernetes/configmap.yaml
```

### Step 4: Deploy Application

```bash
# Deploy all components
kubectl apply -f kubernetes/deployment.yaml
kubectl apply -f kubernetes/service.yaml
kubectl apply -f kubernetes/hpa.yaml

# Verify deployment
kubectl get pods -n banking-services
kubectl get svc -n banking-services
```

### Step 5: Deploy Retraining CronJob

```bash
kubectl apply -f retraining/schedule.yaml
```

### Step 6: Verify Deployment

```bash
# Check pod status
kubectl get pods -n banking-services

# Check logs
kubectl logs -n banking-services -l app=anomaly-detector

# Port forward for testing
kubectl port-forward -n banking-services svc/anomaly-detector 5000:80
```

---

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `RANDOM_SEED` | Random seed for reproducibility | 42 |
| `DB_HOST` | PostgreSQL host | localhost |
| `DB_PORT` | PostgreSQL port | 5432 |
| `DB_NAME` | Database name | anomaly_detection |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka servers | localhost:9092 |
| `LATENCY_TARGET_MS` | Target latency | 100 |
| `BATCH_SIZE` | Kafka consumer batch size | 10 |

### Model Configuration

Models are loaded from `models/` directory with the following structure:
```
models/
├── model_registry.json
├── money_market_fund/
│   └── latest/
│       ├── model.joblib
│       ├── scaler.joblib
│       ├── feature_names.json
│       └── metadata.json
└── fixed_income_fund__usd_/
    └── latest/
        ├── model_architecture.json
        ├── scaler.joblib
        ├── feature_names.json
        └── metadata.json
```

---

## Monitoring & Alerting

### Grafana Dashboards

Access Grafana at `http://<grafana-url>:3000`

**Key Metrics Monitored:**
- Real-time throughput (transactions/sec)
- API latency percentiles (p50, p95, p99)
- Anomaly detection rate
- Risk tier distribution
- Model performance (AUC, precision, recall)
- Resource utilization (CPU, memory)
- Error rates
- Model drift indicators
- Kafka consumer lag

### Alert Rules

**Critical Alerts:**
- Latency > 100ms for 5 minutes
- Error rate > 5% for 5 minutes
- Model AUC drops > 5%
- High anomaly rate (> 10%)

### Accessing Logs

```bash
# Application logs
kubectl logs -n banking-services -l app=anomaly-detector --tail=100

# Database logs
kubectl logs -n banking-services postgresql-0

# Kafka logs
kubectl logs -n banking-services kafka-0
```

---

## Compliance & Security

### Kenyan Banking Regulations

This system complies with:
- ✅ **Data Protection**: Encryption at rest and in transit
- ✅ **Audit Trails**: Comprehensive logging in `audit_log` table
- ✅ **Data Retention**: 7-year retention for transactions
- ✅ **Model Explainability**: SHAP values from the best-performing model per fund; Streamlit app includes an **Explainability (SHAP/LIME)** tab for feature contributions and optional SHAP/fusion/risk plots from notebook output
- ✅ **Bias Monitoring**: Regular fairness metrics evaluation

### Security Features

1. **Encryption**
   - TLS/SSL for all network communication
   - Encrypted secrets in Kubernetes
   - Database encryption at rest

2. **Authentication & Authorization**
   - Role-based access control (RBAC)
   - Service accounts with minimal privileges
   - API key authentication

3. **Audit Logging**
   - All predictions logged to database
   - User actions tracked
   - Immutable audit trail

### Data Privacy

- PII data is handled according to GDPR-style regulations
- Data minimization principles applied
- Right to explanation for ML decisions

---

## Maintenance

### Monthly Retraining

Automated retraining runs on the 1st of each month at 2 AM:

```bash
# Check CronJob status
kubectl get cronjobs -n banking-services

# View retraining logs
kubectl logs -n banking-services -l app=model-retraining

# Manual trigger
kubectl create job --from=cronjob/model-retraining manual-retrain-$(date +%Y%m%d)
```

### Model Updates

To deploy a new model manually:

```bash
# 1. Train model using notebook
# 2. Models are saved to models/ directory
# 3. Copy models to persistent volume
kubectl cp models/ banking-services/anomaly-detector-0:/app/models/

# 4. Reload models without downtime
curl -X POST http://<api-url>/reload
```

### Database Maintenance

```bash
# Backup database
kubectl exec -n banking-services postgresql-0 -- pg_dump -U postgres anomaly_detection > backup.sql

# Restore database
kubectl exec -i -n banking-services postgresql-0 -- psql -U postgres anomaly_detection < backup.sql

# Vacuum and analyze
kubectl exec -n banking-services postgresql-0 -- psql -U postgres -d anomaly_detection -c "VACUUM ANALYZE;"
```

### Scaling

```bash
# Manual scaling
kubectl scale deployment anomaly-detector --replicas=5 -n banking-services

# Check HPA status
kubectl get hpa -n banking-services

# Update HPA limits
kubectl edit hpa anomaly-detector-hpa -n banking-services
```

---

## Troubleshooting

### Common Issues

#### 1. Models Not Loading

**Symptom**: `/health` endpoint returns unhealthy

**Solution**:
```bash
# Check if models directory is mounted
kubectl exec -n banking-services anomaly-detector-0 -- ls -la /app/models/

# Check logs
kubectl logs -n banking-services anomaly-detector-0 | grep -i error

# Verify PVC
kubectl get pvc -n banking-services
```

#### 2. High Latency

**Symptom**: Predictions taking > 100ms

**Solution**:
- Check resource limits: `kubectl top pods -n banking-services`
- Scale up replicas: `kubectl scale deployment anomaly-detector --replicas=6`
- Review batch sizes in ConfigMap
- Check database connection pool

#### 3. Kafka Consumer Lag

**Symptom**: Messages piling up in Kafka

**Solution**:
```bash
# Check consumer lag
kubectl exec -n banking-services kafka-0 -- kafka-consumer-groups.sh \
  --bootstrap-server localhost:9092 \
  --describe --group anomaly-detector-group

# Scale consumers
kubectl scale deployment kafka-consumer --replicas=3
```

#### 4. Database Connection Issues

**Symptom**: Database connection errors in logs

**Solution**:
- Verify credentials in secrets
- Check PostgreSQL pod health: `kubectl get pods -n banking-services`
- Test connection: `kubectl exec -n banking-services postgresql-0 -- pg_isready`
- Review connection pool settings

### Debug Mode

Enable debug logging:

```bash
kubectl set env deployment/anomaly-detector LOG_LEVEL=DEBUG -n banking-services
```

### Performance Tuning

1. **CPU/Memory**:
   - Adjust resource limits in `deployment.yaml`
   - Monitor with `kubectl top`

2. **Batch Processing**:
   - Increase `BATCH_SIZE` for higher throughput
   - Decrease for lower latency

3. **Worker Threads**:
   - Adjust Gunicorn workers: `--workers 4 --threads 2`

---

## Support & Contributing

### Getting Help
- **Documentation**: This README and inline code comments
- **Issues**: Open an issue on the repository
- **Email**: support@your-organization.com

### Contributing
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

### License
MIT License - see LICENSE file for details

---

## Appendix

### A. Kubernetes Resource Templates

See `kubernetes/` directory for:
- `deployment.yaml` - Main application deployment
- `service.yaml` - Service definitions
- `configmap.yaml` - Configuration
- `secrets.yaml` - Sensitive data (template)
- `hpa.yaml` - Horizontal Pod Autoscaler

### B. Monitoring Queries

**Prometheus Queries:**
```promql
# Request rate
rate(http_requests_total[5m])

# Latency p95
histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))

# Error rate
rate(http_requests_total{status=~"5.."}[5m])
```

### C. Backup & Disaster Recovery

**Backup Schedule:**
- Database: Daily at 3 AM
- Models: After each retraining
- Configuration: Version controlled in Git

**Recovery Time Objective (RTO)**: < 1 hour
**Recovery Point Objective (RPO)**: < 24 hours

---

**Last Updated**: February 2026
**Version**: 2.0
**Author**: Anomaly Detection Team

