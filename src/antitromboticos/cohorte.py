"""Construye la cohorte anticoagulante + antiagregante vs. solo anticoagulante.

Carga las tablas de MIMIC-IV Demo en DuckDB, ejecuta los scripts de `sql/` en orden y exporta:

* ``data/processed/cohorte_analitica.parquet``: un renglón por paciente (nivel individual, no se versiona)
* ``resultados/atricion.csv``: tabla de atrición (agregada, sí se versiona)

Uso::

    python -m antitromboticos.cohorte
    python -m antitromboticos.cohorte --datos ruta/a/mimic-iv-clinical-database-demo-2.2
"""

from __future__ import annotations

import argparse
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[2]
DATOS_DEFAULT = RAIZ / "data" / "raw" / "mimic-iv-clinical-database-demo-2.2"
SQL_DIR = RAIZ / "sql"
SALIDA_PROCESADOS = RAIZ / "data" / "processed"
SALIDA_RESULTADOS = RAIZ / "resultados"

# tabla -> módulo de MIMIC donde vive
TABLAS = {
    "patients": "hosp",
    "admissions": "hosp",
    "prescriptions": "hosp",
    "labevents": "hosp",
    "services": "hosp",
    "diagnoses_icd": "hosp",
    "icustays": "icu",
    "inputevents": "icu",
    "d_items": "icu",
}


def cargar_tablas(con: duckdb.DuckDBPyConnection, datos: Path) -> None:
    """Registra cada CSV comprimido de MIMIC como una vista de DuckDB."""
    for tabla, modulo in TABLAS.items():
        ruta = datos / modulo / f"{tabla}.csv.gz"
        if not ruta.exists():
            raise FileNotFoundError(f"No se encontró {ruta}. Revisa el README para descargar los datos.")
        con.execute(
            f"CREATE OR REPLACE VIEW {tabla} AS "
            f"SELECT * FROM read_csv('{ruta.as_posix()}', sample_size = -1)"
        )


def ejecutar_sql(con: duckdb.DuckDBPyConnection, sql_dir: Path = SQL_DIR) -> None:
    """Ejecuta los scripts .sql en orden alfabético (01_, 02_, ...)."""
    for script in sorted(sql_dir.glob("*.sql")):
        con.execute(script.read_text(encoding="utf-8"))


def construir(datos: Path = DATOS_DEFAULT) -> duckdb.DuckDBPyConnection:
    """Construye la cohorte y devuelve la conexión con las tablas creadas."""
    con = duckdb.connect()
    cargar_tablas(con, datos)
    ejecutar_sql(con)
    return con


def exportar(con: duckdb.DuckDBPyConnection) -> None:
    SALIDA_PROCESADOS.mkdir(parents=True, exist_ok=True)
    SALIDA_RESULTADOS.mkdir(parents=True, exist_ok=True)
    destino = (SALIDA_PROCESADOS / "cohorte_analitica.parquet").as_posix()
    con.execute(f"COPY cohorte_analitica TO '{destino}' (FORMAT parquet)")
    con.execute(f"COPY atricion TO '{(SALIDA_RESULTADOS / 'atricion.csv').as_posix()}' (HEADER)")


def resumen(con: duckdb.DuckDBPyConnection) -> None:
    print("\nTabla de atrición")
    print(con.sql("SELECT * FROM atricion"))
    print("Grupos por intensidad del anticoagulante")
    print(con.sql("""
        PIVOT (SELECT grupo, intensidad FROM cohorte_analitica)
        ON intensidad USING count(*) GROUP BY grupo ORDER BY grupo
    """))
    print("Desenlaces por grupo (n con el evento)")
    print(con.sql("""
        SELECT grupo,
               count(*)                                 AS n,
               count(*) FILTER (WHERE sangrado_relevante) AS sangrado_relevante,
               count(*) FILTER (WHERE caida_hb_2)         AS caida_hb_2,
               count(*) FILTER (WHERE transfusion_gr)     AS transfusion,
               count(*) FILTER (WHERE trombocitopenia_nueva) AS tromb_nueva,
               count(*) FILTER (WHERE plaquetas_caida_50) AS plaq_caida_50,
               count(*) FILTER (WHERE uci_posterior)      AS uci_posterior,
               count(*) FILTER (WHERE muerte)             AS muerte,
               round(median(estancia_post_indice_dias), 1) AS estancia_mediana
        FROM cohorte_analitica GROUP BY grupo ORDER BY grupo
    """))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--datos", type=Path, default=DATOS_DEFAULT, help="carpeta de MIMIC-IV Demo v2.2")
    args = parser.parse_args()

    con = construir(args.datos)
    exportar(con)
    resumen(con)


if __name__ == "__main__":
    main()
