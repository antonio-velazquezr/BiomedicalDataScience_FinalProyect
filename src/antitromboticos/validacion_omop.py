"""Valida la cohorte OMOP contra la cohorte nativa de MIMIC, paciente por paciente.

Ambas fuentes son los mismos 100 pacientes del demo (las fechas desplazadas coinciden), así que la
cohorte debería ser casi idéntica. Las diferencias esperadas son las que obliga OMOP (ver docs/omop.md).

Escribe ``resultados/omop/validacion.md`` (solo conteos agregados).

Uso::

    python -m antitromboticos.validacion_omop
"""

from __future__ import annotations

import duckdb

from antitromboticos.cohorte import FUENTES, construir


def comparar() -> duckdb.DuckDBPyConnection:
    """Construye ambas cohortes y devuelve una conexión con la tabla `comparacion`."""
    nativa = construir("mimic")
    omop = construir("omop")
    con = duckdb.connect()
    # Pasar las tablas entre conexiones sin depender de pandas/pyarrow: exportar a parquet temporal
    dest = FUENTES["omop"].procesados
    dest.mkdir(parents=True, exist_ok=True)
    rutas = {}
    for nombre, c in (("nativa", nativa), ("omop", omop)):
        ruta = (dest / f"_validacion_{nombre}.parquet").as_posix()
        c.execute(f"COPY cohorte_analitica TO '{ruta}' (FORMAT parquet)")
        rutas[nombre] = ruta
    con.execute(f"CREATE TABLE nativa AS SELECT * FROM read_parquet('{rutas['nativa']}')")
    con.execute(f"CREATE TABLE omop AS SELECT * FROM read_parquet('{rutas['omop']}')")
    # Atrición de la versión nativa, para saber quién se excluyó por diagnóstico principal de sangrado
    excl = (dest / "_validacion_excluidos.parquet").as_posix()
    nativa.execute(f"""COPY (SELECT DISTINCT subject_id FROM elegibilidad
                     WHERE c_adulto AND c_estancia AND c_anticoagulante AND c_clasificable
                       AND NOT c_sin_sangrado_principal) TO '{excl}' (FORMAT parquet)""")
    con.execute(f"CREATE TABLE excluidos_sangrado AS SELECT * FROM read_parquet('{excl}')")

    con.execute("""
        CREATE TABLE comparacion AS
        SELECT
            coalesce(n.subject_id, TRY_CAST(o.subject_id_fuente AS BIGINT)) AS subject_id,
            n.subject_id IS NOT NULL AS en_nativa,
            o.subject_id_fuente IS NOT NULL AS en_omop,
            n.hadm_id = TRY_CAST(split_part(o.visita_fuente, '|', 2) AS BIGINT) AS misma_hosp,
            n.grupo AS grupo_n, o.grupo AS grupo_o,
            n.intensidad AS int_n, o.intensidad AS int_o,
            n.estrato AS estrato_n, o.estrato AS estrato_o,
            n.t_indice = o.t_indice AS mismo_indice,
            n.caida_hb_2 AS hb_n, o.caida_hb_2 AS hb_o,
            n.uci_posterior AS uci_n, o.uci_posterior AS uci_o,
            n.muerte AS muerte_n, o.muerte AS muerte_o,
            EXISTS (SELECT 1 FROM excluidos_sangrado e
                    WHERE e.subject_id = TRY_CAST(o.subject_id_fuente AS BIGINT)) AS excluido_por_sangrado_en_nativa
        FROM nativa n
        FULL OUTER JOIN omop o ON n.subject_id = TRY_CAST(o.subject_id_fuente AS BIGINT)
    """)
    return con


def concordancia(con: duckdb.DuckDBPyConnection, a: str, b: str) -> str:
    total, iguales = con.execute(
        f"SELECT count(*), count(*) FILTER (WHERE {a} IS NOT DISTINCT FROM {b}) "
        "FROM comparacion WHERE en_nativa AND en_omop AND misma_hosp"
    ).fetchall()[0]
    return f"{iguales}/{total} ({100 * iguales / total:.0f} %)" if total else "—"


def main() -> None:
    con = comparar()
    q = lambda s: con.execute(s).fetchall()[0][0]  # noqa: E731
    ambos = q("SELECT count(*) FROM comparacion WHERE en_nativa AND en_omop")
    solo_n = q("SELECT count(*) FROM comparacion WHERE en_nativa AND NOT en_omop")
    solo_o = q("SELECT count(*) FROM comparacion WHERE en_omop AND NOT en_nativa")
    solo_o_expl = q("SELECT count(*) FROM comparacion WHERE en_omop AND NOT en_nativa AND excluido_por_sangrado_en_nativa")
    misma = q("SELECT count(*) FROM comparacion WHERE en_nativa AND en_omop AND misma_hosp")

    filas = [
        ("Grupo de exposición", "grupo_n", "grupo_o"),
        ("Intensidad", "int_n", "int_o"),
        ("Fecha índice", "mismo_indice", "true"),
        ("Estrato (servicio vs. unidades)", "estrato_n", "estrato_o"),
        ("Caída de Hb ≥ 2 g/dL", "hb_n", "hb_o"),
        ("UCI posterior", "uci_n", "uci_o"),
        ("Muerte hospitalaria", "muerte_n", "muerte_o"),
    ]
    tabla = "\n".join(f"| {nombre} | {concordancia(con, a, b)} |" for nombre, a, b in filas)
    estratos = con.sql("""
        SELECT estrato_n, estrato_o, count(*) n FROM comparacion
        WHERE en_nativa AND en_omop AND misma_hosp AND estrato_n IS DISTINCT FROM estrato_o
        GROUP BY ALL ORDER BY n DESC""").fetchall()
    discordancias = "\n".join(f"| {a} | {b} | {n} |" for a, b, n in estratos) or "| — | — | 0 |"

    reporte = f"""# Validación: cohorte OMOP vs. cohorte nativa

Generado por `python -m antitromboticos.validacion_omop`. Compara paciente por paciente la cohorte
construida sobre OMOP CDM (`sql/omop/`) con la construida sobre las tablas nativas de MIMIC (`sql/`).

## Pertenencia a la cohorte

| | Pacientes |
|---|---|
| En ambas cohortes | {ambos} |
| Solo en la nativa | {solo_n} |
| Solo en OMOP | {solo_o} |
| … de ellos, excluidos en la nativa por diagnóstico principal de sangrado | {solo_o_expl} |
| En ambas, con la misma hospitalización índice | {misma} |

## Concordancia de variables (pacientes en ambas, misma hospitalización)

| Variable | Concordancia |
|---|---|
{tabla}

## Discordancias de estrato

| Nativa (servicio) | OMOP (unidades) | Pacientes |
|---|---|---|
{discordancias}
"""
    destino = FUENTES["omop"].resultados
    destino.mkdir(parents=True, exist_ok=True)
    (destino / "validacion.md").write_text(reporte, encoding="utf-8")
    print(reporte)


if __name__ == "__main__":
    main()
