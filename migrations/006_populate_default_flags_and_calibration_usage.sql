BEGIN;

UPDATE rico.operating_parameter
SET enabled = TRUE;

UPDATE rico.calibration_parameter AS cp
SET enabled = TRUE,
    "UOM" = COALESCE(
        (
            SELECT op."UOM"
            FROM rico.operating_parameter AS op
            WHERE op.parameter_name = cp.parameter_name
              AND op."UOM" IS NOT NULL
            ORDER BY op.created_at DESC
            LIMIT 1
        ),
        cp."UOM"
    ),
    updated_at = cp.created_at;

UPDATE rico.die_calibration
SET calibration_date = COALESCE(calibration_date, created_at),
    updated_at = COALESCE(updated_at, created_at);

UPDATE rico.die AS d
SET id_calibration_implemented = latest.id_calibration,
    updated_at = latest.calibration_timestamp
FROM (
    SELECT
        id_die,
        id_calibration,
        COALESCE(calibration_date, created_at) AS calibration_timestamp,
        ROW_NUMBER() OVER (
            PARTITION BY id_die
            ORDER BY COALESCE(calibration_date, created_at) DESC, id_calibration DESC
        ) AS rn
    FROM rico.die_calibration
) AS latest
WHERE d.id_die = latest.id_die
  AND latest.rn = 1;

UPDATE rico.part
SET enabled = TRUE;

UPDATE rico.part_quality AS q
SET created_at = COALESCE(q.created_at, q.updated_at),
    enabled = TRUE;

UPDATE rico.part_quality_prediction AS q
SET enabled = TRUE,
    manufactored_on = COALESCE(
        q.manufactored_on,
        (SELECT p.manufactored_on FROM rico.part AS p WHERE p.id_part = q.id_part)
    );

UPDATE rico.part AS p
SET id_calibration_used = latest.id_calibration
FROM (
    SELECT
        part.id_part,
        dc.id_calibration,
        ROW_NUMBER() OVER (
            PARTITION BY part.id_part
            ORDER BY COALESCE(dc.calibration_date, dc.created_at) DESC, dc.id_calibration DESC
        ) AS rn
    FROM rico.part AS part
    JOIN rico.die_calibration AS dc
      ON dc.id_die = part.id_die
     AND (
        part.manufactored_on IS NULL
        OR COALESCE(dc.calibration_date, dc.created_at) <= part.manufactored_on
     )
) AS latest
WHERE p.id_part = latest.id_part
  AND latest.rn = 1;

COMMIT;
