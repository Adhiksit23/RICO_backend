-- Migration: 003_part_status.sql
-- Adds a lifecycle status to rico.part.
--
--   in_progress      : part created from PLC shot data (live sync or backfill)
--   part.status value: traceability status (OK / IN_PROGRESS / NG)
--
-- New rows default to in_progress so PLC inserts need not set it explicitly.
-- The traceability writer overwrites it with the record's part.status.

BEGIN;

ALTER TABLE rico.part
    ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'in_progress';

COMMIT;
