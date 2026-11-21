-- Historia · ¿Qué hay detrás de cada caída de hemoglobina?
--
-- Requiere: cohorte_analitica (sql/01-03) y las vistas procedures_icd, d_icd_procedures,
-- d_icd_diagnoses y outputevents.
--
-- Tiempo de referencia (t_ref):
--   * con evento: primera caída de Hb >= 2 g/dL o primera transfusión;
--   * sin evento: momento del nadir de Hb, para comparar una ventana equivalente.
--
-- Explicación probable, jerárquica y mutuamente excluyente (NO prueba causalidad):
--   1. hemorragia documentada  código CIE de hemorragia en la hospitalización
--   2. cirugía o intervención  procedimiento mayor o vascular entre 2 días antes y el día de t_ref
--   3. líquidos IV             >= 2 L de cristaloides/coloides en las 48 h previas (solo medible en UCI)
--   4. sin causa identificada

CREATE OR REPLACE MACRO patron_hemorragia() AS
    '(?i)hemorrhag|bleed|hematemesis|melena|hematuria|hemoptysis|blood loss';
CREATE OR REPLACE MACRO patron_no_hemorragia() AS
    '(?i)without (mention of )?(hemorrhag|bleed)|no bleed|Iatrogenic cerebrovascular';
CREATE OR REPLACE MACRO patron_vascular() AS
    '(?i)coronary arteriography|left heart cardiac catheterization|Fluoroscopy of Multiple Coronary|Cardiac Sampling and Pressure, Left Heart|Dilation of|Occlusion of|Extirpation of Matter from .*(Artery|Vein)';
CREATE OR REPLACE MACRO patron_no_mayor() AS
    '(?i)catheter|infusion|ventilation|endotracheal|nutritional|ultrasonograph|fluoroscopy|filtration|transfusion|monitoring|cardiac output|arteriograph|percutaneous abdominal|endoscop|biopsy|inspection|guidance|imaging|measurement|hemodialysis|spinal tap|puncture|electro|AICD|injection|bronchoscopy|Drainage of .*(Percutaneous|Endoscopic)|gastrostomy|Insertion of|countershock|mapping|thoracentesis|angiocardiography|immobilization|irrigation|extraction of other tooth|Introduction of';

-- Códigos de hemorragia por hospitalización, con su sitio
CREATE OR REPLACE TABLE hemorragias AS
SELECT
    x.hadm_id,
    d.long_title,
    CASE
        WHEN regexp_matches(d.long_title, '(?i)complicating a procedure|postprocedural|during surgical|during other specified medical|during heart') THEN 1
        WHEN regexp_matches(d.long_title, '(?i)gastrointestinal|ulcer|melena|hematemesis|rectum|varices') THEN 2
        WHEN regexp_matches(d.long_title, '(?i)hematuria') THEN 3
        WHEN regexp_matches(d.long_title, '(?i)subarachnoid|subdural|intracerebral|cerebrum') THEN 4
        WHEN regexp_matches(d.long_title, '(?i)posthemorrhagic|blood loss') THEN 6
        ELSE 5
    END AS prioridad_sitio
FROM diagnoses_icd x
JOIN d_icd_diagnoses d ON d.icd_code = x.icd_code AND d.icd_version = x.icd_version
WHERE regexp_matches(d.long_title, patron_hemorragia())
  AND NOT regexp_matches(d.long_title, patron_no_hemorragia());

CREATE OR REPLACE TABLE sitio_hemorragia AS
SELECT
    hadm_id,
    CASE min(prioridad_sitio)
        WHEN 1 THEN 'Asociada a procedimiento'
        WHEN 2 THEN 'Digestiva'
        WHEN 3 THEN 'Urinaria'
        WHEN 4 THEN 'Intracraneal'
        WHEN 6 THEN 'Anemia aguda por hemorragia (sin sitio)'
        ELSE 'Otra'
    END AS sitio
FROM hemorragias
GROUP BY hadm_id;

CREATE OR REPLACE TABLE tiempos_evento AS
WITH tx AS (
    SELECT c.hadm_id, min(i.starttime) AS t
    FROM cohorte_analitica c
    JOIN inputevents i USING (hadm_id)
    JOIN d_items d ON d.itemid = i.itemid AND d.label ILIKE '%packed%'
    WHERE i.starttime > c.t_indice AND i.starttime <= c.t_fin_seguimiento
    GROUP BY c.hadm_id
), hb AS (
    SELECT c.hadm_id,
           min(l.charttime) FILTER (WHERE l.valuenum <= c.hb_basal - 2) AS t_caida,
           arg_min(l.charttime, l.valuenum) AS t_nadir,
           count(*) FILTER (WHERE l.charttime <= c.t_indice + INTERVAL 48 HOUR) AS n_hb_48h
    FROM cohorte_analitica c
    JOIN labevents l
      ON l.subject_id = c.subject_id AND l.itemid = 51222 AND l.valuenum IS NOT NULL
     AND l.charttime > c.t_indice AND l.charttime <= c.t_fin_seguimiento
    GROUP BY c.hadm_id
)
SELECT
    c.hadm_id,
    least(hb.t_caida, tx.t)                                     AS t_evento,
    coalesce(least(hb.t_caida, tx.t), hb.t_nadir, c.t_fin_seguimiento) AS t_ref,
    coalesce(hb.n_hb_48h, 0)                                    AS n_hb_48h
FROM cohorte_analitica c
LEFT JOIN hb USING (hadm_id)
LEFT JOIN tx USING (hadm_id);

CREATE OR REPLACE TABLE causas AS
WITH base AS (
    SELECT
        c.*,
        t.t_evento,
        t.t_ref,
        t.n_hb_48h,
        s.sitio,
        s.hadm_id IS NOT NULL AS hemorragia_cie,
        EXISTS (
            SELECT 1 FROM procedures_icd x
            JOIN d_icd_procedures p ON p.icd_code = x.icd_code AND p.icd_version = x.icd_version
            WHERE x.hadm_id = c.hadm_id
              AND (regexp_matches(p.long_title, patron_vascular()) OR NOT regexp_matches(p.long_title, patron_no_mayor()))
              AND x.chartdate BETWEEN CAST(t.t_ref AS DATE) - 2 AND CAST(t.t_ref AS DATE)
        ) AS cirugia_48h,
        EXISTS (
            SELECT 1 FROM procedures_icd x
            JOIN d_icd_procedures p ON p.icd_code = x.icd_code AND p.icd_version = x.icd_version
            WHERE x.hadm_id = c.hadm_id
              AND (regexp_matches(p.long_title, patron_vascular()) OR NOT regexp_matches(p.long_title, patron_no_mayor()))
        ) AS procedimiento_hosp,
        EXISTS (
            SELECT 1 FROM icustays u
            WHERE u.hadm_id = c.hadm_id AND u.intime <= t.t_ref AND u.outtime >= t.t_ref - INTERVAL 48 HOUR
        ) AS uci_ventana,
        coalesce((
            SELECT sum(i.amount) FROM inputevents i JOIN d_items d USING (itemid)
            WHERE i.hadm_id = c.hadm_id AND i.amountuom = 'ml'
              AND i.starttime BETWEEN t.t_ref - INTERVAL 48 HOUR AND t.t_ref
              AND (i.ordercategoryname IN ('02-Fluids (Crystalloids)', '03-IV Fluid Bolus', '04-Fluids (Colloids)')
                   OR d.label IN ('OR Crystalloid Intake', 'OR Colloid Intake'))
        ), 0) AS liquidos_ml
    FROM cohorte_analitica c
    JOIN tiempos_evento t USING (hadm_id)
    LEFT JOIN sitio_hemorragia s USING (hadm_id)
)
SELECT
    *,
    liquidos_ml >= 2000 AS liquidos_2l,
    CASE
        WHEN hemorragia_cie THEN 'Hemorragia documentada'
        WHEN cirugia_48h    THEN 'Cirugía o intervención'
        WHEN liquidos_ml >= 2000 THEN 'Líquidos IV ≥ 2 L'
        ELSE 'Sin causa identificada'
    END AS explicacion,
    sangrado_relevante AND hemorragia_cie AS sangrado_documentado,
    coalesce(caida_hb_max >= 1, false) AS caida_1,
    coalesce(caida_hb_max >= 3, false) AS caida_3,
    coalesce(caida_hb_max >= 4, false) AS caida_4
FROM base;
