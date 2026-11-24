# Anticoagulante + antiagregante en el hospital

[![CI](https://github.com/antonio-velazquezr/BiomedicalDataScience_FinalProyect/actions/workflows/ci.yml/badge.svg)](https://github.com/antonio-velazquezr/BiomedicalDataScience_FinalProyect/actions/workflows/ci.yml)

Proyecto final del curso de ciencia de datos en salud. Es un estudio de farmacovigilancia sobre el
**efecto conjunto de anticoagulantes y antiagregantes** en pacientes hospitalizados, con datos de
MIMIC-IV Demo en tablas nativas y en OMOP CDM.

**Autor:** José Antonio Velázquez Ruiz · Noviembre 2026

> **Estado:** versión de entrega. Cohorte, desenlaces, análisis descriptivo, análisis de sensibilidad y
> figuras implementados y probados. Mejora opcional a futuro: vocabularios estándar de Athena.

---

## Qué pide el curso y dónde se cumple

El enunciado del proyecto final pide un repositorio que resuelva de principio a fin una pregunta con
datos clínicos usando las herramientas del curso: "no un notebook, sino un proyecto" con código,
pruebas, documentación y entorno reproducible. Este proyecto sigue la **Modalidad A: estudio de
caracterización / epidemiológico**.

### Requisitos mínimos (todas las modalidades)

| # | Lo que pide el profesor | Dónde está en este repositorio | Estado |
|---|---|---|---|
| 1 | Repositorio con historial de commits real (no un solo commit al final) | `git log`: un commit por avance (propuesta, cohorte, análisis, CI y Docker, OMOP, diccionario…) | ✅ |
| 2 | `README.md` que permita a un tercero reproducir el trabajo | Este archivo: [Datos](#datos), [Entorno](#entorno) y [Cómo correrlo](#cómo-correrlo) | ✅ |
| 3 | Entorno containerizado (`Dockerfile` o `compose.yml`) | [`Dockerfile`](Dockerfile) y [`compose.yml`](compose.yml); la imagen se construye y se prueba en CI | ✅ |
| 4 | Al menos una definición de cohorte en SQL sobre OMOP, documentada | [`sql/omop/`](sql/omop) sobre OMOP CDM 5.3.1; documentada en [`docs/omop.md`](docs/omop.md) y [`docs/cohorte.md`](docs/cohorte.md); validada contra la versión nativa ([`resultados/omop/validacion.md`](resultados/omop/validacion.md)) | ✅ |
| 5 | Pruebas automáticas con pytest y CI en GitHub Actions | [`tests/`](tests) (48 pruebas con datos sintéticos) y [`.github/workflows/ci.yml`](.github/workflows/ci.yml) (Python 3.12 y 3.13 + Docker) | ✅ |
| 6 | Diccionario de datos / documentación de variables | [`docs/diccionario_datos.md`](docs/diccionario_datos.md): tipo, unidades, origen y % de faltantes de cada variable; una prueba falla si alguna queda sin documentar | ✅ |
| 7 | Sección de limitaciones escrita honestamente | [Limitaciones](#limitaciones) | ✅ |
| 8 | Declaración de uso de asistentes de IA | [Uso de asistentes de IA](#uso-de-asistentes-de-ia) | ✅ |
| 9 | Cero credenciales y cero datos identificables en el repositorio | [`.gitignore`](.gitignore) excluye `data/`; la CI falla si se versiona algún archivo de datos; en `resultados/` solo hay tablas agregadas | ✅ |

### Modalidad A: énfasis y extras

| Lo que pide el profesor | Dónde está | Estado |
|---|---|---|
| Definir una cohorte, caracterizarla y responder una pregunta descriptiva o de asociación | [Pregunta](#pregunta); cohorte en [`sql/`](sql) y [`sql/omop/`](sql/omop); Tabla 1 y desenlaces en [`resultados/resultados.md`](resultados/resultados.md) | ✅ |
| Énfasis en SQL, OMOP, vocabularios y cohortes (bloques II y III) | SQL en DuckDB, cohorte sobre OMOP CDM, conceptos RxNorm/LOINC ([`sql/omop/01_conjuntos_conceptos.sql`](sql/omop/01_conjuntos_conceptos.sql)) | ✅ |
| **Extra:** tabla de atrición | [`resultados/atricion.csv`](resultados/atricion.csv) (nativa) y [`resultados/omop/atricion.csv`](resultados/omop/atricion.csv); diagrama en [`figuras/principales/01_atricion.pdf`](figuras/principales/01_atricion.pdf) | ✅ |
| **Extra:** análisis de sensibilidad de la definición | [`figuras/analisis/`](figuras/analisis): umbral de sangrado (P12), ventana de seguimiento (P13), definición de la exposición (P14), restricciones de población (P15), confusión (P18), réplica en OMOP (P19) y dosis realmente administradas (P20) | ✅ |

### Reglas del curso sobre datos

| Regla | Cómo se cumple |
|---|---|
| Ningún dato identificable de paciente entra al repositorio | Los datos viven en `data/` (ignorado por git); la CI lo verifica |
| Si un dataset trae términos de uso o licencia, respetarlos | MIMIC-IV Demo y su versión OMOP son de acceso abierto con licencia ODbL |
| Declarar fuente, versión y fecha de descarga | Ver [Datos](#datos) |

### Calendario

| Sesión | Hito | Dónde | Estado |
|---|---|---|---|
| 10 | Propuesta de 1 página: pregunta, modalidad, datos, entregable esperado | [`docs/propuesta.md`](docs/propuesta.md) | ✅ |
| 18 | Cohorte definida, implementada y con tabla de atrición | [`docs/cohorte.md`](docs/cohorte.md), [`sql/`](sql), [`resultados/atricion.csv`](resultados/atricion.csv) | ✅ |
| 24 | Avance intermedio (15 min de revisión con el profesor) | Todo lo anterior + [`figuras/`](figuras) | Repositorio compartido con el profesor |
| 30 | Entrega del repositorio final | Este repositorio | ✅ Versión de entrega |
| 31 | Presentación de 12 min + 5 de preguntas | Última semana de noviembre | Programada |

---

## Pregunta

En pacientes hospitalizados que reciben un anticoagulante, ¿**añadir un antiagregante** se asocia con
más sangrado y con peores desenlaces hospitalarios? El análisis se estratifica por la intensidad de la
anticoagulación (profiláctica vs. terapéutica). Detalle en [`docs/propuesta.md`](docs/propuesta.md).

## Resultados principales

**Hilo de la presentación** (exploratorio y post hoc; guion completo en
[`figuras/historia/HISTORIA.md`](figuras/historia/HISTORIA.md)):

1. **Casi la mitad cumple la definición de sangrado, pero pocos tienen una hemorragia documentada:** 11 de 38 eventos.
2. **Cuando está documentada, la fuente más común son los procedimientos:** 5 de 11.
3. **Las demás caídas de Hb no tienen una causa única:** se asocian con una Hb basal más alta y con más mediciones
   tempranas; cirugía y líquidos IV no son más frecuentes en quienes tienen evento.
4. **Con una definición más específica aparece una posible señal de la combinación:** RR 2.15 (IC 95 % 0.72–6.37).
   No es concluyente; es una hipótesis para probar en MIMIC-IV completo.
5. **Después de la caída de Hb no se observa beneficio ni daño claro de añadir el antiagregante** (7 desenlaces, todos con
   p de Holm = 1.0), pero el estudio no tiene potencia para descartarlo y no mide eventos trombóticos.

**Análisis principal, definido en la propuesta:**

- **Sangrado relevante:** 48 % con la combinación vs. 54 % con solo anticoagulante. RR crudo 0.90
  (IC 95 % 0.57–1.42); RR ajustado por intensidad (Mantel-Haenszel) 0.91 (0.59–1.40). Los datos son
  compatibles tanto con una reducción como con un aumento de alrededor del 40 %: **no permiten concluir
  que haya o no haya diferencia**.
- **Robustez:** la conclusión no cambia con otros umbrales de caída de Hb, otras ventanas de
  seguimiento, otras definiciones de la exposición, restricciones de población ni ajuste por cada
  confusor. La réplica sobre OMOP da RR 0.94 (0.59–1.47).
- **Plaquetas:** la combinación no se asoció con más caídas de plaquetas, coherente con la farmacología
  (los antiagregantes inhiben la función plaquetaria, no la cuenta).
- **Los grupos no son comparables al inicio:** la combinación reúne pacientes mayores y más cardiópatas;
  el comparador está más en UCI en la fecha índice. Los riesgos no deben leerse como efecto causal.

Tablas completas en [`resultados/resultados.md`](resultados/resultados.md). Figuras en PDF:

- [`figuras/principales/`](figuras/principales/INDICE.md): las 6 figuras de resultados (atrición,
  balance basal, desenlace principal, forest plot, trayectorias, réplica OMOP).
- [`figuras/analisis/`](figuras/analisis/INDICE.md): 20 análisis; cada uno contesta una pregunta, con
  su respuesta corta en el índice.

## Diseño

| Elemento | Definición |
|---|---|
| **Fuente** | MIMIC-IV Clinical Database Demo v2.2 (100 pacientes), en tablas nativas y en OMOP CDM 5.3.1 |
| **Población** | Adultos con estancia ≥ 24 h que reciben un anticoagulante (profiláctico o terapéutico); primera hospitalización elegible por paciente |
| **Exclusiones** | Diagnóstico principal de sangrado; sin plaquetas o Hb basales |
| **Grupo expuesto** | Anticoagulante **+ antiagregante** (aspirina o inhibidor P2Y12) con solapamiento temporal. Fecha índice: inicio del primer solapamiento |
| **Grupo comparador** | Anticoagulante **sin** antiagregante en toda la hospitalización. Fecha índice: inicio del anticoagulante |
| **Estratos** | Intensidad del anticoagulante en la fecha índice: profiláctica / terapéutica |
| **Basal** | Último valor en las 48 h previas a la fecha índice |
| **Seguimiento** | Desde la fecha índice hasta el alta o el día 14, lo que ocurra primero |

Cohorte final: **74 pacientes** (33 con la combinación, 41 con solo anticoagulante). Definición
completa y tabla de atrición en [`docs/cohorte.md`](docs/cohorte.md).

## Qué se mide

- **Desenlace principal, sangrado clínicamente relevante:** caída de Hb ≥ 2 g/dL respecto a la basal
  (umbral del criterio ISTH de sangrado mayor) **o** transfusión de concentrado eritrocitario.
- **Secundarios:** cada componente del principal; caída máxima de Hb; plaquetas (cambio al nadir,
  trombocitopenia nueva, caída ≥ 50 %); estancia desde la fecha índice; ingreso a UCI posterior;
  mortalidad hospitalaria.
- **Covariables (Tabla 1):** edad, sexo, estrato clínico, UCI en la fecha índice, fibrilación
  auricular, cardiopatía isquémica, tromboembolia venosa, insuficiencia cardiaca, plaquetas y Hb basales.
- **Análisis:** riesgos con IC 95 % (Wilson), diferencia y razón de riesgos, RR combinado de
  Mantel-Haenszel entre estratos, diferencias estandarizadas para el balance, Kaplan-Meier para el
  tiempo al sangrado.

Tipo, unidades y origen de cada variable: [diccionario de datos](docs/diccionario_datos.md).

## Limitaciones

- **Tamaño de muestra.** 74 pacientes (33 vs. 41). Los intervalos son anchos; los resultados son
  descriptivos y exploratorios, y ningún subgrupo tiene potencia para detectar interacción.
- **Confusión por indicación.** La combinación se da a pacientes mayores, con más cardiopatía
  isquémica y fibrilación auricular. Solo se ajusta por una variable a la vez (Mantel-Haenszel); con
  esta *n* no es posible un ajuste multivariable ni por puntaje de propensión.
- **Sesgo de vigilancia.** Al grupo con la combinación se le mide la Hb con menos frecuencia (74 % vs.
  85 % de los pacientes cada día; [P07](figuras/analisis/P07_vigilancia_hb.pdf)). Eso puede subdetectar
  sangrados en el grupo expuesto y sesgar el RR hacia 1 o por debajo.
- **Tiempo inmortal.** La fecha índice de la combinación ocurre más tarde respecto al ingreso (mediana
  11 vs. 6 h; [P03](figuras/analisis/P03_tiempo_a_indice.pdf)). La diferencia es pequeña, pero no se
  corrigió formalmente.
- **Medición del sangrado.** La caída de Hb también la producen la hemodilución y las flebotomías. La
  transfusión solo está registrada en UCI (`inputevents`). Un evento no medido cuenta como ausente.
- **Exposición por prescripción.** El análisis principal usa las órdenes (`prescriptions`). Con dosis
  realmente administradas (`emar`, disponible para 50 pacientes elegibles) la conclusión no cambia
  ([P20](figuras/analisis/P20_sensibilidad_emar.pdf)). Las órdenes sin fecha de término se asumen activas
  hasta el alta, y no se ven los antiagregantes tomados antes del ingreso.
- **Clasificación de fármacos.** En la versión nativa es por nombre, vía y dosis. En OMOP se usan
  listas de `concept_id` identificadas por cruce de NDC, porque el release no incluye los vocabularios
  estándar (sin `concept_ancestor`).
- **Diferencias de la versión OMOP.** No conserva el orden de los diagnósticos (no se puede excluir el
  sangrado como motivo de ingreso), no incluye transfusiones y el estrato quirúrgico sale de las
  unidades, no del servicio tratante (concordancia del 75 %). Ver [`docs/omop.md`](docs/omop.md).
- **Generalización.** Un solo centro de tercer nivel en EE. UU., con fechas desplazadas por
  desidentificación.

## Datos

Este repositorio **no contiene datos**. Para reproducir el trabajo:

1. Descarga *MIMIC-IV Clinical Database Demo* **v2.2** desde PhysioNet
   (<https://physionet.org/content/mimic-iv-demo/2.2/>). El acceso es abierto y la licencia es ODbL.
2. Descomprímelo en `data/raw/`, de modo que quede `data/raw/mimic-iv-clinical-database-demo-2.2/`.
3. Verifica la integridad con `sha256sum -c SHA256SUMS.txt` dentro de esa carpeta.
4. Para la versión OMOP, descarga *MIMIC-IV demo data in the OMOP Common Data Model* **v0.9**
   (<https://physionet.org/content/mimic-iv-demo-omop/0.9/>, acceso abierto, ODbL) y descomprímelo en
   `data/raw/omop/`, de modo que quede
   `data/raw/omop/mimic-iv-demo-data-in-the-omop-common-data-model-0.9/`. Verifica los checksums igual.

Ambos se descargaron el 2026-11-09.

## Entorno

### Opción A: Docker

Requiere Docker con Compose. Los datos no se copian a la imagen: se montan desde `./data`.

```bash
docker compose build
```

```bash
docker compose run --rm analisis
```

```bash
docker compose run --rm analisis pytest
```

### Opción B: entorno virtual local

```bash
python -m venv .venv
```

```bash
.venv/Scripts/python -m pip install -c constraints.txt -e ".[dev]"
```

[`constraints.txt`](constraints.txt) fija las versiones exactas con las que se desarrolló y probó el
proyecto (DuckDB 2.0, polars 2.1, matplotlib 3.11).

### Integración continua

En cada push, [GitHub Actions](.github/workflows/ci.yml) corre las pruebas en Python 3.12 y 3.13,
verifica que no se haya versionado ningún archivo de datos, construye la imagen Docker y repite las
pruebas dentro de ella. Las pruebas usan datos sintéticos, así que no requieren MIMIC.

## Cómo correrlo

Cada paso reconstruye la cohorte desde los CSV, así que se pueden correr en cualquier orden.

| Comando | Qué produce |
|---|---|
| `python -m antitromboticos.cohorte` | Cohorte nativa y [`resultados/atricion.csv`](resultados/atricion.csv) |
| `python -m antitromboticos.cohorte --fuente omop` | Cohorte OMOP y [`resultados/omop/atricion.csv`](resultados/omop/atricion.csv) |
| `python -m antitromboticos.analisis` | Tabla 1 y desenlaces: [`resultados/`](resultados) (`resultados.md`, CSV) |
| `python -m antitromboticos.analisis --fuente omop` | Lo mismo sobre OMOP: [`resultados/omop/`](resultados/omop) |
| `python -m antitromboticos.validacion_omop` | Comparación paciente por paciente nativa vs. OMOP |
| `python -m antitromboticos.figuras` | Figuras principales en PDF: [`figuras/principales/`](figuras/principales) |
| `python -m antitromboticos.preguntas` | 20 análisis en PDF, uno por pregunta: [`figuras/analisis/`](figuras/analisis) |
| `python -m antitromboticos.historia` | Causas del sangrado y desenlaces tras la caída de Hb, con pruebas formales: 15 figuras en PDF y [`figuras/historia/HISTORIA.md`](figuras/historia/HISTORIA.md) |
| `python -m antitromboticos.diccionario` | [`docs/diccionario_datos.md`](docs/diccionario_datos.md) con faltantes actualizados |
| `python -m pytest` | Pruebas (datos sintéticos, no requieren MIMIC) |

## Estructura

```
.github/workflows/    integración continua
Dockerfile, compose.yml, constraints.txt, pyproject.toml
sql/                  conjuntos de fármacos, cohorte y desenlaces sobre tablas nativas de MIMIC
sql/omop/             conjuntos de conceptos, cohorte y desenlaces sobre OMOP CDM
sql/historia/         causas del sangrado y desenlaces tras la caída de Hb
sql/sensibilidad/     exposición por dosis administradas (emar)
src/antitromboticos/  pipeline (cohorte, análisis, figuras, validación, diccionario)
tests/                pruebas con datos sintéticos
docs/                 propuesta, definición de cohorte, diccionario de datos, notas de OMOP
resultados/           tablas agregadas (sin datos individuales); resultados/omop/ para OMOP
figuras/principales/  6 figuras de resultados (PDF) + INDICE.md
figuras/analisis/     20 análisis, uno por pregunta (PDF) + INDICE.md
figuras/historia/     hilo narrativo sobre las causas del sangrado (PDF) + HISTORIA.md
figuras/              raíz: forest plots del análisis (PDF) y figuras de la exploración inicial (PNG)
notebooks/            exploración inicial (no es lógica de producción)
```

## Uso de asistentes de IA

Se usó **Claude Code (Anthropic)** como asistente durante todo el proyecto: para discutir y acotar la
pregunta, explorar los datos, escribir el SQL y el código de Python, las pruebas, la configuración de
Docker y CI, las figuras y la documentación.

Cómo se controló su uso:

- Cada cohorte y cada resultado se verificó contra los datos: conteos cruzados, validación paciente por
  paciente entre las versiones nativa y OMOP, y pruebas automatizadas sobre casos sintéticos con
  respuesta conocida.
- Los errores detectados durante la revisión (dosis únicas de aspirina perdidas, órdenes previas al
  ingreso, mortalidad nula en OMOP) quedaron corregidos y documentados en el historial de commits.
- Las decisiones de diseño (pregunta, definiciones, umbrales) y la interpretación de los resultados
  son responsabilidad del autor.
