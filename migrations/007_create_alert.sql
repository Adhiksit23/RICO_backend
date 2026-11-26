BEGIN;

CREATE TABLE IF NOT EXISTS rico.alert (
    id_alert BIGSERIAL PRIMARY KEY,
    id_die TEXT,
    id_machine TEXT,
    alert_type TEXT NOT NULL,
    severity TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'OPEN',
    message TEXT NOT NULL,
    enabled BOOLEAN NOT NULL DEFAULT TRUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS alert_status_created_idx ON rico.alert (enabled, status, created_at DESC);

COMMIT;
