-- 03 · Desenlaces y covariables
--
-- Todos los desenlaces se miden en la ventana (t_indice, t_fin_seguimiento].
--
-- Principal: sangrado clínicamente relevante = caída de Hb >= 2 g/dL respecto a la basal
--            o transfusión de concentrado eritrocitario.
-- Secundarios: cada componente; caída máxima de Hb; plaquetas (cambio % al nadir, trombocitopenia
--              nueva, caída >= 50 %); estancia desde la fecha índice; ingreso a UCI posterior;
--              mortalidad hospitalaria.
-- Covariables: estrato clínico, UCI en la fecha índice, indicaciones (CIE de la misma hospitalización).
--
-- Requiere: cohorte (02_cohorte.sql).

-- Valores de laboratorio durante el seguimiento: nadir de Hb y de plaquetas
CREATE OR REPLACE TABLE labs_seguimiento AS
SELECT
    c.hadm_id,
    min(l.valuenum) FILTER (WHERE l.itemid = 51222) AS hb_nadir,
    min(l.valuenum) FILTER (WHERE l.itemid = 51265) AS plaquetas_nadir,
    count(*)        FILTER (WHERE l.itemid = 51222) AS n_hb,
    count(*)        FILTER (WHERE l.itemid = 51265) AS n_plaquetas
FROM cohorte c
JOIN labevents l
  ON  l.subject_id = c.subject_id
  AND l.itemid IN (51222, 51265)
  AND l.valuenum IS NOT NULL
  AND l.charttime > c.t_indice
  AND l.charttime <= c.t_fin_seguimiento
GROUP BY c.hadm_id;

-- Transfusión de concentrado eritrocitario (solo registrada en UCI)
CREATE OR REPLACE TABLE transfusion AS
SELECT
    c.hadm_id,
    min(i.starttime) AS t_primera_transfusion,
    count(*)         AS n_transfusiones
FROM cohorte c
JOIN inputevents i
  ON  i.hadm_id = c.hadm_id
  AND i.starttime > c.t_indice
  AND i.starttime <= c.t_fin_seguimiento
JOIN d_items d
  ON  d.itemid = i.itemid
  AND d.label ILIKE '%packed%'
GROUP BY c.hadm_id;

-- UCI: estancia activa en la fecha índice e ingreso posterior
CREATE OR REPLACE TABLE uci AS
SELECT
    c.hadm_id,
    bool_or(c.t_indice BETWEEN u.intime AND u.outtime)                       AS uci_en_indice,
    bool_or(u.intime > c.t_indice AND u.intime <= c.t_fin_seguimiento)        AS uci_posterior
FROM cohorte c
JOIN icustays u USING (hadm_id)
GROUP BY c.hadm_id;

-- Estrato clínico según servicio tratante
CREATE OR REPLACE TABLE estrato AS
SELECT
    hadm_id,
    CASE
        WHEN bool_or(curr_service = 'CSURG') THEN 'cirugia_cardiaca'
        WHEN bool_or(curr_service IN ('SURG', 'NSURG', 'VSURG', 'TRAUM', 'ORTHO', 'TSURG', 'GYN', 'PSURG', 'ENT'))
            THEN 'quirurgico'
        ELSE 'medico'
    END AS estrato
FROM services
GROUP BY hadm_id;

-- Indicaciones (diagnósticos de la misma hospitalización)
CREATE OR REPLACE TABLE indicaciones AS
SELECT
    hadm_id,
    bool_or(regexp_matches(CAST(icd_code AS VARCHAR), '^(4273[12]|I48)'))                    AS fibrilacion_auricular,
    bool_or(regexp_matches(CAST(icd_code AS VARCHAR), '^(41[0-4]|I2[0-5])'))                 AS cardiopatia_isquemica,
    bool_or(regexp_matches(CAST(icd_code AS VARCHAR), '^(4151|453[4-9]|I26|I824|I825|I829)')) AS tromboembolia_venosa,
    bool_or(regexp_matches(CAST(icd_code AS VARCHAR), '^(428|I50)'))                         AS insuficiencia_cardiaca
FROM diagnoses_icd
GROUP BY hadm_id;

-- Cohorte analítica final
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

    -- Sangrado
    ls.n_hb,
    ls.hb_nadir,
    c.hb_basal - ls.hb_nadir                               AS caida_hb_max,
    coalesce(c.hb_basal - ls.hb_nadir >= 2, false)         AS caida_hb_2,
    t.n_transfusiones IS NOT NULL                          AS transfusion_gr,
    coalesce(c.hb_basal - ls.hb_nadir >= 2, false)
        OR t.n_transfusiones IS NOT NULL                   AS sangrado_relevante,

    -- Plaquetas
    ls.n_plaquetas,
    ls.plaquetas_nadir,
    100.0 * (ls.plaquetas_nadir - c.plaquetas_basal) / c.plaquetas_basal AS plaquetas_cambio_pct,
    CASE WHEN c.plaquetas_basal >= 150 THEN coalesce(ls.plaquetas_nadir < 100, false) END AS trombocitopenia_nueva,
    coalesce(ls.plaquetas_nadir <= 0.5 * c.plaquetas_basal, false)        AS plaquetas_caida_50,

    -- Hospitalarias
    date_diff('minute', c.t_indice, c.dischtime) / 1440.0  AS estancia_post_indice_dias,
    coalesce(u.uci_posterior, false)                       AS uci_posterior,
    c.muerte_hospitalaria = 1                              AS muerte
FROM cohorte c
LEFT JOIN estrato e           USING (hadm_id)
LEFT JOIN uci u               USING (hadm_id)
LEFT JOIN indicaciones i      USING (hadm_id)
LEFT JOIN labs_seguimiento ls USING (hadm_id)
LEFT JOIN transfusion t       USING (hadm_id);
