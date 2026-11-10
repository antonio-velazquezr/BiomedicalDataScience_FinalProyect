"""Pruebas de la lógica de cohorte y desenlaces con datos sintéticos mínimos.

Cada paciente sintético representa un caso de la definición:

    1  heparina SC + aspirina solapadas                 -> combinación, profiláctica, caída de Hb >= 2
    2  solo heparina SC, con transfusión                -> solo anticoagulante, sangrado por transfusión
    3  aspirina en dosis única 2 días antes de warfarina -> combinación (efecto residual de la aspirina)
    4  aspirina y heparina separadas por 10 días        -> no clasificable (excluido)
    5  diagnóstico principal de sangrado digestivo      -> excluido
    6  sin laboratorios basales                         -> excluido
    7  solo heparina "Flush"                            -> no es anticoagulante (excluido)
"""

from __future__ import annotations

import duckdb
import pytest

from antitromboticos.cohorte import ejecutar_sql

D = "2150-01-01"  # día 0 de todas las hospitalizaciones sintéticas


def ts(dia: float, hora: int = 0) -> str:
    """Timestamp sintético a `dia` días y `hora` horas del día 0."""
    return f"TIMESTAMP '{D}' + INTERVAL {int(dia * 24) + hora} HOUR"


def crear_tablas(con: duckdb.DuckDBPyConnection) -> None:
    con.execute("""
        CREATE TABLE patients (subject_id INT, gender VARCHAR, anchor_age INT, anchor_year INT);
        INSERT INTO patients VALUES
            (1,'F',70,2150),(2,'M',60,2150),(3,'M',80,2150),(4,'F',55,2150),
            (5,'M',65,2150),(6,'F',50,2150),(7,'M',45,2150);
    """)
    admisiones = ", ".join(
        f"({s}, {s}0, {ts(0)}, {ts(dias)}, 0)" for s, dias in [(1, 10), (2, 10), (3, 10), (4, 15), (5, 10), (6, 10), (7, 10)]
    )
    con.execute(f"""
        CREATE TABLE admissions (subject_id INT, hadm_id INT, admittime TIMESTAMP, dischtime TIMESTAMP,
                                 hospital_expire_flag INT);
        INSERT INTO admissions VALUES {admisiones};
    """)
    con.execute(f"""
        CREATE TABLE prescriptions (subject_id INT, hadm_id INT, starttime TIMESTAMP, stoptime TIMESTAMP,
                                    drug VARCHAR, route VARCHAR, dose_val_rx VARCHAR);
        INSERT INTO prescriptions VALUES
            (1, 10, {ts(1)}, {ts(8)}, 'Heparin', 'SC', '5000'),
            (1, 10, {ts(2)}, {ts(8)}, 'Aspirin', 'PO', '81'),
            (2, 20, {ts(1)}, {ts(8)}, 'Heparin', 'SC', '5000'),
            (3, 30, {ts(1)}, {ts(1)}, 'Aspirin', 'PO', '325'),
            (3, 30, {ts(3)}, {ts(9)}, 'Warfarin', 'PO/NG', '5'),
            (4, 40, {ts(0, 2)}, {ts(0, 2)}, 'Aspirin', 'PO', '325'),
            (4, 40, {ts(10)}, {ts(14)}, 'Heparin', 'SC', '5000'),
            (5, 50, {ts(1)}, {ts(8)}, 'Heparin', 'SC', '5000'),
            (6, 60, {ts(1)}, {ts(8)}, 'Heparin', 'SC', '5000'),
            (7, 70, {ts(1)}, {ts(8)}, 'Heparin Flush (10 units/ml)', 'IV', '2');
    """)
    # Basales (día 0) para todos menos el paciente 6; seguimiento según el caso
    labs = []
    for s in (1, 2, 3, 4, 5, 7):
        labs += [f"({s}, {s}0, 51222, {ts(0, 12)}, 12.0)", f"({s}, {s}0, 51265, {ts(0, 12)}, 250.0)"]
    for s, dia in ((3, 2), (4, 9)):  # basal dentro de las 48 h previas a su fecha índice (días 3 y 10)
        labs += [f"({s}, {s}0, 51222, {ts(dia)}, 12.0)", f"({s}, {s}0, 51265, {ts(dia)}, 250.0)"]
    labs += [
        f"(1, 10, 51222, {ts(5)}, 9.5)",   # caída de 2.5 g/dL
        f"(1, 10, 51265, {ts(5)}, 100.0)", # caída del 60 %
        f"(2, 20, 51222, {ts(5)}, 11.5)",  # caída de 0.5 g/dL
        f"(2, 20, 51265, {ts(5)}, 240.0)",
        f"(3, 30, 51222, {ts(5)}, 11.8)",
        f"(6, 60, 51222, {ts(5)}, 11.0)",
    ]
    con.execute(f"""
        CREATE TABLE labevents (subject_id INT, hadm_id INT, itemid INT, charttime TIMESTAMP, valuenum DOUBLE);
        INSERT INTO labevents VALUES {", ".join(labs)};
    """)
    con.execute("""
        CREATE TABLE services (hadm_id INT, curr_service VARCHAR);
        INSERT INTO services VALUES (10,'MED'),(20,'SURG'),(30,'CSURG'),(40,'MED'),(50,'MED'),(60,'MED'),(70,'MED');
        CREATE TABLE diagnoses_icd (hadm_id INT, seq_num INT, icd_code VARCHAR);
        INSERT INTO diagnoses_icd VALUES (10,1,'I4891'),(10,2,'I2510'),(20,1,'K3580'),(30,1,'42731'),
                                         (50,1,'K922'),(60,1,'J189'),(70,1,'J189');
    """)
    con.execute(f"""
        CREATE TABLE icustays (hadm_id INT, intime TIMESTAMP, outtime TIMESTAMP);
        INSERT INTO icustays VALUES (20, {ts(4)}, {ts(6)});
        CREATE TABLE d_items (itemid INT, label VARCHAR);
        INSERT INTO d_items VALUES (225168, 'Packed Red Blood Cells'), (220949, 'Dextrose 5%');
        CREATE TABLE inputevents (hadm_id INT, itemid INT, starttime TIMESTAMP);
        INSERT INTO inputevents VALUES (20, 225168, {ts(4, 6)}), (10, 220949, {ts(4)});
    """)


@pytest.fixture(scope="module")
def con() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    crear_tablas(con)
    ejecutar_sql(con)
    return con


def fila(con: duckdb.DuckDBPyConnection, subject_id: int) -> dict | None:
    rel = con.sql(f"SELECT * FROM cohorte_analitica WHERE subject_id = {subject_id}")
    datos = rel.fetchall()
    return dict(zip(rel.columns, datos[0])) if datos else None


def test_clasificacion_de_farmacos(con):
    filas = dict(con.execute("SELECT drug, intensidad FROM rx_antitrombotico WHERE familia = 'anticoagulante'").fetchall())
    assert filas["Heparin"] == "profilactica"
    assert filas["Warfarin"] == "terapeutica"
    assert "Heparin Flush (10 units/ml)" not in filas


def test_combinacion_con_solapamiento(con):
    p1 = fila(con, 1)
    assert p1["grupo"] == "combinacion"
    assert p1["intensidad"] == "profilactica"
    # fecha índice = inicio del solapamiento = inicio de la aspirina (día 2)
    assert p1["t_indice"] == con.execute(f"SELECT {ts(2)}").fetchall()[0][0]


def test_efecto_residual_de_aspirina_cuenta_como_combinacion(con):
    p3 = fila(con, 3)
    assert p3["grupo"] == "combinacion"
    assert p3["intensidad"] == "terapeutica"
    assert p3["estrato"] == "cirugia_cardiaca"


def test_solo_anticoagulante(con):
    p2 = fila(con, 2)
    assert p2["grupo"] == "solo_anticoagulante"
    assert p2["estrato"] == "quirurgico"


@pytest.mark.parametrize("subject_id", [4, 5, 6, 7])
def test_exclusiones(con, subject_id):
    assert fila(con, subject_id) is None


def test_desenlace_sangrado_por_hemoglobina(con):
    p1 = fila(con, 1)
    assert p1["caida_hb_2"] is True
    assert p1["sangrado_relevante"] is True
    assert p1["transfusion_gr"] is False
    assert p1["plaquetas_caida_50"] is True
    assert p1["fibrilacion_auricular"] is True and p1["cardiopatia_isquemica"] is True


def test_desenlace_sangrado_por_transfusion(con):
    p2 = fila(con, 2)
    assert p2["caida_hb_2"] is False
    assert p2["transfusion_gr"] is True
    assert p2["sangrado_relevante"] is True
    assert p2["uci_posterior"] is True


def test_sin_eventos(con):
    p3 = fila(con, 3)
    assert p3["sangrado_relevante"] is False
    # sin plaquetas de seguimiento: la caída no se puede afirmar
    assert p3["plaquetas_caida_50"] is False


def test_atricion_es_monotona(con):
    pasos = con.execute("SELECT hospitalizaciones FROM atricion ORDER BY paso").fetchall()
    conteos = [p[0] for p in pasos]
    assert conteos == sorted(conteos, reverse=True)
    assert conteos[0] == 7 and conteos[-1] == 3
