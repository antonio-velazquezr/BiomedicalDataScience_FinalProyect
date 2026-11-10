"""Construye la cohorte anticoagulante + antiagregante vs. solo anticoagulante.

Hay dos fuentes con la misma definición de cohorte:

* ``mimic``: MIMIC-IV Clinical Database Demo v2.2 (tablas nativas), SQL en ``sql/``
* ``omop``:  MIMIC-IV demo en OMOP CDM 5.3.1 (v0.9), SQL en ``sql/omop/``

Carga las tablas en DuckDB, ejecuta los scripts SQL en orden y exporta:

* ``data/processed/<fuente>/cohorte_analitica.parquet``: nivel individual (no se versiona)
* ``resultados/[omop/]atricion.csv``: tabla de atrición (agregada, sí se versiona)

Uso::

    python -m antitromboticos.cohorte                 # fuente mimic
    python -m antitromboticos.cohorte --fuente omop
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import duckdb

RAIZ = Path(__file__).resolve().parents[2]
SQL_DIR = RAIZ / "sql"
SALIDA_PROCESADOS = RAIZ / "data" / "processed"
SALIDA_RESULTADOS = RAIZ / "resultados"


@dataclass(frozen=True)
class Fuente:
    nombre: str
    datos: Path
    sql_dir: Path
    tablas: dict[str, str]  # nombre de la vista -> ruta relativa del CSV dentro de `datos`
    resultados: Path

    @property
    def procesados(self) -> Path:
        return SALIDA_PROCESADOS / self.nombre


FUENTES = {
    "mimic": Fuente(
        nombre="mimic",
        datos=RAIZ / "data" / "raw" / "mimic-iv-clinical-database-demo-2.2",
        sql_dir=SQL_DIR,
        tablas={
            t: f"{m}/{t}.csv.gz"
            for t, m in {
                "patients": "hosp", "admissions": "hosp", "prescriptions": "hosp", "labevents": "hosp",
                "services": "hosp", "diagnoses_icd": "hosp",
                "icustays": "icu", "inputevents": "icu", "d_items": "icu",
            }.items()
        },
        resultados=SALIDA_RESULTADOS,
    ),
    "omop": Fuente(
        nombre="omop",
        datos=RAIZ / "data" / "raw" / "omop" / "mimic-iv-demo-data-in-the-omop-common-data-model-0.9" / "1_omop_data_csv",
        sql_dir=SQL_DIR / "omop",
        tablas={
            t: f"{t}.csv"
            for t in ["person", "visit_occurrence", "visit_detail", "care_site", "drug_exposure",
                      "measurement", "condition_occurrence", "death"]
        },
        resultados=SALIDA_RESULTADOS / "omop",
    ),
}


def cargar_tablas(con: duckdb.DuckDBPyConnection, fuente: Fuente, datos: Path | None = None) -> None:
    """Registra cada CSV de la fuente como una vista de DuckDB."""
    datos = datos or fuente.datos
    for tabla, relativa in fuente.tablas.items():
        ruta = datos / relativa
        if not ruta.exists():
            raise FileNotFoundError(f"No se encontró {ruta}. Revisa el README para descargar los datos.")
        con.execute(
            f"CREATE OR REPLACE VIEW {tabla} AS "
            f"SELECT * FROM read_csv('{ruta.as_posix()}', sample_size = -1)"
        )


def ejecutar_sql(con: duckdb.DuckDBPyConnection, sql_dir: Path = SQL_DIR) -> None:
    """Ejecuta los scripts .sql de la carpeta (sin subcarpetas) en orden alfabético."""
    for script in sorted(sql_dir.glob("*.sql")):
        con.execute(script.read_text(encoding="utf-8"))


def construir(fuente: str = "mimic", datos: Path | None = None) -> duckdb.DuckDBPyConnection:
    """Construye la cohorte de la fuente indicada y devuelve la conexión con las tablas creadas."""
    f = FUENTES[fuente]
    con = duckdb.connect()
    cargar_tablas(con, f, datos)
    ejecutar_sql(con, f.sql_dir)
    return con


def exportar(con: duckdb.DuckDBPyConnection, fuente: str = "mimic") -> Path:
    """Exporta la cohorte analítica (parquet) y la atrición (CSV). Devuelve la ruta del parquet."""
    f = FUENTES[fuente]
    f.procesados.mkdir(parents=True, exist_ok=True)
    f.resultados.mkdir(parents=True, exist_ok=True)
    destino = f.procesados / "cohorte_analitica.parquet"
    con.execute(f"COPY cohorte_analitica TO '{destino.as_posix()}' (FORMAT parquet)")
    con.execute(f"COPY atricion TO '{(f.resultados / 'atricion.csv').as_posix()}' (HEADER)")
    return destino


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
               count(*)                                    AS n,
               count(*) FILTER (WHERE sangrado_relevante)    AS sangrado_relevante,
               count(*) FILTER (WHERE caida_hb_2)            AS caida_hb_2,
               count(*) FILTER (WHERE transfusion_gr)        AS transfusion,
               count(*) FILTER (WHERE plaquetas_caida_50)    AS plaq_caida_50,
               count(*) FILTER (WHERE uci_posterior)         AS uci_posterior,
               count(*) FILTER (WHERE muerte)                AS muerte
        FROM cohorte_analitica GROUP BY grupo ORDER BY grupo
    """))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fuente", choices=list(FUENTES), default="mimic")
    parser.add_argument("--datos", type=Path, default=None, help="carpeta de datos (por defecto, la de la fuente)")
    args = parser.parse_args()

    con = construir(args.fuente, args.datos)
    exportar(con, args.fuente)
    resumen(con)


if __name__ == "__main__":
    main()
