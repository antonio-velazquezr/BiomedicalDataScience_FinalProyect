-- Sensibilidad · Define la exposición con las dosis realmente administradas (emar).
-- Requiere: prescriptions_fuente (órdenes originales) y emar.
--
-- Solo se conservan las órdenes con al menos una dosis administrada:
--   inicio = primera administración
--   fin    = última administración + 12 h
-- Eventos como 'Not Given' o 'Stopped' no cuentan como dosis. El resto del pipeline no cambia.

CREATE OR REPLACE VIEW prescriptions AS
WITH dosis AS (
    SELECT pharmacy_id, min(charttime) AS primera, max(charttime) AS ultima
    FROM emar
    WHERE pharmacy_id IS NOT NULL
      AND event_txt IN ('Administered', 'Confirmed', 'Started', 'Restarted',
                        'Delayed Administered', 'Delayed Confirmed')
    GROUP BY pharmacy_id
)
SELECT p.* REPLACE (d.primera AS starttime, d.ultima + INTERVAL 12 HOUR AS stoptime)
FROM prescriptions_fuente p
JOIN dosis d USING (pharmacy_id);
