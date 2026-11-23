-- Migration: 005_part_operating_parameters_wide.sql
-- Description:
--   1. Adds covering index on rico.operating_parameter for ultra-fast index-only parameter retrieval.
--   2. Creates standard view rico.vw_part_operating_parameters_wide (live pivot of all parameters).
--      Handles canonical snake_case, legacy display names, and raw IoT telemetry aliases seamlessly.
--   3. Creates materialized view rico.mv_part_operating_parameters_wide with unique index on id_part
--      for instant O(1) reads during bulk reporting, ML training, and analytics.
--   4. Creates a refresh helper function rico.refresh_part_parameters_wide().
--
-- This migration is additive and safe to run multiple times (idempotent).

BEGIN;

-- 1. Covering Index on operating_parameter (Index-Only Scan acceleration)
CREATE INDEX IF NOT EXISTS idx_op_param_covering
    ON rico.operating_parameter (id_part, parameter_name)
    INCLUDE (value);

-- Secondary lookup index by parameter name & die
CREATE INDEX IF NOT EXISTS idx_op_param_name_die
    ON rico.operating_parameter (id_die, parameter_name);

-- 2. Live Wide View: Pivots long operating_parameter rows into columns per part
CREATE OR REPLACE VIEW rico.vw_part_operating_parameters_wide AS
SELECT
    p.id_part,
    p.shot_number,
    p.id_die,
    p.id_machine,
    p.production_date,
    p.manufactored_on,
    p.customer_qr,
    p.status AS part_status,

    -- Core 23 Process Parameters (canonical + raw IoT telemetry aliases)
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('cycle_time', 'cycletime_value_sec', 'total_cycle_time') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'cycle_time') AS cycle_time,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('die_close_core_in_time', 'DIE-CLOSE CORE IN TIME', 'DIE_CLOSE_CORE_IN_step_value_sec') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'die_close_core_in_time') AS die_close_core_in_time,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('pouring_time', 'POURING_step_value_sec', 'poring_step_time') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'pouring_time') AS pouring_time,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('shot_fwd_time', 'SHOT_FWD_step_value_sec', 'shot_fwd_step_time') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'shot_fwd_time') AS shot_fwd_time,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('curing_time', 'COOLING_step_value_sec', 'cooling_step') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'curing_time') AS curing_time,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('die_open_core_out_time', 'DIE_OPEN_CORE_OUT_step_value_sec') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'die_open_core_out_time') AS die_open_core_out_time,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('ejector_time', 'EJECTOR_step_value_sec', 'ejecter_step_time') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'ejector_time') AS ejector_time,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('extract_time', 'EXTRACTOR_step_value_sec', 'extractor_step_time') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'extract_time') AS extract_time,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('spray_time', 'SPRAY_step_value_sec') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'spray_time') AS spray_time,

    MAX(op.value) FILTER (WHERE op.parameter_name IN ('v1_speed', 'SPEED_1_m_sec_value', 'speed_1') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'v1_speed') AS v1_speed,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('v2_speed', 'SPEED_2_m_sec_value', 'speed_2') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'v2_speed') AS v2_speed,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('v3_speed', 'SPEED_3_m_sec_value', 'speed_3') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'v3_speed') AS v3_speed,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('v4_speed', 'SPEED_4_m_sec_value', 'speed_4') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'v4_speed') AS v4_speed,

    MAX(op.value) FILTER (WHERE op.parameter_name IN ('accel_point', 'ACC_POSITION_1_mm_value', 'acc_position_1') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'accel_point') AS accel_point,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('deaccel_point', 'DEACC_POSITION_1_mm_value', 'deacc_position') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'deaccel_point') AS deaccel_point,

    MAX(op.value) FILTER (WHERE op.parameter_name IN ('intensification_time', 'INTESIFICAITON_TIME_msec_value') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'intensification_time') AS intensification_time,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('metal_pressure', 'MATEL_PRESSURE_Mpa_value') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'metal_pressure') AS metal_pressure,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('biscuit_thickness', 'BISCUIT_THICKNESS_mm_value') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'biscuit_thickness') AS biscuit_thickness,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('clamp_force_pct', 'CLAMP_FORCE__value', 'clamp_force') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'clamp_force_pct') AS clamp_force_pct,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('clamp_tonnage', 'CLAMP_TONNAGE_MN_value') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'clamp_tonnage') AS clamp_tonnage,

    MAX(op.value) FILTER (WHERE op.parameter_name IN ('shot_acc_pressure', 'SHOT_ACC_PRESSURE_value') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'shot_acc_pressure') AS shot_acc_pressure,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('intensification_acc_pressure', 'INTESIFICAITON_ACC_PRESSUREvalue', 'intensification_pressure') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'intensification_acc_pressure') AS intensification_acc_pressure,
    MAX(op.value) FILTER (WHERE op.parameter_name IN ('furnace_metal_temp', 'METAL_TEMP_value', 'metal_temp') OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'furnace_metal_temp') AS furnace_metal_temp,

    -- Extended PLC Sensor & Thermal Parameters
    MAX(op.value) FILTER (WHERE op.parameter_name = 'vacuum_pressure' OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'vacuum_pressure') AS vacuum_pressure,
    MAX(op.value) FILTER (WHERE op.parameter_name = 'jet_cooling_pressure' OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'jet_cooling_pressure') AS jet_cooling_pressure,
    MAX(op.value) FILTER (WHERE op.parameter_name = 'cooling_water_mov' OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'cooling_water_mov') AS cooling_water_mov,
    MAX(op.value) FILTER (WHERE op.parameter_name = 'cooling_water_sta' OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'cooling_water_sta') AS cooling_water_sta,
    MAX(op.value) FILTER (WHERE op.parameter_name = 'fixed_die_temp_f1' OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'fixed_die_temp_f1') AS fixed_die_temp_f1,
    MAX(op.value) FILTER (WHERE op.parameter_name = 'fixed_die_temp_f2' OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'fixed_die_temp_f2') AS fixed_die_temp_f2,
    MAX(op.value) FILTER (WHERE op.parameter_name = 'moving_die_temp_m1' OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'moving_die_temp_m1') AS moving_die_temp_m1,
    MAX(op.value) FILTER (WHERE op.parameter_name = 'moving_die_temp_m2' OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'moving_die_temp_m2') AS moving_die_temp_m2,
    MAX(op.value) FILTER (WHERE op.parameter_name = 'slide_temp_s1' OR LOWER(REPLACE(op.parameter_name, ' ', '_')) = 'slide_temp_s1') AS slide_temp_s1

FROM rico.part p
LEFT JOIN rico.operating_parameter op ON p.id_part = op.id_part
GROUP BY
    p.id_part,
    p.shot_number,
    p.id_die,
    p.id_machine,
    p.production_date,
    p.manufactored_on,
    p.customer_qr,
    p.status;

-- 3. Materialized View: Pre-computed snapshot for instant bulk queries / ML / reporting
CREATE MATERIALIZED VIEW IF NOT EXISTS rico.mv_part_operating_parameters_wide AS
SELECT * FROM rico.vw_part_operating_parameters_wide;

-- Unique Index on id_part to enable fast O(1) lookups and REFRESH MATERIALIZED VIEW CONCURRENTLY
CREATE UNIQUE INDEX IF NOT EXISTS idx_mv_part_param_wide_pk
    ON rico.mv_part_operating_parameters_wide (id_part);

-- Filter & Sort Indexes for die, machine, shot number, and date ranges
CREATE INDEX IF NOT EXISTS idx_mv_part_param_wide_filter
    ON rico.mv_part_operating_parameters_wide (id_die, id_machine, production_date);

CREATE INDEX IF NOT EXISTS idx_mv_part_param_wide_shot
    ON rico.mv_part_operating_parameters_wide (shot_number, production_date);

-- 4. Stored Procedure to safely refresh the materialized view without locking readers
CREATE OR REPLACE FUNCTION rico.refresh_part_parameters_wide()
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
    REFRESH MATERIALIZED VIEW CONCURRENTLY rico.mv_part_operating_parameters_wide;
END;
$$;

COMMIT;
