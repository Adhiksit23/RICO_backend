-- Migration: 002_part_shot_identity.sql
-- Adds explicit shot identity to rico.part so sync/backfill can dedupe on the
-- physical shot instead of the derived id_part string.
--
-- id_part layout (legacy and current):
--   MMDDHHMM (8) + machine digit (1) + shot number.
-- The traceability/monthly path zero-pads the shot number to 4 digits; the
-- legacy shot_update path does not, so id_part lengths range 10..13.
-- substring(id_part FROM 10) still yields the shot digits at every width.
--
-- No backfill on purpose: the table is expected to be emptied and repopulated.
-- Writers fill these columns from the API fields:
--   traceability: shot.number and shot.date
--   PLC:          shot_number and production_date
--
-- This migration is additive + idempotent. The index is intentionally
-- NON-unique; add a UNIQUE index only after the table is clean.

BEGIN;

ALTER TABLE rico.part
    ADD COLUMN IF NOT EXISTS shot_number BIGINT,
    ADD COLUMN IF NOT EXISTS production_date DATE;

CREATE INDEX IF NOT EXISTS idx_part_die_shot_proddate
    ON rico.part (id_die, shot_number, production_date);

COMMIT;
