# Definición de la cohorte

Implementada en:
- [`sql/01_conjuntos_farmacos.sql`](../sql/01_conjuntos_farmacos.sql): clasificación de antitrombóticos
- [`sql/02_cohorte.sql`](../sql/02_cohorte.sql): exposición, grupos, criterios y atrición
- [`sql/03_desenlaces.sql`](../sql/03_desenlaces.sql): desenlaces y covariables

Se ejecuta con `python -m antitromboticos.cohorte`. La lógica está cubierta por
[`tests/test_cohorte.py`](../tests/test_cohorte.py), que usa datos sintéticos.

Salidas: `data/processed/mimic/cohorte_analitica.parquet` (nivel individual, no se versiona) y
[`resultados/atricion.csv`](../resultados/atricion.csv). La versión sobre OMOP CDM está en
[docs/omop.md](omop.md), y el detalle de cada variable (tipo, unidades, origen, faltantes) en el
[diccionario de datos](diccionario_datos.md).

## Grupos

| Grupo | Definición | Fecha índice |
|---|---|---|
| `combinacion` | Anticoagulante y antiagregante **activos al mismo tiempo** | Inicio del primer solapamiento |
| `solo_anticoagulante` | Anticoagulante sin **ninguna** orden de antiagregante en la hospitalización | Inicio del primer anticoagulante |

Las hospitalizaciones con ambos fármacos pero sin solapamiento no son clasificables y se excluyen.
Estrato: intensidad del anticoagulante activo en la fecha índice (`profilactica` / `terapeutica`).

### Intervalos de exposición

| Regla | Valor | Por qué |
|---|---|---|
| Órdenes previas al ingreso | Se incluyen las iniciadas hasta 24 h antes; se recortan al ingreso | Órdenes de urgencias que continúan en la hospitalización |
| Orden sin fecha de término | Activa hasta el alta | |
| Antiagregantes | Efecto residual de **7 días** tras la última dosis | La inhibición plaquetaria de la aspirina y de los P2Y12 es irreversible y dura la vida de la plaqueta |
| Anticoagulante en dosis única | 24 h | `stoptime <= starttime` |
| Orden que inicia después del alta | Se descarta | Error de registro |

Todos los valores son parámetros (macros al inicio de `02_cohorte.sql`) para los análisis de sensibilidad.

## Criterios y atrición

| Paso | Criterio | Hospitalizaciones | Pacientes |
|---|---|---|---|
| 1 | Hospitalizaciones en MIMIC-IV Demo | 275 | 100 |
| 2 | Edad ≥ 18 años | 275 | 100 |
| 3 | Estancia ≥ 24 h | 245 | 100 |
| 4 | ≥ 1 anticoagulante en la hospitalización | 193 | 88 |
| 5 | Clasificable (combinación con solapamiento o sin antiagregante) | 193 | 88 |
| 6 | Diagnóstico principal distinto de sangrado | 184 | 82 |
| 7 | Plaquetas y Hb basales (48 h previas a la fecha índice) | 163 | 74 |
| 8 | Primera hospitalización elegible por paciente | 74 | 74 |

El paso 5 no excluye a nadie porque, con el efecto residual de 7 días, todas las hospitalizaciones que
reciben ambos fármacos tienen solapamiento. Se mantiene en la tabla porque deja de ser trivial si se
acorta ese efecto en un análisis de sensibilidad.

### Distribución final (74 pacientes)

| Grupo | Profiláctica | Terapéutica | Total |
|---|---|---|---|
| Combinación | 24 | 9 | 33 |
| Solo anticoagulante | 36 | 5 | 41 |

En la combinación predomina HNF + aspirina, seguida de warfarina + aspirina.

## Clasificación de los antitrombóticos

| Fármaco | Intensidad | Regla |
|---|---|---|
| Heparina no fraccionada (HNF) | Profiláctica | `Heparin` vía SC |
| | Terapéutica | `Heparin` / `Heparin Sodium` vía IV |
| Enoxaparina | Profiláctica / terapéutica | ≤ 40 mg / > 40 mg |
| Warfarina, apixabán, dabigatrán, rivaroxabán | Terapéutica | Excepto rivaroxabán ≤ 10 mg (profiláctica) |
| Aspirina, clopidogrel, ticagrelor, prasugrel | — | Antiagregante |

**Se excluyen:** heparina en flush, dwell, cebado de CRRT, hemodiálisis e IABP.

## Desenlaces (ventana: fecha índice → alta o día 14)

| Variable | Definición |
|---|---|
| `sangrado_relevante` (**principal**) | `caida_hb_2` **o** `transfusion_gr` |
| `caida_hb_2` | Nadir de Hb ≤ basal − 2 g/dL |
| `transfusion_gr` | Concentrado eritrocitario en `inputevents` (solo UCI) |
| `caida_hb_max` | Hb basal − nadir (g/dL) |
| `plaquetas_cambio_pct` | (nadir − basal) / basal × 100 |
| `trombocitopenia_nueva` | Nadir < 100 con basal ≥ 150 (nulo si la basal es < 150) |
| `plaquetas_caida_50` | Nadir ≤ 50 % de la basal |
| `estancia_post_indice_dias` | Días desde la fecha índice al alta |
| `uci_posterior` | Ingreso a UCI después de la fecha índice, dentro del seguimiento |
| `muerte` | Muerte hospitalaria |

Si un paciente no tiene laboratorios en el seguimiento, el evento de laboratorio se cuenta como
**ausente**. `n_hb` y `n_plaquetas` permiten revisar a quién le faltan mediciones.

## Covariables

`edad`, `sexo`, `estrato` (servicio: `cirugia_cardiaca` CSURG > `quirurgico` > `medico`),
`uci_en_indice`, y las indicaciones a partir de la CIE de la misma hospitalización:
`fibrilacion_auricular`, `cardiopatia_isquemica`, `tromboembolia_venosa`, `insuficiencia_cardiaca`.

## Limitaciones conocidas

- La clasificación de fármacos es por nombre. En OMOP se hará con RxNorm/ATC.
- La exposición se define por prescripción; la administración real (`emar`) queda como análisis de sensibilidad.
- No se ven los antiagregantes tomados antes del ingreso. Un paciente del grupo "solo anticoagulante"
  podría tener efecto residual de aspirina tomada en casa.
- La transfusión solo se registra en UCI.
- El estrato quirúrgico se define por servicio, no por la fecha de la cirugía.
