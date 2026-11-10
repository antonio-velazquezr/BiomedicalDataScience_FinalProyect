# Anticoagulante + antiagregante en el hospital

Estudio de farmacovigilancia (Modalidad A del proyecto final del curso de ciencia de datos en salud)
sobre el **efecto conjunto de anticoagulantes y antiagregantes** en pacientes hospitalizados.

> **Estado:** en desarrollo. La cohorte y los desenlaces ya están implementados en SQL y probados
> (74 pacientes: 33 con la combinación y 41 con solo anticoagulante; ver [docs/cohorte.md](docs/cohorte.md)).
> Faltan el análisis estadístico, Docker, CI y la conversión a OMOP.

## Pregunta

En pacientes hospitalizados que reciben un anticoagulante, ¿**añadir un antiagregante** se asocia con
más sangrado y con peores desenlaces hospitalarios? El análisis se estratifica por la intensidad de la
anticoagulación (profiláctica vs. terapéutica).

Detalle en [docs/propuesta.md](docs/propuesta.md).

## Diseño

| Elemento | Definición |
|---|---|
| **Fuente** | MIMIC-IV Clinical Database Demo v2.2 (100 pacientes) |
| **Población** | Adultos con estancia ≥ 24 h que reciben un anticoagulante (profiláctico o terapéutico) durante la hospitalización. Se toma la primera hospitalización elegible por paciente |
| **Exclusiones** | Hospitalizaciones cuyo diagnóstico principal es un sangrado; pacientes sin plaquetas o Hb basales |
| **Grupo expuesto** | Anticoagulante **+ antiagregante** (aspirina o inhibidor P2Y12) con solapamiento temporal. Fecha índice: inicio del primer solapamiento |
| **Grupo comparador** | Anticoagulante **sin** antiagregante en toda la hospitalización. Fecha índice: inicio del anticoagulante |
| **Estratos** | Intensidad del anticoagulante en la fecha índice: profiláctica / terapéutica |
| **Basal** | Último valor en las 48 h previas a la fecha índice |
| **Seguimiento** | Desde la fecha índice hasta el alta o el día 14, lo que ocurra primero |

## Qué se mide

### Desenlace principal: sangrado clínicamente relevante

Se cumple con cualquiera de estas dos condiciones durante el seguimiento:
- caída de hemoglobina ≥ 2 g/dL respecto a la basal (umbral del criterio ISTH de sangrado mayor), o
- transfusión de concentrado eritrocitario.

### Desenlaces secundarios

| Dominio | Variable |
|---|---|
| Sangrado | Cada componente por separado; caída máxima de Hb (basal − nadir, en g/dL) |
| Plaquetas (seguridad) | Cambio porcentual basal → nadir; trombocitopenia nueva (< 100 × 10⁹/L con basal ≥ 150); caída ≥ 50 % |
| Hospitalarias | Estancia desde la fecha índice (días); ingreso a UCI posterior a la fecha índice; mortalidad hospitalaria |

Las plaquetas son una variable **secundaria**. Los antiagregantes inhiben la *función* plaquetaria, no
el *número* de plaquetas, así que la combinación no debería bajar la cuenta. Una caída de la cuenta
apunta más a la heparina, la cirugía o la sepsis.

### Covariables (Tabla 1)

Edad, sexo, estrato clínico (médico / quirúrgico / cirugía cardiaca), estancia en UCI al momento de la
fecha índice, fibrilación auricular, cardiopatía isquémica, tromboembolia venosa, insuficiencia cardiaca,
plaquetas y Hb basales.

### Análisis

- Descripción por grupo y por estrato de intensidad.
- Riesgo de cada desenlace binario con IC 95 % (Wilson); diferencia y razón de riesgos con IC 95 %.
- Razón de riesgos combinada entre estratos (Mantel-Haenszel).
- Variables continuas: mediana y rango intercuartílico.
- Tabla de atrición.

### Análisis de sensibilidad

- Exposición por administración real (`emar`) en lugar de prescripción
- Seguimiento de 7 días en lugar de 14
- Excluir la cirugía cardiaca
- Desenlace solo por laboratorio (sin transfusión)

### Limitaciones previstas

- **Confusión por indicación:** quienes reciben la combinación suelen tener fibrilación auricular y
  cardiopatía isquémica a la vez. Se describe en la Tabla 1, pero no se puede eliminar con esta *n*.
- **Tamaño:** 33 pacientes expuestos y 41 comparadores. Los resultados son descriptivos y exploratorios.
- **Transfusión:** solo está registrada en UCI (`inputevents`).
- **Fuente:** un solo centro de tercer nivel; no se ve la medicación previa al ingreso.

## Datos

Este repositorio **no contiene datos**. Para reproducir el trabajo:

1. Descarga *MIMIC-IV Clinical Database Demo* **v2.2** desde PhysioNet
   (<https://physionet.org/content/mimic-iv-demo/2.2/>). El acceso es abierto y la licencia es ODbL.
2. Descomprime el archivo en `data/raw/`, de modo que quede `data/raw/mimic-iv-clinical-database-demo-2.2/`.
3. Verifica la integridad con `sha256sum -c SHA256SUMS.txt` dentro de esa carpeta.

## Entorno

```bash
python -m venv .venv
.venv/Scripts/python -m pip install -e ".[dev]"
```

Docker queda pendiente.

## Cómo correrlo

```bash
python -m antitromboticos.cohorte
```

Construye la cohorte y los desenlaces en DuckDB a partir de los scripts de `sql/` y escribe la tabla de
atrición en `resultados/atricion.csv`. La definición está en [docs/cohorte.md](docs/cohorte.md).

Pruebas (usan datos sintéticos, no requieren MIMIC):

```bash
python -m pytest
```

## Estructura

```
sql/                  conjuntos de fármacos y cohorte (DuckDB)
src/antitromboticos/  código del pipeline
docs/                 propuesta, definición de cohorte
resultados/           tablas agregadas (sin datos individuales)
notebooks/            exploración (no es lógica de producción)
figuras/              figuras generadas
```

## Uso de asistentes de IA

En la planeación, la exploración de datos, el código y la redacción se usó Claude Code (Anthropic).
Todas las decisiones de diseño y su interpretación son responsabilidad del autor.
