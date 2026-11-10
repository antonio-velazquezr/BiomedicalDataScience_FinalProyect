"""Diccionario de datos de la cohorte analítica.

Los metadatos de cada variable viven aquí, en un solo lugar. El script genera
``docs/diccionario_datos.md`` y, si existen las cohortes procesadas, agrega el porcentaje de
valores faltantes por fuente. También verifica que **toda** columna de la cohorte esté documentada:
si alguien agrega una variable al SQL sin documentarla, el script (y la prueba) fallan.

Uso::

    python -m antitromboticos.diccionario
"""

from __future__ import annotations

from dataclasses import dataclass

import duckdb

from antitromboticos.cohorte import FUENTES, RAIZ

DESTINO = RAIZ / "docs" / "diccionario_datos.md"

# Fuentes de laboratorio y tablas, citadas en `origen`
HB = "Hb: `labevents.itemid` 51222 · OMOP `measurement_concept_id` 3000963 (LOINC 718-7)"
PLAQ = "Plaquetas: `labevents.itemid` 51265 · OMOP `measurement_concept_id` 3024929 (LOINC 777-3)"


@dataclass(frozen=True)
class Variable:
    nombre: str
    dominio: str
    descripcion: str
    tipo: str
    unidades: str = "—"
    valores: str = "—"
    origen: str = "—"
    solo: str | None = None  # "mimic" / "omop" si la columna existe solo en una fuente


VARIABLES: list[Variable] = [
    # --- Identificadores
    Variable("subject_id", "Identificadores", "Identificador del paciente en MIMIC-IV", "entero",
             origen="`admissions.subject_id`", solo="mimic"),
    Variable("hadm_id", "Identificadores", "Identificador de la hospitalización índice", "entero",
             origen="`admissions.hadm_id`", solo="mimic"),
    Variable("person_id", "Identificadores", "Identificador del paciente en OMOP", "entero",
             origen="`person.person_id`", solo="omop"),
    Variable("visit_occurrence_id", "Identificadores", "Identificador de la hospitalización índice en OMOP", "entero",
             origen="`visit_occurrence.visit_occurrence_id`", solo="omop"),
    Variable("subject_id_fuente", "Identificadores", "`subject_id` de MIMIC del paciente (para validar contra la versión nativa)",
             "entero", origen="`person.person_source_value`", solo="omop"),
    Variable("visita_fuente", "Identificadores", "Valor de origen de la visita, `subject_id|hadm_id`", "texto",
             origen="`visit_occurrence.visit_source_value`", solo="omop"),

    # --- Exposición
    Variable("grupo", "Exposición", "Grupo de exposición", "categórica",
             valores="`combinacion` = anticoagulante + antiagregante con solapamiento temporal; "
                     "`solo_anticoagulante` = anticoagulante sin ninguna orden de antiagregante en la hospitalización",
             origen="Derivada de `prescriptions` / `drug_exposure` (ver docs/cohorte.md)"),
    Variable("intensidad", "Exposición", "Intensidad del anticoagulante activo en la fecha índice (estrato del análisis)",
             "categórica", valores="`profilactica`, `terapeutica`",
             origen="Fármaco, vía y dosis (nativa) o concepto y vía (OMOP)"),
    Variable("anticoagulante", "Exposición", "Anticoagulante activo en la fecha índice", "categórica",
             valores="`HNF` (heparina no fraccionada), `enoxaparina`, `warfarina`, `DOAC`"),
    Variable("antiagregante", "Exposición", "Antiagregante del primer solapamiento (nulo en `solo_anticoagulante`)",
             "categórica", valores="`aspirina`, `P2Y12` (clopidogrel, prasugrel, ticagrelor)"),
    Variable("t_indice", "Exposición", "Fecha índice: inicio del primer solapamiento (combinación) o del primer anticoagulante (comparador)",
             "fecha-hora", origen="Fechas desplazadas de MIMIC (años 2100+); los intervalos son reales"),
    Variable("t_fin_seguimiento", "Exposición", "Fin del seguimiento: el alta o el día 14 desde la fecha índice, lo que ocurra primero",
             "fecha-hora"),
    Variable("dias_seguimiento", "Exposición", "Duración del seguimiento", "decimal", unidades="días"),

    # --- Demografía y hospitalización
    Variable("sexo", "Demografía", "Sexo registrado", "categórica", valores="`F`, `M`",
             origen="`patients.gender` · OMOP `person.gender_concept_id` (8532 = F, 8507 = M)"),
    Variable("edad", "Demografía", "Edad al ingreso", "entero", unidades="años",
             valores="18–91 (MIMIC agrupa a los mayores de 89 en 91)",
             origen="`anchor_age` + (año de ingreso − `anchor_year`) · OMOP: año de ingreso − `year_of_birth`"),
    Variable("admittime", "Hospitalización", "Ingreso hospitalario", "fecha-hora",
             origen="`admissions.admittime` · OMOP `visit_start_datetime`"),
    Variable("dischtime", "Hospitalización", "Alta hospitalaria", "fecha-hora",
             origen="`admissions.dischtime` · OMOP `visit_end_datetime`"),
    Variable("muerte_hospitalaria", "Hospitalización", "Muerte durante la hospitalización (variable de origen)",
             "entero 0/1 (nativa) · booleana (OMOP)",
             origen="`admissions.hospital_expire_flag` · OMOP `discharge_to_concept_id` = 4216643 o `death` durante la visita"),
    Variable("estrato", "Hospitalización", "Estrato clínico de la hospitalización", "categórica",
             valores="`cirugia_cardiaca`, `quirurgico`, `medico`",
             origen="Nativa: servicio tratante (`services`: CSURG > SURG/NSURG/VSURG/TRAUM/ORTHO/TSURG/GYN…). "
                    "OMOP: unidades de `visit_detail` + `care_site` (concordancia del 75 % con la nativa)"),
    Variable("uci_en_indice", "Hospitalización", "En UCI en la fecha índice", "booleana",
             origen="`icustays` · OMOP `visit_detail` en unidades de cuidados intensivos"),

    # --- Indicaciones
    Variable("fibrilacion_auricular", "Indicaciones", "Fibrilación o flutter auricular en la hospitalización", "booleana",
             valores="CIE-9 427.31, 427.32 · CIE-10 I48", origen="`diagnoses_icd` · OMOP `condition_source_value`"),
    Variable("cardiopatia_isquemica", "Indicaciones", "Cardiopatía isquémica en la hospitalización", "booleana",
             valores="CIE-9 410–414 · CIE-10 I20–I25", origen="`diagnoses_icd` · OMOP `condition_source_value`"),
    Variable("tromboembolia_venosa", "Indicaciones", "Trombosis venosa profunda o tromboembolia pulmonar en la hospitalización",
             "booleana", valores="CIE-9 415.1, 453.4–453.9 · CIE-10 I26, I82.4, I82.5, I82.9",
             origen="`diagnoses_icd` · OMOP `condition_source_value`"),
    Variable("insuficiencia_cardiaca", "Indicaciones", "Insuficiencia cardiaca en la hospitalización", "booleana",
             valores="CIE-9 428 · CIE-10 I50", origen="`diagnoses_icd` · OMOP `condition_source_value`"),

    # --- Laboratorio basal
    Variable("hb_basal", "Laboratorio basal", "Último valor de hemoglobina en las 48 h previas a la fecha índice",
             "decimal", unidades="g/dL", origen=HB),
    Variable("plaquetas_basal", "Laboratorio basal", "Último valor de plaquetas en las 48 h previas a la fecha índice",
             "decimal", unidades="× 10⁹/L (K/µL)", origen=PLAQ),

    # --- Desenlaces de sangrado
    Variable("sangrado_relevante", "Desenlace: sangrado", "**Desenlace principal.** `caida_hb_2` o `transfusion_gr`",
             "booleana", origen="En OMOP equivale a `caida_hb_2` (no hay transfusiones)"),
    Variable("caida_hb_2", "Desenlace: sangrado", "Nadir de Hb en el seguimiento ≤ basal − 2 g/dL (umbral ISTH)",
             "booleana", origen=HB),
    Variable("transfusion_gr", "Desenlace: sangrado", "Transfusión de concentrado eritrocitario en el seguimiento",
             "booleana", valores="Nulo en OMOP (no disponible)",
             origen="`inputevents` con `d_items.label` ~ 'Packed' (solo UCI)"),
    Variable("hb_nadir", "Desenlace: sangrado", "Valor mínimo de Hb en el seguimiento", "decimal", unidades="g/dL", origen=HB),
    Variable("caida_hb_max", "Desenlace: sangrado", "Caída máxima de Hb: basal − nadir (negativo si subió)", "decimal",
             unidades="g/dL"),
    Variable("n_hb", "Desenlace: sangrado", "Número de mediciones de Hb en el seguimiento (nulo si ninguna)", "entero"),

    # --- Desenlaces plaquetarios
    Variable("plaquetas_nadir", "Desenlace: plaquetas", "Valor mínimo de plaquetas en el seguimiento", "decimal",
             unidades="× 10⁹/L", origen=PLAQ),
    Variable("plaquetas_cambio_pct", "Desenlace: plaquetas", "Cambio porcentual de la basal al nadir", "decimal",
             unidades="%"),
    Variable("trombocitopenia_nueva", "Desenlace: plaquetas", "Nadir < 100 con basal ≥ 150 × 10⁹/L",
             "booleana", valores="Nulo si la basal es < 150 (no aplica)"),
    Variable("plaquetas_caida_50", "Desenlace: plaquetas", "Nadir ≤ 50 % de la basal", "booleana"),
    Variable("n_plaquetas", "Desenlace: plaquetas", "Número de mediciones de plaquetas en el seguimiento (nulo si ninguna)",
             "entero"),

    # --- Desenlaces hospitalarios
    Variable("estancia_post_indice_dias", "Desenlace: hospitalario", "Días desde la fecha índice hasta el alta", "decimal",
             unidades="días"),
    Variable("uci_posterior", "Desenlace: hospitalario", "Ingreso a UCI después de la fecha índice, dentro del seguimiento",
             "booleana"),
    Variable("muerte", "Desenlace: hospitalario", "Muerte hospitalaria (versión booleana de `muerte_hospitalaria`)",
             "booleana"),
]


def columnas_documentadas(fuente: str) -> set[str]:
    return {v.nombre for v in VARIABLES if v.solo in (None, fuente)}


def faltantes(fuente: str) -> tuple[int, dict[str, float]] | None:
    """(n, {columna: % de nulos}) de la cohorte procesada, o None si no se ha generado."""
    ruta = FUENTES[fuente].procesados / "cohorte_analitica.parquet"
    if not ruta.exists():
        return None
    rel = duckdb.sql(f"SELECT * FROM read_parquet('{ruta.as_posix()}')")
    columnas = rel.columns
    n = duckdb.sql(f"SELECT count(*) FROM read_parquet('{ruta.as_posix()}')").fetchall()[0][0]
    exprs = ", ".join(f'100.0 * count(*) FILTER (WHERE "{c}" IS NULL) / count(*)' for c in columnas)
    valores = duckdb.sql(f"SELECT {exprs} FROM read_parquet('{ruta.as_posix()}')").fetchall()[0]
    return n, dict(zip(columnas, valores))


def verificar_cobertura(fuente: str, columnas: list[str]) -> None:
    """Falla si la cohorte tiene columnas sin documentar o si el diccionario documenta columnas inexistentes."""
    doc = columnas_documentadas(fuente)
    sin_doc = set(columnas) - doc
    sobrantes = doc - set(columnas)
    if sin_doc or sobrantes:
        raise ValueError(f"[{fuente}] sin documentar: {sorted(sin_doc)} · documentadas pero inexistentes: {sorted(sobrantes)}")


def generar() -> str:
    datos = {f: faltantes(f) for f in FUENTES}
    for f, d in datos.items():
        if d is not None:
            verificar_cobertura(f, list(d[1]))

    def pct(fuente: str, col: str) -> str:
        d = datos[fuente]
        if d is None:
            return "?"
        if col not in d[1]:
            return "n/a"
        return f"{d[1][col]:.0f} %"

    partes = [
        "# Diccionario de datos",
        "Variables de la **cohorte analítica** (`cohorte_analitica`): un renglón por paciente, en su primera "
        "hospitalización elegible. La misma estructura se produce desde las tablas nativas de MIMIC-IV "
        "(`sql/`) y desde OMOP CDM (`sql/omop/`); las diferencias se marcan en la columna *Origen*.",
        "Generado por `python -m antitromboticos.diccionario` a partir de "
        "[`src/antitromboticos/diccionario.py`](../src/antitromboticos/diccionario.py). "
        "La prueba `tests/test_diccionario.py` falla si alguna columna queda sin documentar.",
        "**% faltante:** porcentaje de pacientes con valor nulo en cada fuente "
        + ", ".join(f"({f}: n = {d[0]})" for f, d in datos.items() if d is not None)
        + ". *n/a* = la columna no existe en esa fuente.",
        "**Fechas:** MIMIC desplaza todas las fechas de cada paciente al futuro (años 2100+) para desidentificar; "
        "los intervalos entre fechas son reales.",
    ]
    for dominio in dict.fromkeys(v.dominio for v in VARIABLES):
        filas = [
            "| Variable | Descripción | Tipo | Unidades | Valores | Origen | % faltante (mimic / omop) |",
            "|---|---|---|---|---|---|---|",
        ]
        for v in (v for v in VARIABLES if v.dominio == dominio):
            filas.append(
                f"| `{v.nombre}` | {v.descripcion} | {v.tipo} | {v.unidades} | {v.valores} | {v.origen} | "
                f"{pct('mimic', v.nombre)} / {pct('omop', v.nombre)} |"
            )
        partes += [f"## {dominio}", "\n".join(filas)]

    partes += [
        "## Valores faltantes: cómo se tratan",
        "- `hb_nadir`, `plaquetas_nadir` y los `n_*` son nulos cuando no hubo mediciones en el seguimiento. "
        "En ese caso, los desenlaces booleanos de laboratorio (`caida_hb_2`, `plaquetas_caida_50`) se codifican "
        "como `false`: un evento no medido se cuenta como ausente (puede subestimar el riesgo).",
        "- `trombocitopenia_nueva` es nula por diseño cuando la basal es < 150 × 10⁹/L.",
        "- `transfusion_gr` es nula en OMOP porque el release no incluye `inputevents`; el análisis la omite.",
        "- `antiagregante` es nulo en el grupo `solo_anticoagulante` por definición.",
    ]
    return "\n\n".join(partes) + "\n"


def main() -> None:
    DESTINO.write_text(generar(), encoding="utf-8")
    print(f"Escrito {DESTINO.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
