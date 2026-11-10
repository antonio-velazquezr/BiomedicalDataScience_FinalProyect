# Propuesta de proyecto final

**Título:** Anticoagulante + antiagregante en el hospital: sangrado y desenlaces hospitalarios
asociados a la terapia antitrombótica combinada

**Modalidad:** A — Estudio de caracterización / farmacovigilancia
**Fecha:** 2026-11-09 (revisada el mismo día; sustituye la versión centrada en trombocitopenia)

## Pregunta

En pacientes hospitalizados que reciben un anticoagulante, ¿añadir un antiagregante se asocia con
más sangrado clínicamente relevante y con peores desenlaces hospitalarios? Análisis estratificado por
la intensidad de la anticoagulación (profiláctica vs. terapéutica).

## Justificación

Anticoagulantes y antiagregantes actúan sobre brazos distintos de la hemostasia: la cascada de
coagulación y la función plaquetaria. En la práctica se combinan con frecuencia, por ejemplo en
fibrilación auricular con cardiopatía isquémica, en síndrome coronario agudo, o en profilaxis
tromboembólica en pacientes que ya toman aspirina. Bloquear ambos brazos aumenta el riesgo de sangrado.
Los ensayos clínicos lo cuantifican en poblaciones seleccionadas; este proyecto describe qué ocurre en
pacientes hospitalizados reales.

## Datos

- **Fuente:** MIMIC-IV Clinical Database Demo v2.2 (PhysioNet), 100 pacientes, licencia ODbL.
  Descargado el 2026-11-09. Los datos no se incluyen en el repositorio.
- **Implementación:** SQL en DuckDB (`sql/`), ejecutado desde Python. Conversión a OMOP CDM pendiente.
- **Volumen:** la cohorte implementada tiene 74 pacientes: 33 con la combinación y 41 con solo
  anticoagulante (ver `docs/cohorte.md`).

## Diseño

| Elemento | Definición |
|---|---|
| Población | Adultos con estancia ≥ 24 h que reciben un anticoagulante; primera hospitalización elegible por paciente |
| Exclusiones | Diagnóstico principal de sangrado; sin plaquetas o Hb basales |
| Expuestos | Anticoagulante + antiagregante con solapamiento temporal; fecha índice = inicio del solapamiento |
| Comparadores | Anticoagulante sin antiagregante en la hospitalización; fecha índice = inicio del anticoagulante |
| Estratos | Intensidad: profiláctica / terapéutica |
| Seguimiento | Fecha índice → alta o día 14 |

**Desenlace principal:** sangrado clínicamente relevante, definido como caída de Hb ≥ 2 g/dL respecto a
la basal o transfusión de concentrado eritrocitario.

**Secundarios:** cada componente del desenlace principal; caída máxima de Hb; plaquetas (cambio
porcentual, trombocitopenia nueva, caída ≥ 50 %); estancia desde la fecha índice; ingreso a UCI
posterior; mortalidad hospitalaria.

**Análisis:** riesgos con IC 95 %, diferencia y razón de riesgos, razón de riesgos combinada de
Mantel-Haenszel entre estratos, Tabla 1 con indicaciones (fibrilación auricular, cardiopatía isquémica,
tromboembolia venosa, insuficiencia cardiaca) y tabla de atrición.

**Sensibilidad:** exposición por administración (`emar`); seguimiento de 7 días; excluir cirugía
cardiaca; desenlace solo por laboratorio.

## Limitaciones previstas

- Confusión por indicación: la combinación se da a pacientes más cardiópatas. Se describe, no se elimina.
- Tamaño de muestra pequeño: resultados descriptivos y exploratorios.
- La transfusión solo está registrada en UCI; no se ve la medicación previa al ingreso.
- Un solo centro de tercer nivel.

## Entorno y reproducibilidad

Python (polars, DuckDB), SQL, Docker, pytest con datos sintéticos de prueba y CI en GitHub Actions.
Si se obtiene la acreditación de PhysioNet a tiempo, el mismo pipeline se correrá sobre MIMIC-IV completo.
