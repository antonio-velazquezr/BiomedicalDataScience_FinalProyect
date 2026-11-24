"""Sensibilidad: exposición por prescripción vs. dosis realmente administradas (emar).

``emar`` no cubre todas las hospitalizaciones, así que se comparan tres cohortes:

1. principal: todas las hospitalizaciones, exposición por prescripción;
2. cobertura emar: solo hospitalizaciones con emar, exposición por prescripción;
3. administrada: solo hospitalizaciones con emar, exposición por dosis administradas.

La diferencia 1 → 2 refleja la pérdida de pacientes; la diferencia 2 → 3, el cambio de exposición.
"""

from __future__ import annotations

import duckdb
import polars as pl

from antitromboticos.cohorte import FUENTES, SQL_DIR, cargar_tablas, ejecutar_sql
from antitromboticos.figuras import tabla

VARIANTES = {
    "principal": (False, False),
    "cobertura_emar": (True, False),
    "administrada": (True, True),
}


def conexion_variante(restringir: bool, administrada: bool) -> duckdb.DuckDBPyConnection:
    f = FUENTES["mimic"]
    datos = f.datos.as_posix()
    con = duckdb.connect()
    cargar_tablas(con, f)
    for t in ("procedures_icd", "d_icd_procedures", "d_icd_diagnoses"):
        con.execute(f"CREATE OR REPLACE VIEW {t} AS SELECT * FROM read_csv('{datos}/hosp/{t}.csv.gz', "
                    "sample_size = -1, types = {'icd_code': 'VARCHAR'})")
    con.execute(f"CREATE OR REPLACE VIEW emar AS SELECT * FROM read_csv('{datos}/hosp/emar.csv.gz', sample_size = -1)")
    if restringir:
        con.execute(f"CREATE OR REPLACE VIEW admissions_fuente AS SELECT * FROM read_csv('{datos}/hosp/admissions.csv.gz', "
                    "sample_size = -1)")
        con.execute((SQL_DIR / "sensibilidad" / "01_cobertura_emar.sql").read_text(encoding="utf-8"))
    if administrada:
        con.execute(f"CREATE OR REPLACE VIEW prescriptions_fuente AS SELECT * FROM read_csv('{datos}/hosp/prescriptions.csv.gz', "
                    "sample_size = -1)")
        con.execute((SQL_DIR / "sensibilidad" / "02_exposicion_administrada.sql").read_text(encoding="utf-8"))
    ejecutar_sql(con, SQL_DIR)
    con.execute((SQL_DIR / "historia" / "01_causas_sangrado.sql").read_text(encoding="utf-8"))
    return con


def cohortes() -> dict[str, pl.DataFrame]:
    return {n: tabla(conexion_variante(r, a), "SELECT * FROM causas") for n, (r, a) in VARIANTES.items()}


def concordancia_grupo(prescripcion: pl.DataFrame, administrada: pl.DataFrame) -> tuple[int, int]:
    """(iguales, total) de grupo de exposición entre pacientes con la misma hospitalización índice."""
    d = prescripcion.select("hadm_id", "grupo").join(administrada.select("hadm_id", pl.col("grupo").alias("g2")), on="hadm_id")
    return d.filter(pl.col("grupo") == pl.col("g2")).height, d.height
