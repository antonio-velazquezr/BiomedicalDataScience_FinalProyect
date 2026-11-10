"""El diccionario de datos debe cubrir exactamente las columnas que produce el SQL, en ambas fuentes."""

import duckdb
import pytest
from test_cohorte import crear_tablas

from antitromboticos.cohorte import SQL_DIR, ejecutar_sql
from antitromboticos.diccionario import VARIABLES, generar, verificar_cobertura

# Esquema mínimo de OMOP: solo las columnas que usa sql/omop/ (tablas vacías)
ESQUEMA_OMOP = {
    "person": "person_id BIGINT, person_source_value VARCHAR, gender_concept_id INT, year_of_birth INT",
    "visit_occurrence": "visit_occurrence_id BIGINT, person_id BIGINT, visit_concept_id INT, visit_start_datetime TIMESTAMP, "
                        "visit_end_datetime TIMESTAMP, visit_source_value VARCHAR, discharge_to_concept_id INT",
    "death": "person_id BIGINT, death_datetime TIMESTAMP",
    "drug_exposure": "person_id BIGINT, visit_occurrence_id BIGINT, drug_concept_id INT, drug_exposure_start_datetime TIMESTAMP, "
                     "drug_exposure_end_datetime TIMESTAMP, route_source_value VARCHAR",
    "measurement": "person_id BIGINT, measurement_concept_id INT, value_as_number DOUBLE, measurement_datetime TIMESTAMP",
    "visit_detail": "visit_occurrence_id BIGINT, visit_detail_start_datetime TIMESTAMP, visit_detail_end_datetime TIMESTAMP, "
                    "care_site_id BIGINT",
    "care_site": "care_site_id BIGINT, care_site_name VARCHAR",
    "condition_occurrence": "visit_occurrence_id BIGINT, condition_source_value VARCHAR, condition_type_concept_id INT",
}


def columnas(con: duckdb.DuckDBPyConnection) -> list[str]:
    return [r[0] for r in con.execute("DESCRIBE cohorte_analitica").fetchall()]


def test_cobertura_mimic():
    con = duckdb.connect()
    crear_tablas(con)
    ejecutar_sql(con, SQL_DIR)
    verificar_cobertura("mimic", columnas(con))


def test_sql_omop_corre_y_cobertura():
    con = duckdb.connect()
    for tabla, cols in ESQUEMA_OMOP.items():
        con.execute(f"CREATE TABLE {tabla} ({cols})")
    ejecutar_sql(con, SQL_DIR / "omop")
    verificar_cobertura("omop", columnas(con))


def test_cobertura_detecta_columnas_sin_documentar():
    with pytest.raises(ValueError, match="sin documentar"):
        verificar_cobertura("mimic", [v.nombre for v in VARIABLES if v.solo != "omop"] + ["columna_nueva"])


def test_nombres_unicos_y_campos_completos():
    nombres = [v.nombre for v in VARIABLES]
    assert len(nombres) == len(set(nombres))
    assert all(v.descripcion and v.tipo and v.dominio for v in VARIABLES)


def test_generar_produce_markdown():
    texto = generar()
    assert texto.startswith("# Diccionario de datos")
    assert all(f"`{v.nombre}`" in texto for v in VARIABLES)
