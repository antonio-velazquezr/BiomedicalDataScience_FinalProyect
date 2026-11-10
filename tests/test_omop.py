"""Pruebas de los conjuntos de conceptos OMOP (sql/omop/01_conjuntos_conceptos.sql) con datos sintéticos."""

import duckdb
import pytest

from antitromboticos.cohorte import SQL_DIR

SCRIPT = SQL_DIR / "omop" / "01_conjuntos_conceptos.sql"

# (drug_exposure_id, drug_concept_id, ruta)
EXPOSICIONES = [
    (1, 43011850, "SC"),      # heparina SC          -> profiláctica
    (2, 43011850, "IV"),      # heparina IV          -> terapéutica
    (3, 43011850, "DIALYS"),  # cebado de CRRT       -> excluida
    (4, 43011884, "IV"),      # heparina flush       -> no está en el conjunto
    (5, 46275400, "IV"),      # infusión 25,000 U    -> terapéutica
    (6, 40160973, "SC"),      # enoxaparina 40 mg    -> profiláctica
    (7, 40160992, "SC"),      # enoxaparina 80 mg    -> terapéutica
    (8, 40241334, "PO/NG"),   # rivaroxabán 10 mg    -> profiláctico
    (9, 40163555, "PO"),      # warfarina            -> terapéutica
    (10, 1113346, "PO"),      # aspirina 81 mg       -> antiagregante
    (11, 19075601, "PO"),     # clopidogrel          -> antiagregante
    (12, 1308216, "PO"),      # concepto ajeno (no antitrombótico) -> no está
]


@pytest.fixture(scope="module")
def rx() -> dict[int, tuple]:
    con = duckdb.connect()
    filas = ", ".join(
        f"({i}, 1, 1, {c}, TIMESTAMP '2150-01-01 08:00', TIMESTAMP '2150-01-02 08:00', '{r}')"
        for i, c, r in EXPOSICIONES
    )
    con.execute(f"""
        CREATE TABLE drug_exposure (drug_exposure_id INT, person_id INT, visit_occurrence_id INT,
            drug_concept_id INT, drug_exposure_start_datetime TIMESTAMP, drug_exposure_end_datetime TIMESTAMP,
            route_source_value VARCHAR);
        INSERT INTO drug_exposure VALUES {filas};
    """)
    con.execute(SCRIPT.read_text(encoding="utf-8"))
    filas = con.execute("""
        SELECT d.drug_exposure_id, r.familia, r.farmaco, r.intensidad
        FROM rx_antitrombotico r
        JOIN drug_exposure d ON d.drug_concept_id = r.drug_concept_id AND d.route_source_value = r.route
    """).fetchall()
    return {f[0]: f[1:] for f in filas}


@pytest.mark.parametrize("exposicion, esperado", [
    (1, ("anticoagulante", "HNF", "profilactica")),
    (2, ("anticoagulante", "HNF", "terapeutica")),
    (5, ("anticoagulante", "HNF", "terapeutica")),
    (6, ("anticoagulante", "enoxaparina", "profilactica")),
    (7, ("anticoagulante", "enoxaparina", "terapeutica")),
    (8, ("anticoagulante", "DOAC", "profilactica")),
    (9, ("anticoagulante", "warfarina", "terapeutica")),
    (10, ("antiagregante", "aspirina", None)),
    (11, ("antiagregante", "P2Y12", None)),
])
def test_clasificacion(rx, exposicion, esperado):
    assert rx[exposicion] == esperado


@pytest.mark.parametrize("exposicion", [3, 4, 12])
def test_excluidas(rx, exposicion):
    assert exposicion not in rx
