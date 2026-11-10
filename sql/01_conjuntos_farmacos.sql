-- 01 · Conjuntos de fármacos antitrombóticos
--
-- Clasifica cada prescripción de `prescriptions` en familia, fármaco e intensidad.
-- Provisional: clasifica por nombre, vía y dosis. En OMOP se reemplazará por
-- conceptos RxNorm agrupados con concept_ancestor (clases ATC B01AB, B01AA, B01AF/AE, B01AC).
--
-- Decisiones:
--   * Heparina no fraccionada (HNF): solo 'Heparin' y 'Heparin Sodium'. Se excluyen flush, dwell,
--     cebado de CRRT, hemodiálisis e IABP (no son anticoagulación sistémica del paciente o son de circuito).
--   * HNF SC = profiláctica; HNF IV = terapéutica.
--   * Enoxaparina <= 40 mg = profiláctica; > 40 mg = terapéutica.
--   * Rivaroxabán 10 mg = profiláctico; otras dosis de DOAC y warfarina = terapéuticas.
--   * Antiagregantes: aspirina e inhibidores P2Y12 (sin intensidad).

CREATE OR REPLACE TABLE rx_antitrombotico AS
WITH rx AS (
    SELECT
        subject_id,
        hadm_id,
        starttime,
        stoptime,
        drug,
        route,
        TRY_CAST(
            regexp_extract(replace(CAST(dose_val_rx AS VARCHAR), ',', ''), '^([0-9.]+)', 1) AS DOUBLE
        ) AS dosis
    FROM prescriptions
    WHERE starttime IS NOT NULL
),
clasificado AS (
    SELECT
        *,
        CASE
            WHEN drug IN ('Heparin', 'Heparin Sodium')                    THEN 'HNF'
            WHEN drug ILIKE '%enoxaparin%'                                THEN 'enoxaparina'
            WHEN drug ILIKE '%warfarin%'                                  THEN 'warfarina'
            WHEN regexp_matches(drug, '(?i)apixaban|rivaroxaban|dabigatran') THEN 'DOAC'
            WHEN drug ILIKE '%aspirin%'                                   THEN 'aspirina'
            WHEN regexp_matches(drug, '(?i)clopidogrel|ticagrelor|prasugrel') THEN 'P2Y12'
        END AS farmaco
    FROM rx
)
SELECT
    subject_id,
    hadm_id,
    starttime,
    stoptime,
    drug,
    route,
    dosis,
    farmaco,
    CASE WHEN farmaco IN ('aspirina', 'P2Y12') THEN 'antiagregante' ELSE 'anticoagulante' END AS familia,
    CASE
        WHEN farmaco = 'HNF' AND route = 'SC'                          THEN 'profilactica'
        WHEN farmaco = 'HNF' AND route = 'IV'                          THEN 'terapeutica'
        WHEN farmaco = 'enoxaparina' AND dosis <= 40                   THEN 'profilactica'
        WHEN farmaco = 'enoxaparina' AND dosis > 40                    THEN 'terapeutica'
        WHEN farmaco = 'DOAC' AND drug ILIKE '%rivaroxaban%' AND dosis <= 10 THEN 'profilactica'
        WHEN farmaco IN ('warfarina', 'DOAC')                          THEN 'terapeutica'
    END AS intensidad
FROM clasificado
WHERE farmaco IS NOT NULL
  -- HNF por otra vía (p. ej. DIALYS) o enoxaparina sin dosis legible quedan sin intensidad: se descartan
  AND (farmaco IN ('aspirina', 'P2Y12')
       OR (farmaco = 'HNF' AND route IN ('SC', 'IV'))
       OR (farmaco = 'enoxaparina' AND dosis IS NOT NULL)
       OR farmaco IN ('warfarina', 'DOAC'));
