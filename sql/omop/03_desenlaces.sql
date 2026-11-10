-- OMOP 03 · Desenlaces y covariables
--
-- Misma definición que sql/03_desenlaces.sql, sobre tablas OMOP. Diferencias:
--   * Transfusión: no disponible (este release de OMOP no incorpora inputevents). La columna queda en
--     NULL y el desenlace principal se reduce a la caída de Hb >= 2 g/dL.
--   * Estrato y UCI: a partir de las unidades de visit_detail/care_site (OMOP no tiene "servicio tratante").
--   * Indicaciones: códigos CIE de condition_source_value (sin vocabularios estándar no se puede usar SNOMED).
--
-- Requiere: cohorte (02_cohorte.sql).

CREATE OR REPLACE TABLE labs_seguimiento AS
SELECT
    c.visit_occurrence_id,
    min(m.value_as_number) FILTER (WHERE m.measurement_concept_id = hb_concept())        AS hb_nadir,
    min(m.value_as_number) FILTER (WHERE m.measurement_concept_id = plaquetas_concept()) AS plaquetas_nadir,
    count(*)               FILTER (WHERE m.measurement_concept_id = hb_concept())        AS n_hb,
    count(*)               FILTER (WHERE m.measurement_concept_id = plaquetas_concept()) AS n_plaquetas
FROM cohorte c
JOIN measurement m
  ON  m.person_id = c.person_id
  AND m.measurement_concept_id IN (hb_concept(), plaquetas_concept())
  AND m.value_as_number IS NOT NULL
  AND m.measurement_datetime > c.t_indice
  AND m.measurement_datetime <= c.t_fin_seguimiento
GROUP BY c.visit_occurrence_id;

-- Unidades por las que pasó cada hospitalización
CREATE OR REPLACE TABLE unidades AS
SELECT
    vd.visit_occurrence_id,
    vd.visit_detail_start_datetime AS inicio,
    vd.visit_detail_end_datetime   AS fin,
    cs.care_site_name              AS unidad,
    regexp_matches(cs.care_site_name, 'Intensive Care Unit|\(CCU\)|SICU')                 AS es_uci,
    regexp_matches(cs.care_site_name, '^(Cardiac Surgery|Cardiology Surgery Intermediate|Cardiac Vascular Intensive Care Unit)') AS es_cx_cardiaca,
    regexp_matches(cs.care_site_name, '^(Surgical Intensive Care Unit|Trauma SICU|Neuro Surgical Intensive Care Unit|PACU|Surgery/|Vascular|Transplant|Med/Surg/Trauma|Med/Surg/GYN)') AS es_quirurgica
FROM visit_detail vd
JOIN care_site cs USING (care_site_id);

CREATE OR REPLACE TABLE uci AS
SELECT
    c.visit_occurrence_id,
    bool_or(c.t_indice BETWEEN u.inicio AND u.fin)                      AS uci_en_indice,
    bool_or(u.inicio > c.t_indice AND u.inicio <= c.t_fin_seguimiento)   AS uci_posterior
FROM cohorte c
JOIN unidades u USING (visit_occurrence_id)
WHERE u.es_uci
GROUP BY c.visit_occurrence_id;

CREATE OR REPLACE TABLE estrato AS
SELECT
    visit_occurrence_id,
    CASE
        WHEN bool_or(es_cx_cardiaca) THEN 'cirugia_cardiaca'
        WHEN bool_or(es_quirurgica)  THEN 'quirurgico'
        ELSE 'medico'
    END AS estrato
FROM unidades
GROUP BY visit_occurrence_id;

CREATE OR REPLACE TABLE indicaciones AS
SELECT
    visit_occurrence_id,
    bool_or(regexp_matches(condition_source_value, '^(4273[12]|I48)'))                    AS fibrilacion_auricular,
    bool_or(regexp_matches(condition_source_value, '^(41[0-4]|I2[0-5])'))                 AS cardiopatia_isquemica,
    bool_or(regexp_matches(condition_source_value, '^(4151|453[4-9]|I26|I824|I825|I829)')) AS tromboembolia_venosa,
    bool_or(regexp_matches(condition_source_value, '^(428|I50)'))                         AS insuficiencia_cardiaca
FROM condition_occurrence
WHERE condition_type_concept_id = 32821  -- diagnósticos codificados de la hospitalización
GROUP BY visit_occurrence_id;

CREATE OR REPLACE TABLE cohorte_analitica AS
SELECT
    c.*,
    coalesce(e.estrato, 'medico')                          AS estrato,
    coalesce(u.uci_en_indice, false)                       AS uci_en_indice,
    coalesce(i.fibrilacion_auricular, false)               AS fibrilacion_auricular,
    coalesce(i.cardiopatia_isquemica, false)               AS cardiopatia_isquemica,
    coalesce(i.tromboembolia_venosa, false)                AS tromboembolia_venosa,
    coalesce(i.insuficiencia_cardiaca, false)              AS insuficiencia_cardiaca,
    date_diff('minute', c.t_indice, c.t_fin_seguimiento) / 1440.0 AS dias_seguimiento,

    ls.n_hb,
    ls.hb_nadir,
    c.hb_basal - ls.hb_nadir                               AS caida_hb_max,
    coalesce(c.hb_basal - ls.hb_nadir >= 2, false)         AS caida_hb_2,
    CAST(NULL AS BOOLEAN)                                  AS transfusion_gr,     -- no disponible en OMOP
    coalesce(c.hb_basal - ls.hb_nadir >= 2, false)         AS sangrado_relevante, -- solo componente de laboratorio

    ls.n_plaquetas,
    ls.plaquetas_nadir,
    100.0 * (ls.plaquetas_nadir - c.plaquetas_basal) / c.plaquetas_basal AS plaquetas_cambio_pct,
    CASE WHEN c.plaquetas_basal >= 150 THEN coalesce(ls.plaquetas_nadir < 100, false) END AS trombocitopenia_nueva,
    coalesce(ls.plaquetas_nadir <= 0.5 * c.plaquetas_basal, false)        AS plaquetas_caida_50,

    date_diff('minute', c.t_indice, c.dischtime) / 1440.0  AS estancia_post_indice_dias,
    coalesce(u.uci_posterior, false)                       AS uci_posterior,
    c.muerte_hospitalaria                                  AS muerte
FROM cohorte c
LEFT JOIN estrato e           USING (visit_occurrence_id)
LEFT JOIN uci u               USING (visit_occurrence_id)
LEFT JOIN indicaciones i      USING (visit_occurrence_id)
LEFT JOIN labs_seguimiento ls USING (visit_occurrence_id);
