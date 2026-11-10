-- OMOP 01 · Conjuntos de conceptos
--
-- Fuente: MIMIC-IV demo data in the OMOP CDM v0.9 (CDM 5.3.1). Este release solo trae los conceptos
-- locales (>2B), no los vocabularios estándar, así que aquí no hay `concept` ni `concept_ancestor`.
-- Los conjuntos se definen como listas explícitas de concept_id estándar (RxNorm / LOINC):
--   * Los fármacos se identificaron cruzando drug_exposure.drug_source_value (NDC) con el nombre del
--     fármaco en prescriptions de MIMIC-IV Demo v2.2 (ver docs/omop.md).
--   * Cuando se carguen los vocabularios de Athena, estas listas deben reemplazarse por descendientes
--     de los ingredientes (concept_ancestor) para tener el conjunto completo.
--
-- Intensidad:
--   * Heparina 43011850: SC = profiláctica, IV = terapéutica, otra vía (p. ej. DIALYS) = se excluye.
--   * Enoxaparina: el concepto corresponde a la presentación, no a la dosis administrada.
--     40160971/40160973/40160974 (≤ 40 mg) = profiláctica; el resto = terapéutica.
--     Limitación: 40160974 incluye algunas dosis de 80 mg (dos jeringas).
--   * Rivaroxabán 10 mg (40241334) = profiláctico.
-- No incluidos a propósito: heparina flush/dwell/hemodiálisis (43011826, 43011884, 43011897) e IABP (46275378).

CREATE OR REPLACE TABLE cs_antitrombotico AS
SELECT * FROM (VALUES
    -- concept_id, farmaco,      familia,          intensidad (NULL = depende de la vía)
    (43011850, 'HNF',         'anticoagulante', NULL),
    (46275400, 'HNF',         'anticoagulante', 'terapeutica'),    -- infusión 25,000 U IV
    (40160971, 'enoxaparina', 'anticoagulante', 'profilactica'),   -- 30 mg
    (40160973, 'enoxaparina', 'anticoagulante', 'profilactica'),   -- 40 mg
    (40160974, 'enoxaparina', 'anticoagulante', 'profilactica'),   -- 40 mg (ver limitación)
    (40160990, 'enoxaparina', 'anticoagulante', 'terapeutica'),    -- 60 mg
    (40160992, 'enoxaparina', 'anticoagulante', 'terapeutica'),    -- 80 mg
    (40160993, 'enoxaparina', 'anticoagulante', 'terapeutica'),    -- 120 mg
    (40160996, 'enoxaparina', 'anticoagulante', 'terapeutica'),    -- 100 mg
    (40163511, 'warfarina',   'anticoagulante', 'terapeutica'),
    (40163525, 'warfarina',   'anticoagulante', 'terapeutica'),
    (40163535, 'warfarina',   'anticoagulante', 'terapeutica'),
    (40163555, 'warfarina',   'anticoagulante', 'terapeutica'),
    (43013031, 'DOAC',        'anticoagulante', 'terapeutica'),    -- apixabán
    (40228158, 'DOAC',        'anticoagulante', 'terapeutica'),    -- dabigatrán 150 mg
    (40244445, 'DOAC',        'anticoagulante', 'terapeutica'),    -- rivaroxabán 15 mg
    (40244449, 'DOAC',        'anticoagulante', 'terapeutica'),    -- rivaroxabán 20 mg
    (40241334, 'DOAC',        'anticoagulante', 'profilactica'),   -- rivaroxabán 10 mg
    (1112839,  'aspirina',    'antiagregante',  NULL),
    (1112892,  'aspirina',    'antiagregante',  NULL),
    (1113346,  'aspirina',    'antiagregante',  NULL),
    (19046742, 'aspirina',    'antiagregante',  NULL),
    (19073712, 'aspirina',    'antiagregante',  NULL),
    (19133435, 'aspirina',    'antiagregante',  NULL),
    (1322185,  'P2Y12',       'antiagregante',  NULL),             -- clopidogrel 75 mg
    (1322189,  'P2Y12',       'antiagregante',  NULL),             -- clopidogrel 300 mg
    (19075601, 'P2Y12',       'antiagregante',  NULL),             -- clopidogrel 75 mg
    (40163721, 'P2Y12',       'antiagregante',  NULL),             -- prasugrel
    (40241189, 'P2Y12',       'antiagregante',  NULL)              -- ticagrelor
) AS t(concept_id, farmaco, familia, intensidad);

-- Mediciones (LOINC)
CREATE OR REPLACE MACRO hb_concept()        AS 3000963;  -- Hemoglobin [Mass/volume] in Blood
CREATE OR REPLACE MACRO plaquetas_concept() AS 3024929;  -- Platelets [#/volume] in Blood

-- Exposiciones antitrombóticas con familia, fármaco e intensidad
CREATE OR REPLACE TABLE rx_antitrombotico AS
SELECT
    d.person_id,
    d.visit_occurrence_id,
    d.drug_exposure_start_datetime AS starttime,
    d.drug_exposure_end_datetime   AS stoptime,
    d.drug_concept_id,
    d.route_source_value           AS route,
    cs.farmaco,
    cs.familia,
    CASE
        WHEN cs.intensidad IS NOT NULL                          THEN cs.intensidad
        WHEN cs.farmaco = 'HNF' AND d.route_source_value = 'SC' THEN 'profilactica'
        WHEN cs.farmaco = 'HNF' AND d.route_source_value = 'IV' THEN 'terapeutica'
    END AS intensidad
FROM drug_exposure d
JOIN cs_antitrombotico cs ON cs.concept_id = d.drug_concept_id
WHERE d.drug_exposure_start_datetime IS NOT NULL
  -- heparina por una vía distinta de SC/IV (cebado de CRRT) no es anticoagulación del paciente
  AND NOT (cs.farmaco = 'HNF' AND cs.intensidad IS NULL AND coalesce(d.route_source_value, '') NOT IN ('SC', 'IV'));
