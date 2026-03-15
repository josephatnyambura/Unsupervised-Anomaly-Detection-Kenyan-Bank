-- PostgreSQL Schema for Anomaly Detection System
-- Kenyan Banking Compliance & Audit Requirements

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE SCHEMA IF NOT EXISTS anomaly_detection;
SET search_path TO anomaly_detection;

-- ============================================================================
-- TRANSACTIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    fund_name VARCHAR(255) NOT NULL,
    client_id VARCHAR(255) NOT NULL,
    transaction_date TIMESTAMP NOT NULL,

    inflows DECIMAL(15, 2) DEFAULT 0,
    outflows DECIMAL(15, 2) DEFAULT 0,
    balance DECIMAL(15, 2) NOT NULL,
    daily_income DECIMAL(15, 2) DEFAULT 0,
    cumulative_income DECIMAL(15, 2) DEFAULT 0,

    reversals INTEGER DEFAULT 0,
    income_distribution DECIMAL(15, 2) DEFAULT 0,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_txn_client_id ON transactions (client_id);
CREATE INDEX IF NOT EXISTS idx_txn_fund_name ON transactions (fund_name);
CREATE INDEX IF NOT EXISTS idx_txn_date ON transactions (transaction_date);
CREATE INDEX IF NOT EXISTS idx_txn_created ON transactions (created_at);

-- ============================================================================
-- ANOMALY_PREDICTIONS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS anomaly_predictions (
    prediction_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    transaction_id UUID REFERENCES transactions(transaction_id),

    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50),

    is_anomaly BOOLEAN NOT NULL,
    anomaly_score DECIMAL(10, 6) NOT NULL,
    risk_tier VARCHAR(20) NOT NULL CHECK (risk_tier IN ('Low', 'Medium', 'High')),
    fusion_score DECIMAL(10, 6),

    processing_time_ms DECIMAL(10, 2),
    prediction_confidence DECIMAL(5, 4),

    predicted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_pred_txn ON anomaly_predictions (transaction_id);
CREATE INDEX IF NOT EXISTS idx_pred_anomaly ON anomaly_predictions (is_anomaly);
CREATE INDEX IF NOT EXISTS idx_pred_risk ON anomaly_predictions (risk_tier);
CREATE INDEX IF NOT EXISTS idx_pred_date ON anomaly_predictions (predicted_at);

-- ============================================================================
-- ALERTS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS alerts (
    alert_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    prediction_id UUID REFERENCES anomaly_predictions(prediction_id),
    transaction_id UUID REFERENCES transactions(transaction_id),

    alert_type VARCHAR(50) NOT NULL,
    severity VARCHAR(20) NOT NULL CHECK (severity IN ('Low', 'Medium', 'High', 'Critical')),
    description TEXT,

    status VARCHAR(50) DEFAULT 'Open' CHECK (status IN ('Open', 'In Progress', 'Resolved', 'False Positive')),
    assigned_to VARCHAR(255),
    resolution_notes TEXT,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    resolved_at TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_alert_status ON alerts (status);
CREATE INDEX IF NOT EXISTS idx_alert_severity ON alerts (severity);
CREATE INDEX IF NOT EXISTS idx_alert_created ON alerts (created_at);

-- ============================================================================
-- MODEL_PERFORMANCE_LOGS TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS model_performance_logs (
    log_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    fund_name VARCHAR(255) NOT NULL,
    model_name VARCHAR(100) NOT NULL,
    model_version VARCHAR(50),

    auc DECIMAL(5, 4),
    precision_score DECIMAL(5, 4),
    recall DECIMAL(5, 4),
    f1_score DECIMAL(5, 4),
    avg_latency_ms DECIMAL(10, 2),
    throughput_per_sec DECIMAL(10, 2),

    total_predictions INTEGER,
    anomalies_detected INTEGER,
    false_positives INTEGER,
    false_negatives INTEGER,

    period_start TIMESTAMP NOT NULL,
    period_end TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_perf_fund ON model_performance_logs (fund_name, model_name);
CREATE INDEX IF NOT EXISTS idx_perf_period ON model_performance_logs (period_start);

-- ============================================================================
-- AUDIT_LOG TABLE
-- ============================================================================
CREATE TABLE IF NOT EXISTS audit_log (
    audit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),

    event_type VARCHAR(100) NOT NULL,
    event_description TEXT,

    user_id VARCHAR(255),
    system_component VARCHAR(100),
    ip_address INET,

    transaction_id UUID,
    prediction_id UUID,
    alert_id UUID,

    request_data JSONB,
    response_data JSONB,

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_audit_event ON audit_log (event_type);
CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log (created_at);
CREATE INDEX IF NOT EXISTS idx_audit_txn ON audit_log (transaction_id);

-- ============================================================================
-- DATA RETENTION FUNCTIONS
-- ============================================================================

CREATE OR REPLACE FUNCTION cleanup_old_transactions()
RETURNS void AS $$
BEGIN
    DELETE FROM transactions
    WHERE created_at < CURRENT_TIMESTAMP - INTERVAL '7 years';
END;
$$ LANGUAGE plpgsql;

-- ============================================================================
-- VIEWS FOR REPORTING
-- ============================================================================

CREATE OR REPLACE VIEW v_anomaly_rate AS
SELECT
    fund_name,
    DATE(predicted_at) AS date,
    COUNT(*) AS total_predictions,
    SUM(CASE WHEN is_anomaly THEN 1 ELSE 0 END) AS anomalies_count,
    ROUND(100.0 * SUM(CASE WHEN is_anomaly THEN 1 ELSE 0 END) / COUNT(*), 2) AS anomaly_rate_pct
FROM anomaly_predictions ap
JOIN transactions t ON ap.transaction_id = t.transaction_id
WHERE predicted_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
GROUP BY fund_name, DATE(predicted_at)
ORDER BY date DESC, fund_name;

CREATE OR REPLACE VIEW v_risk_distribution AS
SELECT
    fund_name,
    risk_tier,
    COUNT(*) AS count,
    ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (PARTITION BY fund_name), 2) AS percentage
FROM anomaly_predictions ap
JOIN transactions t ON ap.transaction_id = t.transaction_id
WHERE predicted_at >= CURRENT_TIMESTAMP - INTERVAL '7 days'
GROUP BY fund_name, risk_tier;

CREATE OR REPLACE VIEW v_alert_dashboard AS
SELECT
    status,
    severity,
    COUNT(*) AS count,
    AVG(EXTRACT(EPOCH FROM (COALESCE(resolved_at, CURRENT_TIMESTAMP) - created_at)) / 3600) AS avg_resolution_hours
FROM alerts
WHERE created_at >= CURRENT_TIMESTAMP - INTERVAL '30 days'
GROUP BY status, severity;

-- ============================================================================
-- COMMENTS FOR DOCUMENTATION
-- ============================================================================

COMMENT ON TABLE transactions IS 'Stores all processed financial transactions';
COMMENT ON TABLE anomaly_predictions IS 'ML model predictions and risk assessments';
COMMENT ON TABLE alerts IS 'Generated alerts for high-risk anomalies requiring review';
COMMENT ON TABLE model_performance_logs IS 'Time-series model performance metrics for monitoring';
COMMENT ON TABLE audit_log IS 'Comprehensive audit trail for regulatory compliance';
