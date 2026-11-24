-- Sensibilidad · Restringe la cohorte a hospitalizaciones con registro de administración (emar).
-- Requiere: admissions_fuente (admisiones originales) y emar.

CREATE OR REPLACE VIEW admissions AS
SELECT *
FROM admissions_fuente
WHERE hadm_id IN (SELECT hadm_id FROM emar WHERE hadm_id IS NOT NULL);
