# S14 Defect-Prediction Report — False Negatives & Accuracy

- Die: **S14**  |  Defect models: latest per defect `Blow_Hole` `20260923`, `Crack` `20260923`, `Non_filling` `20260923`, `Porosity` `20260923`, `Shrinkage` `20260923`, `Chipoff` `20260923`
- Prediction threshold: **0.40** (same as training)

- Scope: all parts of die **S14**: **14364** (good: **12888**, defective: **1476**)
- Parts with operating parameters (prediction computed): **14364** (0 lack operating_parameter rows)
- Defective parts mappable to a target model: **579**
- Parts without a mappable defect (good + unsupported defect names): **13785** (good: **12888**, defective with unsupported name: **897**)

## Part-level results (all parts with a computable prediction)

- Scored parts: **13467**
- Part-level **accuracy: 6.62%** (891/13467)
- **False positives (good part flagged defective): 12501**
- **False negatives (defective part's defect not predicted): 75**

## Per-defect confusion matrix (positive = actual defect == that target)

| Defect | Positives | True Pos | False Neg | True Neg | False Pos | Accuracy | Precision | Recall |
|---|---|--:|--:|--:|--:|--:|--:|--:|
| Blow_Hole | 146 | 125 | **21** | 6793 | **7425** | 48.16% | 1.66% | 85.62% |
| Crack | 17 | 16 | **1** | 2850 | **11497** | 19.95% | 0.14% | 94.12% |
| Non_filling | 247 | 222 | **25** | 5483 | **8634** | 39.72% | 2.51% | 89.88% |
| Porosity | 100 | 86 | **14** | 7080 | **7184** | 49.89% | 1.18% | 86.00% |
| Shrinkage | 29 | 23 | **6** | 8428 | **5907** | 58.83% | 0.39% | 79.31% |
| Chipoff | 40 | 32 | **8** | 8294 | **6030** | 57.96% | 0.53% | 80.00% |

_Note: a part with an unmapped defect name counts as negative for each target (training labels the 6 target defects only)._

## False-negative parts (actual defect not predicted)

### Blow_Hole — 21 false negatives

| id_part | actual defect_type | probability assigned to actual defect |
|---|---|--:|
| 0729125623744 | Face Blow Hole | 0.1018 |
| 0730064924631 | Blow Hole M8 | 0.1870 |
| 0730183125135 | Face Blow Hole | 0.3944 |
| 0731020325168 | Face Blow Hole | 0.0930 |
| 0731124925682 | Face Blow Hole | 0.3002 |
| 0801035226368 | Blow Hole M8 | 0.1998 |
| 0803144828364 | M14 Face Blow Hole | 0.3807 |
| 0803150428377 | M14 Face Blow Hole | 0.3997 |
| 0803230628686 | Face Blow Hole | 0.1927 |
| 0804003628744 | Blow Hole M8 | 0.3719 |
| 0809042522817 | Blow Hole M8 | 0.3655 |
| 0809051422856 | Blow Hole M8 | 0.3794 |
| 0809131623019 | Face Blow Hole | 0.1850 |
| 0809140623061 | Blow Hole M8 | 0.2082 |
| 0809140723062 | Blow Hole M8 | 0.3982 |
| 0809162723173 | Face Blow Hole | 0.1016 |
| 0810235224600 | Face Blow Hole | 0.2080 |
| 0811035024793 | Blow Hole M8 | 0.3632 |
| 0821065222458 | M14 Face Blow Hole | 0.2528 |
| 0826011622577 | Blow Hole M8 | 0.0885 |
| 0826165623171 | M14 Face Blow Hole | 0.3640 |

### Crack — 1 false negative

| id_part | actual defect_type | probability assigned to actual defect |
|---|---|--:|
| 0802132627268 | Crack | 0.2998 |

### Non_filling — 25 false negatives

| id_part | actual defect_type | probability assigned to actual defect |
|---|---|--:|
| 0729134923779 | Non-Filling | 0.3018 |
| 0731080125446 | Non-Filling | 0.3435 |
| 0731225626137 | Non-Filling | 0.2179 |
| 0801020926290 | Non-Filling | 0.3237 |
| 0801074826538 | Non-Filling | 0.3383 |
| 0803130728282 | Non-filling | 0.3389 |
| 0803153828403 | Non-Filling | 0.1335 |
| 0805005129277 | Non-Filling | 0.3527 |
| 0805094329685 | Non-Filling | 0.3888 |
| 0805172020047 | Non-Filling | 0.3378 |
| 0806114820862 | Non-Filling | 0.3042 |
| 0806151320963 | Non-Filling | 0.2449 |
| 0807010121433 | Non-Filling | 0.3104 |
| 0809010922657 | Non-Filling | 0.3533 |
| 0809011722664 | Non-Filling | 0.3948 |
| 0809143123082 | Non-Filling | 0.2974 |
| 0812200026540 | Non-Filling | 0.2674 |
| 0818001129988 | Non-Filling | 0.3724 |
| 0818040920195 | Non-Filling | 0.3539 |
| 0820154221730 | Non-Filling | 0.2576 |
| 0821020522246 | Non-Filling | 0.1142 |
| 0821194320443 | Non-Filling | 0.1940 |
| 0824190521203 | Non-Filling | 0.1213 |
| 0825165022204 | Non-Filling | 0.1691 |
| 0827093523829 | Non-Filling | 0.3804 |

### Porosity — 14 false negatives

| id_part | actual defect_type | probability assigned to actual defect |
|---|---|--:|
| 0801000926190 | Porosity | 0.3510 |
| 0802172227467 | Porosity | 0.2344 |
| 0803131328287 | Porosity | 0.3744 |
| 0803144428360 | Porosity | 0.2696 |
| 0805084829643 | M14 Face Porosity | 0.1908 |
| 0809124822996 | Porosity | 0.3696 |
| 0813015426748 | Porosity | 0.1192 |
| 0814053127427 | Porosity | 0.2043 |
| 0815011828314 | Porosity | 0.1350 |
| 0817133129517 | Porosity | 0.1057 |
| 0817160229645 | Porosity | 0.3993 |
| 0825140122064 | Porosity | 0.3875 |
| 0826061622823 | Porosity | 0.2671 |
| 0826235423480 | Porosity | 0.1103 |

### Shrinkage — 6 false negatives

| id_part | actual defect_type | probability assigned to actual defect |
|---|---|--:|
| 0728235723232 | Shrinkage | 0.2560 |
| 0806220121290 | Shrinkage | 0.2188 |
| 0812191726504 | Shrinkage | 0.2459 |
| 0813020826760 | Shrinkage | 0.3953 |
| 0814210228095 | Shrinkage | 0.3990 |
| 0817045129119 | Shrinkage | 0.2529 |

### Chipoff — 8 false negatives

| id_part | actual defect_type | probability assigned to actual defect |
|---|---|--:|
| 0728233923216 | Chip-off | 0.0711 |
| 0731160525816 | Chipoff on M8.0 | 0.1198 |
| 0806202821218 | Chip-off | 0.2509 |
| 0809214923419 | Chip-off | 0.1684 |
| 0810235624603 | Chip-off | 0.0983 |
| 0813070626777 | Chipoff on M8.0 | 0.0681 |
| 0826091522942 | Chip-off | 0.2526 |
| 0826102123000 | Chip-off | 0.3569 |

## False-positive parts (good part, but flagged defective)

12501 good parts were flagged (sample of 50 shown; full list in the CSV).

| id_part | flagged defect | probability |
|---|---|--:|
| 0728172322907 | Crack | 0.5238 |
| 0728172522908 | Crack | 0.7639 |
| 0728172722910 | Blow_Hole | 0.4014 |
| 0728172822911 | Blow_Hole | 0.4250 |
| 0728172922912 | Non_filling | 0.6836 |
| 0728173022913 | Non_filling | 0.5866 |
| 0728173122914 | Crack | 0.7614 |
| 0728173322916 | Non_filling | 0.7354 |
| 0728173522918 | Crack | 0.8238 |
| 0728173722919 | Blow_Hole | 0.4943 |
| 0728173822920 | Non_filling | 0.6743 |
| 0728173922921 | Blow_Hole | 0.5185 |
| 0728174322925 | Crack | 0.8324 |
| 0728175222930 | Porosity | 0.8247 |
| 0728175322931 | Crack | 0.7601 |
| 0728175622933 | Blow_Hole | 0.4025 |
| 0728175722934 | Non_filling | 0.4638 |
| 0728175822935 | Non_filling | 0.4688 |
| 0728175922936 | Crack | 0.5293 |
| 0728180122938 | Crack | 0.7642 |
| 0728180222939 | Crack | 0.7439 |
| 0728180422941 | Crack | 0.5974 |
| 0728180522942 | Crack | 0.7590 |
| 0728180622943 | Crack | 0.7445 |
| 0728180822944 | Non_filling | 0.5752 |
| 0728181022946 | Crack | 0.4294 |
| 0728181322949 | Non_filling | 0.5908 |
| 0728181522951 | Crack | 0.7437 |
| 0728181622952 | Crack | 0.4252 |
| 0728181722953 | Crack | 0.8395 |
| 0728182022955 | Crack | 0.7215 |
| 0728182122956 | Crack | 0.8261 |
| 0728182222957 | Non_filling | 0.4545 |
| 0728182322958 | Crack | 0.5956 |
| 0728182422959 | Crack | 0.7653 |
| 0728182722962 | Non_filling | 0.4154 |
| 0728182822963 | Non_filling | 0.4765 |
| 0728183022965 | Blow_Hole | 0.5589 |
| 0728183122966 | Blow_Hole | 0.6613 |
| 0728183322967 | Crack | 0.8155 |
| 0728183422968 | Crack | 0.8230 |
| 0728183522969 | Crack | 0.8252 |
| 0728183622970 | Crack | 0.8126 |
| 0728183722971 | Crack | 0.6135 |
| 0728183922973 | Crack | 0.4248 |
| 0728184022974 | Crack | 0.8370 |
| 0728184122975 | Non_filling | 0.5855 |
| 0728184222976 | Crack | 0.8375 |
| 0728184322977 | Crack | 0.8310 |
| 0728184522978 | Crack | 0.7612 |

---
_Generated by `verification_report.py` using the latest trained S14 models._
