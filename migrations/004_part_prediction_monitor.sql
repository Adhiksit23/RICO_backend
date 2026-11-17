-- Migration: 004_part_prediction_monitor.sql
-- Adds monitor/calibration comparison results to rico.part_quality_prediction.
--
--   monitor_verdict       : PASS / FAIL (same rule as the UI monitor page:
--                           FAIL when more than 4 monitored parameters are
--                           outside their calibration tolerance)
--   params_out_of_range   : number of monitored parameters outside tolerance
--   params_compared       : monitored parameters that had both a part value
--                           and calibration bounds available
--   params_total          : size of the monitored parameter set (23)

BEGIN;

ALTER TABLE rico.part_quality_prediction
    ADD COLUMN IF NOT EXISTS monitor_verdict TEXT,
    ADD COLUMN IF NOT EXISTS params_out_of_range INTEGER,
    ADD COLUMN IF NOT EXISTS params_compared INTEGER,
    ADD COLUMN IF NOT EXISTS params_total INTEGER;

COMMIT;
