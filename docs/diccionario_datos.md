# Diccionario de datos

Variables de la **cohorte analítica** (`cohorte_analitica`): un renglón por paciente, en su primera hospitalización elegible. La misma estructura se produce desde las tablas nativas de MIMIC-IV (`sql/`) y desde OMOP CDM (`sql/omop/`); las diferencias se marcan en la columna *Origen*.

Generado por `python -m antitromboticos.diccionario` a partir de [`src/antitromboticos/diccionario.py`](../src/antitromboticos/diccionario.py). La prueba `tests/test_diccionario.py` falla si alguna columna queda sin documentar.

**% faltante:** porcentaje de pacientes con valor nulo en cada fuente (mimic: n = 74), (omop: n = 80). *n/a* = la columna no existe en esa fuente.

**Fechas:** MIMIC desplaza todas las fechas de cada paciente al futuro (años 2100+) para desidentificar; los intervalos entre fechas son reales.

## Identificadores

| Variable | Descripción | Tipo | Unidades | Valores | Origen | % faltante (mimic / omop) |
|---|---|---|---|---|---|---|
| `subject_id` | Identificador del paciente en MIMIC-IV | entero | — | — | `admissions.subject_id` | 0 % / n/a |
| `hadm_id` | Identificador de la hospitalización índice | entero | — | — | `admissions.hadm_id` | 0 % / n/a |
| `person_id` | Identificador del paciente en OMOP | entero | — | — | `person.person_id` | n/a / 0 % |
| `visit_occurrence_id` | Identificador de la hospitalización índice en OMOP | entero | — | — | `visit_occurrence.visit_occurrence_id` | n/a / 0 % |
| `subject_id_fuente` | `subject_id` de MIMIC del paciente (para validar contra la versión nativa) | entero | — | — | `person.person_source_value` | n/a / 0 % |
| `visita_fuente` | Valor de origen de la visita, `subject_id|hadm_id` | texto | — | — | `visit_occurrence.visit_source_value` | n/a / 0 % |

## Exposición

| Variable | Descripción | Tipo | Unidades | Valores | Origen | % faltante (mimic / omop) |
|---|---|---|---|---|---|---|
| `grupo` | Grupo de exposición | categórica | — | `combinacion` = anticoagulante + antiagregante con solapamiento temporal; `solo_anticoagulante` = anticoagulante sin ninguna orden de antiagregante en la hospitalización | Derivada de `prescriptions` / `drug_exposure` (ver docs/cohorte.md) | 0 % / 0 % |
| `intensidad` | Intensidad del anticoagulante activo en la fecha índice (estrato del análisis) | categórica | — | `profilactica`, `terapeutica` | Fármaco, vía y dosis (nativa) o concepto y vía (OMOP) | 0 % / 0 % |
| `anticoagulante` | Anticoagulante activo en la fecha índice | categórica | — | `HNF` (heparina no fraccionada), `enoxaparina`, `warfarina`, `DOAC` | — | 0 % / 0 % |
| `antiagregante` | Antiagregante del primer solapamiento (nulo en `solo_anticoagulante`) | categórica | — | `aspirina`, `P2Y12` (clopidogrel, prasugrel, ticagrelor) | — | 55 % / 58 % |
| `t_indice` | Fecha índice: inicio del primer solapamiento (combinación) o del primer anticoagulante (comparador) | fecha-hora | — | — | Fechas desplazadas de MIMIC (años 2100+); los intervalos son reales | 0 % / 0 % |
| `t_fin_seguimiento` | Fin del seguimiento: el alta o el día 14 desde la fecha índice, lo que ocurra primero | fecha-hora | — | — | — | 0 % / 0 % |
| `dias_seguimiento` | Duración del seguimiento | decimal | días | — | — | 0 % / 0 % |

## Demografía

| Variable | Descripción | Tipo | Unidades | Valores | Origen | % faltante (mimic / omop) |
|---|---|---|---|---|---|---|
| `sexo` | Sexo registrado | categórica | — | `F`, `M` | `patients.gender` · OMOP `person.gender_concept_id` (8532 = F, 8507 = M) | 0 % / 0 % |
| `edad` | Edad al ingreso | entero | años | 18–91 (MIMIC agrupa a los mayores de 89 en 91) | `anchor_age` + (año de ingreso − `anchor_year`) · OMOP: año de ingreso − `year_of_birth` | 0 % / 0 % |

## Hospitalización

| Variable | Descripción | Tipo | Unidades | Valores | Origen | % faltante (mimic / omop) |
|---|---|---|---|---|---|---|
| `admittime` | Ingreso hospitalario | fecha-hora | — | — | `admissions.admittime` · OMOP `visit_start_datetime` | 0 % / 0 % |
| `dischtime` | Alta hospitalaria | fecha-hora | — | — | `admissions.dischtime` · OMOP `visit_end_datetime` | 0 % / 0 % |
| `muerte_hospitalaria` | Muerte durante la hospitalización (variable de origen) | entero 0/1 (nativa) · booleana (OMOP) | — | — | `admissions.hospital_expire_flag` · OMOP `discharge_to_concept_id` = 4216643 o `death` durante la visita | 0 % / 0 % |
| `estrato` | Estrato clínico de la hospitalización | categórica | — | `cirugia_cardiaca`, `quirurgico`, `medico` | Nativa: servicio tratante (`services`: CSURG > SURG/NSURG/VSURG/TRAUM/ORTHO/TSURG/GYN…). OMOP: unidades de `visit_detail` + `care_site` (concordancia del 75 % con la nativa) | 0 % / 0 % |
| `uci_en_indice` | En UCI en la fecha índice | booleana | — | — | `icustays` · OMOP `visit_detail` en unidades de cuidados intensivos | 0 % / 0 % |

## Indicaciones

| Variable | Descripción | Tipo | Unidades | Valores | Origen | % faltante (mimic / omop) |
|---|---|---|---|---|---|---|
| `fibrilacion_auricular` | Fibrilación o flutter auricular en la hospitalización | booleana | — | CIE-9 427.31, 427.32 · CIE-10 I48 | `diagnoses_icd` · OMOP `condition_source_value` | 0 % / 0 % |
| `cardiopatia_isquemica` | Cardiopatía isquémica en la hospitalización | booleana | — | CIE-9 410–414 · CIE-10 I20–I25 | `diagnoses_icd` · OMOP `condition_source_value` | 0 % / 0 % |
| `tromboembolia_venosa` | Trombosis venosa profunda o tromboembolia pulmonar en la hospitalización | booleana | — | CIE-9 415.1, 453.4–453.9 · CIE-10 I26, I82.4, I82.5, I82.9 | `diagnoses_icd` · OMOP `condition_source_value` | 0 % / 0 % |
| `insuficiencia_cardiaca` | Insuficiencia cardiaca en la hospitalización | booleana | — | CIE-9 428 · CIE-10 I50 | `diagnoses_icd` · OMOP `condition_source_value` | 0 % / 0 % |

## Laboratorio basal

| Variable | Descripción | Tipo | Unidades | Valores | Origen | % faltante (mimic / omop) |
|---|---|---|---|---|---|---|
| `hb_basal` | Último valor de hemoglobina en las 48 h previas a la fecha índice | decimal | g/dL | — | Hb: `labevents.itemid` 51222 · OMOP `measurement_concept_id` 3000963 (LOINC 718-7) | 0 % / 0 % |
| `plaquetas_basal` | Último valor de plaquetas en las 48 h previas a la fecha índice | decimal | × 10⁹/L (K/µL) | — | Plaquetas: `labevents.itemid` 51265 · OMOP `measurement_concept_id` 3024929 (LOINC 777-3) | 0 % / 0 % |

## Desenlace: sangrado

| Variable | Descripción | Tipo | Unidades | Valores | Origen | % faltante (mimic / omop) |
|---|---|---|---|---|---|---|
| `sangrado_relevante` | **Desenlace principal.** `caida_hb_2` o `transfusion_gr` | booleana | — | — | En OMOP equivale a `caida_hb_2` (no hay transfusiones) | 0 % / 0 % |
| `caida_hb_2` | Nadir de Hb en el seguimiento ≤ basal − 2 g/dL (umbral ISTH) | booleana | — | — | Hb: `labevents.itemid` 51222 · OMOP `measurement_concept_id` 3000963 (LOINC 718-7) | 0 % / 0 % |
| `transfusion_gr` | Transfusión de concentrado eritrocitario en el seguimiento | booleana | — | Nulo en OMOP (no disponible) | `inputevents` con `d_items.label` ~ 'Packed' (solo UCI) | 0 % / 100 % |
| `hb_nadir` | Valor mínimo de Hb en el seguimiento | decimal | g/dL | — | Hb: `labevents.itemid` 51222 · OMOP `measurement_concept_id` 3000963 (LOINC 718-7) | 1 % / 1 % |
| `caida_hb_max` | Caída máxima de Hb: basal − nadir (negativo si subió) | decimal | g/dL | — | — | 1 % / 1 % |
| `n_hb` | Número de mediciones de Hb en el seguimiento (nulo si ninguna) | entero | — | — | — | 1 % / 1 % |

## Desenlace: plaquetas

| Variable | Descripción | Tipo | Unidades | Valores | Origen | % faltante (mimic / omop) |
|---|---|---|---|---|---|---|
| `plaquetas_nadir` | Valor mínimo de plaquetas en el seguimiento | decimal | × 10⁹/L | — | Plaquetas: `labevents.itemid` 51265 · OMOP `measurement_concept_id` 3024929 (LOINC 777-3) | 1 % / 1 % |
| `plaquetas_cambio_pct` | Cambio porcentual de la basal al nadir | decimal | % | — | — | 1 % / 1 % |
| `trombocitopenia_nueva` | Nadir < 100 con basal ≥ 150 × 10⁹/L | booleana | — | Nulo si la basal es < 150 (no aplica) | — | 23 % / 22 % |
| `plaquetas_caida_50` | Nadir ≤ 50 % de la basal | booleana | — | — | — | 0 % / 0 % |
| `n_plaquetas` | Número de mediciones de plaquetas en el seguimiento (nulo si ninguna) | entero | — | — | — | 1 % / 1 % |

## Desenlace: hospitalario

| Variable | Descripción | Tipo | Unidades | Valores | Origen | % faltante (mimic / omop) |
|---|---|---|---|---|---|---|
| `estancia_post_indice_dias` | Días desde la fecha índice hasta el alta | decimal | días | — | — | 0 % / 0 % |
| `uci_posterior` | Ingreso a UCI después de la fecha índice, dentro del seguimiento | booleana | — | — | — | 0 % / 0 % |
| `muerte` | Muerte hospitalaria (versión booleana de `muerte_hospitalaria`) | booleana | — | — | — | 0 % / 0 % |

## Valores faltantes: cómo se tratan

- `hb_nadir`, `plaquetas_nadir` y los `n_*` son nulos cuando no hubo mediciones en el seguimiento. En ese caso, los desenlaces booleanos de laboratorio (`caida_hb_2`, `plaquetas_caida_50`) se codifican como `false`: un evento no medido se cuenta como ausente (puede subestimar el riesgo).

- `trombocitopenia_nueva` es nula por diseño cuando la basal es < 150 × 10⁹/L.

- `transfusion_gr` es nula en OMOP porque el release no incluye `inputevents`; el análisis la omite.

- `antiagregante` es nulo en el grupo `solo_anticoagulante` por definición.
