# Cohorte sobre OMOP CDM

La cohorte está implementada dos veces con la misma definición:

| | Nativa | OMOP |
|---|---|---|
| Datos | MIMIC-IV Clinical Database Demo v2.2 | MIMIC-IV demo data in the OMOP CDM v0.9 (CDM 5.3.1) |
| SQL | [`sql/`](../sql) | [`sql/omop/`](../sql/omop) |
| Ejecución | `python -m antitromboticos.cohorte` | `python -m antitromboticos.cohorte --fuente omop` |
| Resultados | [`resultados/`](../resultados) | [`resultados/omop/`](../resultados/omop) |

La versión OMOP cumple el requisito del curso (cohorte en SQL sobre OMOP). La nativa se conserva porque
tiene información que el release de OMOP no incluye (transfusiones, orden de los diagnósticos, servicio
tratante) y sirve para validar.

## Datos

- **Dataset:** *MIMIC-IV demo data in the OMOP Common Data Model*, versión 0.9 (21 de junio de 2021),
  PhysioNet, licencia ODbL, acceso abierto. <https://physionet.org/content/mimic-iv-demo-omop/0.9/>
- **Descargado:** 2026-11-09. ZIP de 10.3 MB; checksums `SHA256SUMS.txt` verificados.
- **Ubicación esperada:** `data/raw/omop/mimic-iv-demo-data-in-the-omop-common-data-model-0.9/1_omop_data_csv/`
- **Tablas usadas:** `person`, `visit_occurrence`, `visit_detail`, `care_site`, `drug_exposure`,
  `measurement`, `condition_occurrence`, `death`.
- Las 275 hospitalizaciones del demo v2.2 están en `visit_occurrence` con las mismas fechas desplazadas.

## Conjuntos de conceptos

El release **no incluye los vocabularios estándar** (solo los conceptos locales > 2B), así que no hay
`concept` ni `concept_ancestor` para RxNorm/ATC. Los conjuntos se definieron como **listas explícitas de
`concept_id`** en [`sql/omop/01_conjuntos_conceptos.sql`](../sql/omop/01_conjuntos_conceptos.sql):

1. Se cruzó `drug_exposure.drug_source_value` (código NDC) con `prescriptions.ndc` de MIMIC-IV Demo v2.2
   para obtener el nombre del fármaco de cada `drug_concept_id`.
2. Se seleccionaron los conceptos de heparina, enoxaparina, warfarina, DOAC, aspirina y P2Y12, y se
   excluyeron los de flush, dwell, hemodiálisis e IABP.
3. La intensidad se asigna por concepto. En la heparina no fraccionada (un solo concepto para SC e IV) se
   asigna por la vía (`route_source_value`).

Mediciones: hemoglobina = **3000963**, plaquetas = **3024929** (LOINC estándar, ya mapeadas en el release).

**Siguiente mejora:** descargar de [Athena](https://athena.ohdsi.org) los vocabularios RxNorm, RxNorm
Extension, ATC, LOINC, SNOMED, ICD9CM e ICD10CM. Con ellos, las listas se reemplazan por
`concept_ancestor` (descendientes de los ingredientes o de las clases ATC B01AA, B01AB, B01AC, B01AE, B01AF)
y las indicaciones pasan de códigos CIE a conceptos SNOMED.

## Diferencias con la versión nativa

| Aspecto | Nativa | OMOP | Consecuencia |
|---|---|---|---|
| Hospitalizaciones | `admissions` (275) | `visit_occurrence` con concepto hospitalario (270) | 5 hospitalizaciones codificadas como visita ambulatoria quedan fuera |
| Diagnóstico principal | `diagnoses_icd.seq_num = 1` | No disponible (`condition_status_concept_id` vacío) | No se puede excluir el sangrado como motivo de ingreso |
| Transfusión | `inputevents` | No incorporado en el release | El desenlace principal se reduce a la caída de Hb ≥ 2 g/dL |
| Estrato clínico | Servicio tratante (`services`) | Unidades físicas (`visit_detail` + `care_site`) | Concordancia del 75 % (ver abajo) |
| Indicaciones | `diagnoses_icd` | `condition_source_value` (CIE) | Equivalente |
| Enoxaparina | Dosis prescrita | Concepto de la presentación | El concepto 40160974 incluye algunas dosis de 80 mg |

## Validación

[`resultados/omop/validacion.md`](../resultados/omop/validacion.md), generado con
`python -m antitromboticos.validacion_omop`:

- Los **74** pacientes de la cohorte nativa están todos en la cohorte OMOP. Los **6** pacientes
  adicionales de OMOP son exactamente los que la versión nativa excluye por diagnóstico principal de sangrado.
- En los 71 pacientes con la misma hospitalización índice, la concordancia es de **100 %** en grupo de
  exposición y mortalidad, **99 %** en intensidad y caída de Hb, **97 %** en fecha índice y **96 %** en
  ingreso posterior a UCI.
- El **estrato** concuerda en el **75 %**: las unidades físicas no equivalen al servicio tratante (por
  ejemplo, pacientes médicos alojados en una UCI quirúrgica).
- Resultado principal: RR de Mantel-Haenszel **0.94 (0.59–1.47)** en OMOP vs. **0.91 (0.59–1.40)** en la
  versión nativa.
