"""La exposición por administración conserva solo órdenes con dosis reales."""

import duckdb

from antitromboticos.cohorte import SQL_DIR


def preparar() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("""
        CREATE TABLE admissions_fuente (hadm_id INT);
        INSERT INTO admissions_fuente VALUES (10), (20);
        CREATE TABLE prescriptions_fuente (pharmacy_id INT, hadm_id INT, drug VARCHAR,
                                           starttime TIMESTAMP, stoptime TIMESTAMP);
        INSERT INTO prescriptions_fuente VALUES
            (1, 10, 'Heparin', '2150-01-01 00:00', '2150-01-09 00:00'),
            (2, 10, 'Aspirin', '2150-01-01 00:00', '2150-01-09 00:00'),
            (3, 10, 'Warfarin', '2150-01-01 00:00', '2150-01-09 00:00');
        CREATE TABLE emar (hadm_id INT, pharmacy_id INT, charttime TIMESTAMP, event_txt VARCHAR);
        INSERT INTO emar VALUES
            (10, 1, '2150-01-02 08:00', 'Administered'),
            (10, 1, '2150-01-03 08:00', 'Confirmed'),
            (10, 1, '2150-01-05 08:00', 'Not Given'),
            (10, 2, '2150-01-04 08:00', 'Not Given');
    """)
    for script in ("01_cobertura_emar.sql", "02_exposicion_administrada.sql"):
        con.execute((SQL_DIR / "sensibilidad" / script).read_text(encoding="utf-8"))
    return con


def test_restringe_a_hospitalizaciones_con_emar():
    assert preparar().execute("SELECT hadm_id FROM admissions").fetchall() == [(10,)]


def test_solo_conserva_ordenes_administradas():
    filas = preparar().execute("SELECT pharmacy_id FROM prescriptions").fetchall()
    assert filas == [(1,)]


def test_intervalo_usa_dosis_reales_y_no_cuenta_not_given():
    inicio, fin = preparar().execute("""
        SELECT strftime(starttime, '%Y-%m-%d %H:%M'), strftime(stoptime, '%Y-%m-%d %H:%M') FROM prescriptions
    """).fetchall()[0]
    assert inicio == "2150-01-02 08:00"
    assert fin == "2150-01-03 20:00"
