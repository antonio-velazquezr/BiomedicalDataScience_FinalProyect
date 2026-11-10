-- OMOP 02 · Cohorte: anticoagulante + antiagregante vs. solo anticoagulante
--
-- Misma definición que sql/02_cohorte.sql (versión nativa MIMIC), escrita sobre tablas OMOP CDM 5.3:
--   person, visit_occurrence, drug_exposure, measurement, condition_occurrence, death.
--
-- Diferencias obligadas por el modelo de datos (ver docs/omop.md):
--   * Hospitalización = visit_occurrence con visit_concept_id de atención hospitalaria
--     (9201 Inpatient, 262 ER+Inpatient, 8870 ER que termina en ingreso, 8883, 581385 Observation).
--   * El criterio "diagnóstico principal distinto de sangrado" no es implementable: OMOP no conserva
--     el orden de los diagnósticos (condition_status_concept_id viene vacío en este release).
--     El paso se mantiene en la atrición con 0 exclusiones para que las tablas sean comparables.
--
-- Requiere: rx_antitrombotico y macros de 01_conjuntos_conceptos.sql.

CREATE OR REPLACE MACRO ventana_basal_h()      AS 48;
CREATE OR REPLACE MACRO seguimiento_d()        AS 14;
CREATE OR REPLACE MACRO previo_ingreso_h()     AS 24;
CREATE OR REPLACE MACRO efecto_residual_ap_d() AS 7;
CREATE OR REPLACE MACRO dosis_unica_ac_h()     AS 24;

-- Hospitalizaciones
CREATE OR REPLACE TABLE hosp AS
SELECT
    v.person_id,
    v.visit_occurrence_id,
    p.person_source_value                                          AS subject_id_fuente,
    v.visit_source_value                                           AS visita_fuente,
    v.visit_start_datetime                                         AS admittime,
    v.visit_end_datetime                                           AS dischtime,
    CASE p.gender_concept_id WHEN 8532 THEN 'F' WHEN 8507 THEN 'M' END AS sexo,
    year(v.visit_start_datetime) - p.year_of_birth                 AS edad,
    date_diff('minute', v.visit_start_datetime, v.visit_end_datetime) / 1440.0 AS estancia_dias,
    v.discharge_to_concept_id = 4216643                            -- "Patient died"
        OR EXISTS (SELECT 1 FROM death d
                   WHERE d.person_id = v.person_id
                     AND d.death_datetime BETWEEN v.visit_start_datetime
                                              AND v.visit_end_datetime + INTERVAL 1 DAY) AS muerte_hospitalaria
FROM visit_occurrence v
JOIN person p USING (person_id)
WHERE v.visit_concept_id IN (9201, 262, 8870, 8883, 581385);

-- Intervalos de exposición (mismas reglas que la versión nativa)
CREATE OR REPLACE TABLE intervalos AS
SELECT *
FROM (
    SELECT
        r.visit_occurrence_id,
        r.familia,
        r.farmaco,
        r.intensidad,
        greatest(r.starttime, h.admittime) AS inicio,
        least(
            CASE
                WHEN r.familia = 'antiagregante'
                    THEN coalesce(greatest(r.stoptime, r.starttime), h.dischtime) + to_days(efecto_residual_ap_d())
                WHEN r.stoptime IS NULL        THEN h.dischtime
                WHEN r.stoptime <= r.starttime THEN r.starttime + to_hours(dosis_unica_ac_h())
                ELSE r.stoptime
            END,
            h.dischtime
        ) AS fin
    FROM rx_antitrombotico r
    JOIN hosp h USING (visit_occurrence_id)
    WHERE r.starttime BETWEEN h.admittime - to_hours(previo_ingreso_h()) AND h.dischtime
)
WHERE fin > inicio;

-- Primer solapamiento anticoagulante-antiagregante
CREATE OR REPLACE TABLE solapamiento AS
SELECT
    ac.visit_occurrence_id,
    min(greatest(ac.inicio, ap.inicio))                    AS t_solapamiento,
    arg_min(ac.intensidad, greatest(ac.inicio, ap.inicio)) AS intensidad_solapamiento,
    arg_min(ac.farmaco,    greatest(ac.inicio, ap.inicio)) AS anticoagulante_solapamiento,
    arg_min(ap.farmaco,    greatest(ac.inicio, ap.inicio)) AS antiagregante_solapamiento
FROM intervalos ac
JOIN intervalos ap
  ON  ac.visit_occurrence_id = ap.visit_occurrence_id
  AND ac.familia = 'anticoagulante'
  AND ap.familia = 'antiagregante'
  AND greatest(ac.inicio, ap.inicio) < least(ac.fin, ap.fin)
GROUP BY ac.visit_occurrence_id;

CREATE OR REPLACE TABLE expo AS
SELECT
    i.visit_occurrence_id,
    min(i.inicio)                   FILTER (WHERE i.familia = 'anticoagulante') AS t_anticoagulante,
    arg_min(i.intensidad, i.inicio) FILTER (WHERE i.familia = 'anticoagulante') AS intensidad_primer_ac,
    arg_min(i.farmaco, i.inicio)    FILTER (WHERE i.familia = 'anticoagulante') AS primer_anticoagulante,
    EXISTS (SELECT 1 FROM rx_antitrombotico r
            WHERE r.visit_occurrence_id = i.visit_occurrence_id AND r.familia = 'antiagregante') AS recibio_antiagregante
FROM intervalos i
GROUP BY i.visit_occurrence_id;

CREATE OR REPLACE TABLE clasificacion AS
SELECT
    e.visit_occurrence_id,
    e.t_anticoagulante,
    CASE
        WHEN s.t_solapamiento IS NOT NULL                 THEN 'combinacion'
        WHEN NOT coalesce(e.recibio_antiagregante, false) THEN 'solo_anticoagulante'
    END AS grupo,
    coalesce(s.t_solapamiento, e.t_anticoagulante)                AS t_indice,
    CASE WHEN s.t_solapamiento IS NOT NULL THEN s.intensidad_solapamiento ELSE e.intensidad_primer_ac END AS intensidad,
    CASE WHEN s.t_solapamiento IS NOT NULL THEN s.anticoagulante_solapamiento ELSE e.primer_anticoagulante END AS anticoagulante,
    s.antiagregante_solapamiento                                  AS antiagregante
FROM expo e
LEFT JOIN solapamiento s USING (visit_occurrence_id)
WHERE e.t_anticoagulante IS NOT NULL;

-- Laboratorios basales (measurement, LOINC), por persona en las 48 h previas a la fecha índice
CREATE OR REPLACE TABLE basal AS
SELECT
    c.visit_occurrence_id,
    arg_max(m.value_as_number, m.measurement_datetime) FILTER (WHERE m.measurement_concept_id = plaquetas_concept()) AS plaquetas_basal,
    arg_max(m.value_as_number, m.measurement_datetime) FILTER (WHERE m.measurement_concept_id = hb_concept())        AS hb_basal
FROM clasificacion c
JOIN hosp h USING (visit_occurrence_id)
JOIN measurement m
  ON  m.person_id = h.person_id
  AND m.measurement_concept_id IN (hb_concept(), plaquetas_concept())
  AND m.value_as_number IS NOT NULL
  AND m.measurement_datetime BETWEEN c.t_indice - to_hours(ventana_basal_h()) AND c.t_indice
WHERE c.grupo IS NOT NULL
GROUP BY c.visit_occurrence_id;

CREATE OR REPLACE TABLE elegibilidad AS
SELECT
    h.*,
    c.* EXCLUDE (visit_occurrence_id),
    b.plaquetas_basal,
    b.hb_basal,
    h.edad >= 18                                             AS c_adulto,
    h.estancia_dias >= 1                                     AS c_estancia,
    c.t_anticoagulante IS NOT NULL                           AS c_anticoagulante,
    c.grupo IS NOT NULL                                      AS c_clasificable,
    true                                                     AS c_sin_sangrado_principal,  -- no implementable en OMOP
    b.plaquetas_basal IS NOT NULL AND b.hb_basal IS NOT NULL AS c_basal
FROM hosp h
LEFT JOIN clasificacion c USING (visit_occurrence_id)
LEFT JOIN basal b         USING (visit_occurrence_id);

CREATE OR REPLACE TABLE elegibilidad AS
SELECT *,
    coalesce(c_adulto AND c_estancia AND c_anticoagulante AND c_clasificable
             AND c_sin_sangrado_principal AND c_basal, false) AS c_elegible
FROM elegibilidad;

CREATE OR REPLACE TABLE elegibilidad AS
SELECT *,
    c_elegible AND row_number() OVER (PARTITION BY person_id, c_elegible ORDER BY admittime) = 1 AS c_primera
FROM elegibilidad;

CREATE OR REPLACE TABLE atricion AS
WITH pasos AS (
    SELECT *,
        c_adulto                                                                                       AS p2,
        c_adulto AND c_estancia                                                                        AS p3,
        c_adulto AND c_estancia AND coalesce(c_anticoagulante, false)                                  AS p4,
        c_adulto AND c_estancia AND coalesce(c_anticoagulante, false) AND coalesce(c_clasificable, false) AS p5
    FROM elegibilidad
)
SELECT 1 AS paso, 'Hospitalizaciones en OMOP (visit_occurrence hospitalarias)' AS criterio,
       count(*) AS hospitalizaciones, count(DISTINCT person_id) AS pacientes FROM pasos
UNION ALL SELECT 2, 'Edad >= 18 años', count(*), count(DISTINCT person_id) FROM pasos WHERE p2
UNION ALL SELECT 3, 'Estancia >= 24 h', count(*), count(DISTINCT person_id) FROM pasos WHERE p3
UNION ALL SELECT 4, '>= 1 anticoagulante en la hospitalización', count(*), count(DISTINCT person_id) FROM pasos WHERE p4
UNION ALL SELECT 5, 'Clasificable (combinación con solapamiento o sin antiagregante)', count(*), count(DISTINCT person_id) FROM pasos WHERE p5
UNION ALL SELECT 6, 'Diagnóstico principal distinto de sangrado (no implementable en OMOP)', count(*), count(DISTINCT person_id) FROM pasos WHERE p5
UNION ALL SELECT 7, 'Plaquetas y Hb basales (48 h previas)', count(*), count(DISTINCT person_id) FROM pasos WHERE c_elegible
UNION ALL SELECT 8, 'Primera hospitalización elegible por paciente', count(*), count(DISTINCT person_id) FROM pasos WHERE c_primera
ORDER BY paso;

CREATE OR REPLACE TABLE cohorte AS
SELECT
    person_id,
    visit_occurrence_id,
    subject_id_fuente,
    visita_fuente,
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
