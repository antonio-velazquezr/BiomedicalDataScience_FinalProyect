# Propuesta de proyecto final

**Título:** Seguridad hematológica de la tromboprofilaxis con heparina: incidencia y temporalidad de
trombocitopenia en pacientes hospitalizados, con estratificación por cirugía

**Modalidad:** A — Estudio de caracterización / farmacovigilancia
**Fecha:** 2026-11-09

## Pregunta

¿Con qué frecuencia y en qué momento aparece trombocitopenia durante la tromboprofilaxis con heparina
en pacientes hospitalizados, y cómo cambia este patrón entre pacientes médicos, quirúrgicos y de cirugía
cardiaca?

**Secundaria (exploratoria):** ¿la incidencia difiere entre heparina no fraccionada (HNF) y enoxaparina?

## Justificación

La tromboprofilaxis farmacológica se usa casi de rutina en pacientes hospitalizados. Su reacción adversa
hematológica más relevante es la trombocitopenia inducida por heparina (HIT), que suele aparecer entre
los días 5 y 10 de exposición y es más frecuente con HNF que con heparinas de bajo peso molecular.
En pacientes quirúrgicos, la cirugía por sí misma baja las plaquetas en los primeros días. Distinguir
esa caída esperada de una caída sospechosa de HIT es el problema central de farmacovigilancia que
aborda este proyecto.

## Datos

- **Fuente:** MIMIC-IV Clinical Database Demo v2.2 (PhysioNet), 100 pacientes, licencia ODbL.
  Descargado el 2026-11-09. Los datos no se incluyen en el repositorio.
- **Modelo de datos:** conversión a OMOP CDM en DuckDB. Las definiciones de cohorte se escriben en SQL.
- **Volumen preliminar:** 79 pacientes reciben heparina SC profiláctica y unos 10 enoxaparina profiláctica.
  Hay 83 hospitalizaciones quirúrgicas con procedimiento mayor (20 de cirugía cardiaca). Las plaquetas
  se miden casi a diario.

## Diseño

| Elemento | Definición |
|---|---|
| Población | Hospitalizaciones de ≥24 h que inician profilaxis (heparina SC o enoxaparina ≤40 mg) sin anticoagulación terapéutica previa; primera hospitalización elegible por paciente |
| Fecha índice | Primera dosis de profilaxis |
| Basal | Última cuenta de plaquetas en las 48 h previas a la fecha índice (requisito de inclusión) |
| Seguimiento | Desde la fecha índice hasta el alta, el fin de la profilaxis o el día 14, lo que ocurra primero |
| Desenlace principal | Caída de plaquetas ≥50 % respecto a la basal |
| Temporalidad | Caída temprana (días 1–3) vs. caída compatible con HIT (días 5–10) |
| Estratos | Médico / quirúrgico / cirugía cardiaca |
| Comparación | Antes vs. durante la profilaxis (cada paciente es su propio control); HNF vs. enoxaparina (exploratoria) |

**Análisis de sensibilidad:** umbral de caída (≥30 % vs. ≥50 %; <100k vs. <150k), exposición por
prescripción vs. por administración (`emar`), exclusión de los primeros 4 días posoperatorios.

**Entregables:** tabla de atrición, Tabla 1 por estrato, incidencia con IC 95 %, curvas de plaquetas
por día desde la fecha índice, puntaje 4T parcial (componentes de magnitud y temporalidad).

## Limitaciones previstas

- No hay prueba de anticuerpos anti-PF4 en el demo. Se reportará "trombocitopenia compatible con HIT",
  no HIT confirmada.
- El tamaño de muestra es pequeño; la comparación HNF vs. enoxaparina es exploratoria.
- No se ve la heparina intraoperatoria (bypass cardiaco) ni la medicación previa al ingreso.
- Los procedimientos tienen fecha pero no hora.
- Los datos provienen de un solo centro de tercer nivel.

## Entorno y reproducibilidad

Python (polars, DuckDB), SQL sobre OMOP, Docker, pytest con datos sintéticos de prueba, CI en GitHub
Actions. Si se obtiene la acreditación de PhysioNet a tiempo, el mismo pipeline se correrá sobre
MIMIC-IV completo.
