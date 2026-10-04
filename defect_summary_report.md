# Defect & Part Summary — All Dies (as of 2026-09-23 22:04)

- Dies: **S14, S16, S17, S18**
- Total parts recorded: **37296**
- Total defects recorded: **2551**
- Distinct defect types (raw): **440** (of which **402** are PLC-communication-failure variants, grouped as `PLC_COMMUNICATION_FAILED_*` below)

## 1) Recorded defects per die

### 1a) Totals per die

| Die | Machine | Parts | Defects | Distinct defect types |
|---|------|--:|--:|--:|
| S14 | UBE 850T-2 | 14364 | 1476 | 289 |
| S16 | UBE 850T-2 | 512 | 18 | 4 |
| S17 | UBE 850T-2 | 9014 | 844 | 148 |
| S18 | UBE 850T-2 | 13406 | 213 | 40 |

### 1b) Defect counts by type per die

_`PLC_COMMUNICATION_FAILED_*` groups all PLC-communication-failure variants; the full variant list is in `defect_types_by_die.csv`._

| Defect type | S14 | S16 | S17 | S18 | Total |
|---|---|---|---|---||---|
| PLC_COMMUNICATION_FAILED_* | 665 | 0 | 276 | 53 | 994 |
| Non-Filling | 239 | 1 | 166 | 26 | 432 |
| Bend | 101 | 0 | 97 | 6 | 204 |
| Porosity | 99 | 0 | 33 | 16 | 148 |
| Black Mark | 69 | 0 | 27 | 23 | 119 |
| Face Blow Hole | 48 | 0 | 39 | 14 | 101 |
| Blow Hole M8 | 70 | 0 | 8 | 10 | 88 |
| Dent | 38 | 0 | 28 | 15 | 81 |
| Chip-off | 23 | 1 | 31 | 16 | 71 |
| Shrinkage | 29 | 0 | 22 | 15 | 66 |
| Chipoff on M8.0 | 15 | 0 | 21 | 11 | 47 |
| M14 Face Blow Hole | 28 | 0 | 12 | 3 | 43 |
| Crack | 17 | 0 | 20 | 1 | 38 |
| Laser Marking NG | 5 | 0 | 11 | 0 | 16 |
| RECOVERY_PENDING_AFTER_BACKEND_RESTART | 0 | 15 | 0 | 0 | 15 |
| Flow Mark | 0 | 1 | 11 | 0 | 12 |
| Pre Filling | 1 | 0 | 10 | 0 | 11 |
| Face Unclean | 0 | 0 | 10 | 0 | 10 |
| Non-filling | 8 | 0 | 1 | 0 | 9 |
| Dia Under Size | 4 | 0 | 1 | 0 | 5 |
| Cold Shut | 3 | 0 | 1 | 1 | 5 |
| Air Bubble | 0 | 0 | 4 | 0 | 4 |
| Body Leak | 2 | 0 | 0 | 1 | 3 |
| Scratch Mark | 1 | 0 | 2 | 0 | 3 |
| M14 Face Porosity | 1 | 0 | 2 | 0 | 3 |
| Blister | 1 | 0 | 1 | 0 | 2 |
| LT Oil Gallery-1 NG | 2 | 0 | 0 | 0 | 2 |
| Extra Metal | 2 | 0 | 0 | 0 | 2 |
| Chipoff on Dia 8.0 | 2 | 0 | 0 | 0 | 2 |
| Soldering | 0 | 0 | 2 | 0 | 2 |
| LT Oil Gallery-2 NG | 0 | 0 | 1 | 1 | 2 |
| Casting Dent on Surface | 0 | 0 | 1 | 0 | 1 |
| Casting Dent on Riv | 1 | 0 | 0 | 0 | 1 |
| Cold Shot | 0 | 0 | 1 | 0 | 1 |
| Iron Particle on face | 0 | 0 | 0 | 1 | 1 |
| Face Step | 0 | 0 | 1 | 0 | 1 |
| Face Chattering | 1 | 0 | 0 | 0 | 1 |
| Ejector Pin Depression | 0 | 0 | 1 | 0 | 1 |
| Oval/Soldering | 0 | 0 | 1 | 0 | 1 |
| M8 Taping undersize | 1 | 0 | 0 | 0 | 1 |
| Peel Off | 0 | 0 | 1 | 0 | 1 |
| Setting part | 0 | 0 | 1 | 0 | 1 |

### 1c) Breakdown per die

#### Die S14 — 1476 defects (28 grouped types [289 raw, PLC-comm variants grouped])

| Defect type | Count |
|---|---|--:|
| PLC_COMMUNICATION_FAILED_* | 665 |
| Non-Filling | 239 |
| Bend | 101 |
| Porosity | 99 |
| Blow Hole M8 | 70 |
| Black Mark | 69 |
| Face Blow Hole | 48 |
| Dent | 38 |
| Shrinkage | 29 |
| M14 Face Blow Hole | 28 |
| Chip-off | 23 |
| Crack | 17 |
| Chipoff on M8.0 | 15 |
| Non-filling | 8 |
| Laser Marking NG | 5 |
| Dia Under Size | 4 |
| Cold Shut | 3 |
| LT Oil Gallery-1 NG | 2 |
| Body Leak | 2 |
| Chipoff on Dia 8.0 | 2 |
| Extra Metal | 2 |
| Blister | 1 |
| Casting Dent on Riv | 1 |
| Face Chattering | 1 |
| M14 Face Porosity | 1 |
| M8 Taping undersize | 1 |
| Pre Filling | 1 |
| Scratch Mark | 1 |

#### Die S16 — 18 defects (4 grouped types [4 raw, PLC-comm variants grouped])

| Defect type | Count |
|---|---|--:|
| RECOVERY_PENDING_AFTER_BACKEND_RESTART | 15 |
| Chip-off | 1 |
| Flow Mark | 1 |
| Non-Filling | 1 |

#### Die S17 — 844 defects (33 grouped types [148 raw, PLC-comm variants grouped])

| Defect type | Count |
|---|---|--:|
| PLC_COMMUNICATION_FAILED_* | 276 |
| Non-Filling | 166 |
| Bend | 97 |
| Face Blow Hole | 39 |
| Porosity | 33 |
| Chip-off | 31 |
| Dent | 28 |
| Black Mark | 27 |
| Shrinkage | 22 |
| Chipoff on M8.0 | 21 |
| Crack | 20 |
| M14 Face Blow Hole | 12 |
| Laser Marking NG | 11 |
| Flow Mark | 11 |
| Pre Filling | 10 |
| Face Unclean | 10 |
| Blow Hole M8 | 8 |
| Air Bubble | 4 |
| Soldering | 2 |
| M14 Face Porosity | 2 |
| Scratch Mark | 2 |
| Casting Dent on Surface | 1 |
| Blister | 1 |
| Cold Shot | 1 |
| Dia Under Size | 1 |
| Face Step | 1 |
| Ejector Pin Depression | 1 |
| Cold Shut | 1 |
| LT Oil Gallery-2 NG | 1 |
| Oval/Soldering | 1 |
| Non-filling | 1 |
| Peel Off | 1 |
| Setting part | 1 |

#### Die S18 — 213 defects (17 grouped types [40 raw, PLC-comm variants grouped])

| Defect type | Count |
|---|---|--:|
| PLC_COMMUNICATION_FAILED_* | 53 |
| Non-Filling | 26 |
| Black Mark | 23 |
| Porosity | 16 |
| Chip-off | 16 |
| Dent | 15 |
| Shrinkage | 15 |
| Face Blow Hole | 14 |
| Chipoff on M8.0 | 11 |
| Blow Hole M8 | 10 |
| Bend | 6 |
| M14 Face Blow Hole | 3 |
| Body Leak | 1 |
| Crack | 1 |
| Cold Shut | 1 |
| LT Oil Gallery-2 NG | 1 |
| Iron Particle on face | 1 |

## 2) Parts per die — first & last made / recorded

| Die | Parts | First made | Last made | First recorded | Last recorded |
|---|--:|---|---|---|---|
| S14 | 14364 | 2026-07-28 11:53:57+00:00 | 2026-08-27 08:27:27+00:00 | 2026-09-09 13:55:05.393396+00:00 | 2026-09-22 22:55:06.683163+00:00 |
| S16 | 512 | 2026-06-27 00:19:12+00:00 | 2026-07-02 15:51:40+00:00 | 2026-09-16 05:38:11.593250+00:00 | 2026-09-20 23:09:21.843644+00:00 |
| S17 | 9014 | 2026-07-02 16:38:35+00:00 | 2026-07-30 10:11:06+00:00 | 2026-09-09 21:16:49.228834+00:00 | 2026-09-22 06:56:37.545306+00:00 |
| S18 | 13406 | 2026-08-27 14:36:08+00:00 | 2026-09-23 18:29:41+00:00 | 2026-09-08 10:13:15.853030+00:00 | 2026-09-23 15:13:00.646113+00:00 |

---
_Generated by `defect_summary_report.py` from `rico.die` / `rico.part` / `rico.part_quality`._
