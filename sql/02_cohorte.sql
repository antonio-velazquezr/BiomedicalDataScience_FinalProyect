-- 02 · Cohorte: anticoagulante + antiagregante vs. solo anticoagulante
--
-- Unidad de análisis: hospitalización (primera elegible por paciente).
--
-- Grupos:
--   combinacion          anticoagulante y antiagregante activos al mismo tiempo (solapamiento de intervalos).
--                        Fecha índice = inicio del primer solapamiento.
--   solo_anticoagulante  anticoagulante sin ningún antiagregante en toda la hospitalización.
--                        Fecha índice = inicio del primer anticoagulante.
-- Las hospitalizaciones con ambos fármacos pero sin solapamiento no son clasificables y se excluyen.
--
-- Estrato: intensidad del anticoagulante activo en la fecha índice (profilactica / terapeutica).
-- Seguimiento: desde la fecha índice hasta el alta o el día 14, lo que ocurra primero.
--
-- Criterios en orden (ver tabla `atricion`):
--   1. Hospitalizaciones en la base
--   2. Edad >= 18 años al ingreso
--   3. Estancia >= 24 h
--   4. >= 1 anticoagulante iniciado durante la hospitalización
--   5. Clasificable: combinación con solapamiento o anticoagulante sin antiagregante
--   6. Diagnóstico principal distinto de sangrado
--   7. Plaquetas y hemoglobina basales en las 48 h previas a la fecha índice
--   8. Primera hospitalización elegible por paciente
--
-- Requiere: rx_antitrombotico (01_conjuntos_farmacos.sql).

CREATE OR REPLACE MACRO ventana_basal_h()      AS 48;  -- basal: horas previas a la fecha índice
CREATE OR REPLACE MACRO seguimiento_d()        AS 14;  -- días de seguimiento máximo
CREATE OR REPLACE MACRO previo_ingreso_h()     AS 24;  -- órdenes de urgencias previas al ingreso
CREATE OR REPLACE MACRO efecto_residual_ap_d() AS 7;   -- inhibición plaquetaria irreversible (vida de la plaqueta)
CREATE OR REPLACE MACRO dosis_unica_ac_h()     AS 24;  -- duración asumida de una dosis única de anticoagulante

-- Códigos CIE-9/CIE-10 de sangrado (para excluir ingresos cuyo motivo principal es un sangrado)
CREATE OR REPLACE MACRO es_sangrado(codigo) AS regexp_matches(
    CAST(codigo AS VARCHAR),
    '^(430|431|432|578[019]|53[1-4][0246]|4560|45620|5693|5997|7863|99811|2851|85[23]'   -- CIE-9
    || '|I6[012]|K92[012]|K2[5-8][0246]|I8501|I8511|K625|R31|R042|D62|S06[3-6]|K661|R58)'  -- CIE-10
);

-- Hospitalizaciones con datos demográficos
CREATE OR REPLACE TABLE hosp AS
SELECT
    a.subject_id,
    a.hadm_id,
    a.admittime,
    a.dischtime,
    a.hospital_expire_flag                                  AS muerte_hospitalaria,
    p.gender                                                AS sexo,
    p.anchor_age + (year(a.admittime) - p.anchor_year)      AS edad,
    date_diff('minute', a.admittime, a.dischtime) / 1440.0  AS estancia_dias
FROM admissions a
JOIN patients p USING (subject_id);

-- Intervalos de exposición (todos recortados a [ingreso, alta]):
--   * Se incluyen órdenes iniciadas hasta 24 h antes del ingreso (urgencias).
--   * Sin fecha de término -> activa hasta el alta.
--   * Antiagregantes: efecto residual de 7 días tras la última dosis (inhibición irreversible).
--   * Anticoagulante en dosis única (stoptime <= starttime): 24 h de efecto.
--   * Se descartan órdenes que inician después del alta (errores de registro).
CREATE OR REPLACE TABLE intervalos AS
SELECT *
FROM (
    SELECT
        r.hadm_id,
        r.familia,
        r.farmaco,
        r.intensidad,
        greatest(r.starttime, h.admittime) AS inicio,
        least(
            CASE
                WHEN r.familia = 'antiagregante'
                    THEN coalesce(greatest(r.stoptime, r.starttime), h.dischtime) + to_days(efecto_residual_ap_d())
                WHEN r.stoptime IS NULL       THEN h.dischtime
                WHEN r.stoptime <= r.starttime THEN r.starttime + to_hours(dosis_unica_ac_h())
                ELSE r.stoptime
            END,
            h.dischtime
        ) AS fin
    FROM rx_antitrombotico r
    JOIN hosp h USING (hadm_id)
    WHERE r.starttime BETWEEN h.admittime - to_hours(previo_ingreso_h()) AND h.dischtime
)
WHERE fin > inicio;

-- Primer solapamiento anticoagulante-antiagregante por hospitalización
CREATE OR REPLACE TABLE solapamiento AS
SELECT
    ac.hadm_id,
    min(greatest(ac.inicio, ap.inicio))                                   AS t_solapamiento,
    arg_min(ac.intensidad, greatest(ac.inicio, ap.inicio))                AS intensidad_solapamiento,
    arg_min(ac.farmaco,    greatest(ac.inicio, ap.inicio))                AS anticoagulante_solapamiento,
    arg_min(ap.farmaco,    greatest(ac.inicio, ap.inicio))                AS antiagregante_solapamiento
FROM intervalos ac
JOIN intervalos ap
  ON  ac.hadm_id = ap.hadm_id
  AND ac.familia = 'anticoagulante'
  AND ap.familia = 'antiagregante'
  AND greatest(ac.inicio, ap.inicio) < least(ac.fin, ap.fin)
GROUP BY ac.hadm_id;

-- Resumen de exposición por hospitalización.
-- `recibio_antiagregante` mira cualquier orden de la hospitalización, aunque no haya formado intervalo,
-- para que el comparador sea realmente "sin antiagregante".
CREATE OR REPLACE TABLE expo AS
SELECT
    i.hadm_id,
    min(i.inicio)                 FILTER (WHERE i.familia = 'anticoagulante') AS t_anticoagulante,
    arg_min(i.intensidad, i.inicio) FILTER (WHERE i.familia = 'anticoagulante') AS intensidad_primer_ac,
    arg_min(i.farmaco, i.inicio)  FILTER (WHERE i.familia = 'anticoagulante') AS primer_anticoagulante,
    EXISTS (SELECT 1 FROM rx_antitrombotico r
            WHERE r.hadm_id = i.hadm_id AND r.familia = 'antiagregante')        AS recibio_antiagregante
FROM intervalos i
GROUP BY i.hadm_id;

-- Clasificación en grupo y fecha índice
CREATE OR REPLACE TABLE clasificacion AS
SELECT
    e.hadm_id,
    e.t_anticoagulante,
    CASE
        WHEN s.t_solapamiento IS NOT NULL                          THEN 'combinacion'
        WHEN NOT coalesce(e.recibio_antiagregante, false)          THEN 'solo_anticoagulante'
    END                                                                       AS grupo,
    CASE WHEN s.t_solapamiento IS NOT NULL THEN s.t_solapamiento ELSE e.t_anticoagulante END AS t_indice,
    CASE WHEN s.t_solapamiento IS NOT NULL THEN s.intensidad_solapamiento ELSE e.intensidad_primer_ac END AS intensidad,
    CASE WHEN s.t_solapamiento IS NOT NULL THEN s.anticoagulante_solapamiento ELSE e.primer_anticoagulante END AS anticoagulante,
    s.antiagregante_solapamiento                                              AS antiagregante
FROM expo e
LEFT JOIN solapamiento s USING (hadm_id)
WHERE e.t_anticoagulante IS NOT NULL;

-- Diagnóstico principal de sangrado
CREATE OR REPLACE TABLE dx_principal_sangrado AS
SELECT DISTINCT hadm_id
FROM diagnoses_icd
WHERE seq_num = 1 AND es_sangrado(icd_code);

-- Laboratorios basales: último valor en las 48 h previas a la fecha índice (incluye urgencias, sin hadm_id)
CREATE OR REPLACE TABLE basal AS
SELECT
    c.hadm_id,
    arg_max(l.valuenum, l.charttime) FILTER (WHERE l.itemid = 51265) AS plaquetas_basal,
    arg_max(l.valuenum, l.charttime) FILTER (WHERE l.itemid = 51222) AS hb_basal
FROM clasificacion c
JOIN hosp h USING (hadm_id)
JOIN labevents l
  ON  l.subject_id = h.subject_id
  AND l.itemid IN (51265, 51222)
  AND l.valuenum IS NOT NULL
  AND l.charttime BETWEEN c.t_indice - to_hours(ventana_basal_h()) AND c.t_indice
WHERE c.grupo IS NOT NULL
GROUP BY c.hadm_id;

-- Elegibilidad: un renglón por hospitalización, cada criterio como bandera
CREATE OR REPLACE TABLE elegibilidad AS
SELECT
    h.*,
    c.* EXCLUDE (hadm_id),
    b.plaquetas_basal,
    b.hb_basal,
    h.edad >= 18                                             AS c_adulto,
    h.estancia_dias >= 1                                     AS c_estancia,
    c.t_anticoagulante IS NOT NULL                           AS c_anticoagulante,
    c.grupo IS NOT NULL                                      AS c_clasificable,
    d.hadm_id IS NULL                                        AS c_sin_sangrado_principal,
    b.plaquetas_basal IS NOT NULL AND b.hb_basal IS NOT NULL AS c_basal
FROM hosp h
LEFT JOIN clasificacion c         USING (hadm_id)
LEFT JOIN basal b                 USING (hadm_id)
LEFT JOIN dx_principal_sangrado d USING (hadm_id);

CREATE OR REPLACE TABLE elegibilidad AS
SELECT
    *,
    coalesce(c_adulto AND c_estancia AND c_anticoagulante AND c_clasificable
             AND c_sin_sangrado_principal AND c_basal, false) AS c_elegible
FROM elegibilidad;

CREATE OR REPLACE TABLE elegibilidad AS
SELECT
    *,
    c_elegible AND row_number() OVER (PARTITION BY subject_id, c_elegible ORDER BY admittime) = 1 AS c_primera
FROM elegibilidad;

-- Tabla de atrición (criterios acumulativos)
CREATE OR REPLACE TABLE atricion AS
WITH pasos AS (
    SELECT *,
        c_adulto                                                   AS p2,
        c_adulto AND c_estancia                                    AS p3,
        c_adulto AND c_estancia AND coalesce(c_anticoagulante, false) AS p4,
        c_adulto AND c_estancia AND coalesce(c_anticoagulante, false) AND coalesce(c_clasificable, false) AS p5,
        c_adulto AND c_estancia AND coalesce(c_anticoagulante, false) AND coalesce(c_clasificable, false)
            AND c_sin_sangrado_principal                           AS p6
    FROM elegibilidad
)
SELECT 1 AS paso, 'Hospitalizaciones en MIMIC-IV Demo' AS criterio,
       count(*) AS hospitalizaciones, count(DISTINCT subject_id) AS pacientes FROM pasos
UNION ALL SELECT 2, 'Edad >= 18 años', count(*), count(DISTINCT subject_id) FROM pasos WHERE p2
UNION ALL SELECT 3, 'Estancia >= 24 h', count(*), count(DISTINCT subject_id) FROM pasos WHERE p3
UNION ALL SELECT 4, '>= 1 anticoagulante en la hospitalización', count(*), count(DISTINCT subject_id) FROM pasos WHERE p4
UNION ALL SELECT 5, 'Clasificable (combinación con solapamiento o sin antiagregante)', count(*), count(DISTINCT subject_id) FROM pasos WHERE p5
UNION ALL SELECT 6, 'Diagnóstico principal distinto de sangrado', count(*), count(DISTINCT subject_id) FROM pasos WHERE p6
UNION ALL SELECT 7, 'Plaquetas y Hb basales (48 h previas)', count(*), count(DISTINCT subject_id) FROM pasos WHERE c_elegible
UNION ALL SELECT 8, 'Primera hospitalización elegible por paciente', count(*), count(DISTINCT subject_id) FROM pasos WHERE c_primera
ORDER BY paso;

-- Cohorte (sin desenlaces; se agregan en 03_desenlaces.sql)
CREATE OR REPLACE TABLE cohorte AS
SELECT
    subject_id,
    hadm_id,
    grupo,
    intensidad,
    anticoagulante,
    antiagregante,
    sexo,
    edad,
    admittime,
    dischtime,
    muerte_hospitalaria,
    t_indice,
    least(dischtime, t_indice + to_days(seguimiento_d())) AS t_fin_seguimiento,
    plaquetas_basal,
    hb_basal
FROM elegibilidad
WHERE c_primera;
