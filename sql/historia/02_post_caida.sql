-- Historia · ¿Qué pasa después de la primera caída de hemoglobina?
--
-- Requiere: causas (01_causas_sangrado.sql), rx_antitrombotico y las tablas de laboratorio/UCI.
--
-- Población: pacientes de la cohorte con una caída de Hb >= 2 g/dL respecto a la basal.
-- Tiempo cero (t0): primera medición de Hb que cumple la caída.
-- Seguimiento: desde t0 hasta el alta o 7 días, lo que ocurra primero.
--
-- Desenlaces:
--   recupera_hb      alguna Hb >= basal - 1 g/dL en el seguimiento
--   nueva_caida      alguna Hb <= Hb en t0 - 1 g/dL
--   cambio_hb_72h    Hb más cercana a t0 + 72 h (entre 48 y 96 h) menos Hb en t0
--   transfusion_post, uci_post, muerte, dias_a_alta
--
-- Manejo tras la caída (orden activa en las 24 h siguientes a t0, sin efecto residual):
--   ap_continua, ac_continua

CREATE OR REPLACE MACRO seguimiento_post_d() AS 7;

CREATE OR REPLACE TABLE post_t0 AS
WITH hb AS (
    SELECT c.hadm_id, l.charttime, l.valuenum
    FROM causas c
    JOIN labevents l
      ON l.subject_id = c.subject_id AND l.itemid = 51222 AND l.valuenum IS NOT NULL
     AND l.charttime > c.t_indice AND l.charttime <= c.t_fin_seguimiento
     AND l.valuenum <= c.hb_basal - 2
)
SELECT hadm_id, min(charttime) AS t0, arg_min(valuenum, charttime) AS hb_t0
FROM hb
GROUP BY hadm_id;

CREATE OR REPLACE TABLE post_caida AS
WITH base AS (
    SELECT c.*, p.t0, p.hb_t0,
           least(c.dischtime, p.t0 + to_days(seguimiento_post_d())) AS t_fin_post
    FROM causas c
    JOIN post_t0 p USING (hadm_id)
), labs AS (
    SELECT b.hadm_id,
           min(l.charttime) FILTER (WHERE l.valuenum >= b.hb_basal - 1) AS t_recupera,
           min(l.valuenum) AS hb_min_post,
           count(*) AS n_hb_post,
           arg_min(l.valuenum, abs(date_diff('minute', b.t0 + INTERVAL 72 HOUR, l.charttime)))
               FILTER (WHERE l.charttime BETWEEN b.t0 + INTERVAL 48 HOUR AND b.t0 + INTERVAL 96 HOUR) AS hb_72h
    FROM base b
    JOIN labevents l
      ON l.subject_id = b.subject_id AND l.itemid = 51222 AND l.valuenum IS NOT NULL
     AND l.charttime > b.t0 AND l.charttime <= b.t_fin_post
    GROUP BY b.hadm_id
), tx AS (
    SELECT b.hadm_id, min(i.starttime) AS t_tx
    FROM base b
    JOIN inputevents i ON i.hadm_id = b.hadm_id AND i.starttime > b.t0 AND i.starttime <= b.t_fin_post
    JOIN d_items d ON d.itemid = i.itemid AND d.label ILIKE '%packed%'
    GROUP BY b.hadm_id
), manejo AS (
    SELECT b.hadm_id,
           bool_or(r.familia = 'antiagregante') AS ap_continua,
           bool_or(r.familia = 'anticoagulante') AS ac_continua
    FROM base b
    JOIN rx_antitrombotico r
      ON r.hadm_id = b.hadm_id
     AND r.starttime <= b.t0 + INTERVAL 24 HOUR
     AND coalesce(r.stoptime, b.dischtime) > b.t0
    GROUP BY b.hadm_id
)
SELECT
    b.*,
    l.n_hb_post,
    l.hb_min_post,
    l.hb_72h,
    l.hb_72h - b.hb_t0                                         AS cambio_hb_72h,
    b.hb_basal - b.hb_t0                                       AS magnitud_caida,
    date_diff('minute', b.t0, b.t_fin_post) / 1440.0           AS dias_post,
    date_diff('minute', b.t0, l.t_recupera) / 1440.0           AS dias_a_recuperar,
    date_diff('minute', b.t0, b.dischtime) / 1440.0            AS dias_a_alta,
    l.t_recupera IS NOT NULL                                   AS recupera_hb,
    coalesce(l.hb_min_post <= b.hb_t0 - 1, false)              AS nueva_caida,
    tx.t_tx IS NOT NULL                                        AS transfusion_post,
    EXISTS (SELECT 1 FROM icustays u WHERE u.hadm_id = b.hadm_id
            AND u.intime > b.t0 AND u.intime <= b.t_fin_post)  AS uci_post,
    coalesce(m.ap_continua, false)                             AS ap_continua,
    coalesce(m.ac_continua, false)                             AS ac_continua
FROM base b
LEFT JOIN labs l   USING (hadm_id)
LEFT JOIN tx       USING (hadm_id)
LEFT JOIN manejo m USING (hadm_id);
