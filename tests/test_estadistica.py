"""Pruebas de las funciones estadísticas contra valores calculados a mano."""

import math

import pytest

from antitromboticos.estadistica import (
    diferencia_riesgos,
    hodges_lehmann,
    holm,
    mantel_haenszel_rr,
    n_por_grupo,
    newcombe_rd,
    ols_hc3,
    potencia_dos_proporciones,
    razon_riesgos,
    regresion_logistica,
    smd_binaria,
    smd_continua,
    wilson,
)


def test_wilson_valores_conocidos():
    e = wilson(5, 10)
    assert e.valor == 0.5
    assert e.li == pytest.approx(0.2366, abs=1e-4)
    assert e.ls == pytest.approx(0.7634, abs=1e-4)


def test_wilson_cero_eventos_tiene_limite_superior_positivo():
    e = wilson(0, 10)
    assert e.valor == 0 and e.li == 0
    assert e.ls == pytest.approx(0.2775, abs=1e-4)


def test_razon_riesgos():
    # RR = (10/100) / (5/100) = 2; EE(log RR) = sqrt(1/10 - 1/100 + 1/5 - 1/100) = sqrt(0.28)
    e = razon_riesgos(10, 100, 5, 100)
    assert e.valor == pytest.approx(2.0)
    assert e.li == pytest.approx(2 * math.exp(-1.959964 * math.sqrt(0.28)), rel=1e-5)
    assert e.ls == pytest.approx(2 * math.exp(1.959964 * math.sqrt(0.28)), rel=1e-5)


def test_razon_riesgos_con_cero_usa_haldane_y_sin_eventos_es_nan():
    assert razon_riesgos(0, 10, 3, 10).valor == pytest.approx((0.5 / 11) / (3.5 / 11))
    assert math.isnan(razon_riesgos(0, 10, 0, 10).valor)


def test_diferencia_riesgos():
    e = diferencia_riesgos(10, 100, 5, 100)
    assert e.valor == pytest.approx(0.05)
    ee = math.sqrt(0.1 * 0.9 / 100 + 0.05 * 0.95 / 100)
    assert e.li == pytest.approx(0.05 - 1.959964 * ee, rel=1e-5)


def test_diferencia_sin_eventos_no_tiene_ic():
    e = diferencia_riesgos(0, 10, 0, 8)
    assert e.valor == 0 and math.isnan(e.li) and math.isnan(e.ls)


def test_mantel_haenszel_con_un_estrato_es_la_cruda():
    cruda = razon_riesgos(10, 100, 5, 100)
    mh = mantel_haenszel_rr([(10, 100, 5, 100)])
    assert mh.valor == pytest.approx(cruda.valor)
    assert mh.li == pytest.approx(cruda.li)
    assert mh.ls == pytest.approx(cruda.ls)


def test_mantel_haenszel_con_estratos_homogeneos():
    # Dos estratos con RR = 2 cada uno -> RR combinado = 2
    mh = mantel_haenszel_rr([(10, 100, 5, 100), (4, 20, 2, 20)])
    assert mh.valor == pytest.approx(2.0)
    assert mh.li < 2.0 < mh.ls


def test_mantel_haenszel_omite_estratos_vacios():
    assert mantel_haenszel_rr([(10, 100, 5, 100), (0, 0, 3, 10)]).valor == pytest.approx(2.0)


def test_regresion_logistica_reproduce_tabla_2x2():
    # a=10, b=20, c=5, d=25 -> OR = 2.5; EE(log OR) = sqrt(1/10 + 1/20 + 1/5 + 1/25)
    x = [1] * 30 + [0] * 30
    y = [1] * 10 + [0] * 20 + [1] * 5 + [0] * 25
    beta, ee = regresion_logistica([[1, v] for v in x], y)
    assert math.exp(beta[1]) == pytest.approx(2.5, rel=1e-6)
    assert ee[1] == pytest.approx(math.sqrt(0.39), rel=1e-6)


def test_newcombe_ejemplo_publicado():
    # Newcombe (1998), método 10: 56/70 vs. 48/80
    e = newcombe_rd(56, 70, 48, 80)
    assert e.valor == pytest.approx(0.2)
    assert e.li == pytest.approx(0.0524, abs=1e-4)
    assert e.ls == pytest.approx(0.3339, abs=1e-4)


def test_holm():
    assert holm([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])
    assert holm([0.9, 0.8]) == pytest.approx([1.0, 1.0])  # 2 × 0.8 se trunca en 1


def test_hodges_lehmann_desplazamiento_conocido():
    e = hodges_lehmann([3, 4, 5, 6, 7, 8], [1, 2, 3, 4, 5, 6])
    assert e.valor == pytest.approx(2.0)
    assert e.li < 2 < e.ls


def test_potencia_y_tamano_de_muestra_son_coherentes():
    n = n_por_grupo(0.2, 0.1)
    assert potencia_dos_proporciones(0.2, 0.1, n, n) == pytest.approx(0.8, abs=0.01)


def test_ols_recupera_recta_exacta():
    x = [0.0, 1.0, 2.0, 3.0, 4.0]
    beta, ee, gl = ols_hc3([[1, v] for v in x], [2 + 3 * v for v in x])
    assert beta == pytest.approx([2, 3])
    assert gl == 3 and max(ee) == pytest.approx(0, abs=1e-9)


def test_diferencias_estandarizadas():
    assert smd_binaria(0.5, 0.5) == 0
    assert smd_binaria(0.6, 0.4) == pytest.approx(0.2 / math.sqrt(0.24))
    assert smd_continua([1, 2, 3], [1, 2, 3]) == 0
    assert smd_continua([2, 3, 4], [1, 2, 3]) == pytest.approx(1.0)
