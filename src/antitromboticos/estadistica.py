"""Funciones estadísticas para tablas 2×2 y la Tabla 1, sin dependencias externas.

Convención de una tabla 2×2 (expuestos = combinación, no expuestos = solo anticoagulante)::

                 evento   sin evento   total
    expuestos      a          b         n1
    no expuestos   c          d         n0
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import NormalDist, mean, stdev

Z95 = 1.959963984540054


@dataclass(frozen=True)
class Estimacion:
    valor: float
    li: float  # límite inferior del IC 95 %
    ls: float  # límite superior del IC 95 %


def wilson(eventos: int, n: int) -> Estimacion:
    """Proporción con IC 95 % de Wilson (se comporta bien con n pequeños y con 0 eventos)."""
    if n == 0:
        return Estimacion(math.nan, math.nan, math.nan)
    p = eventos / n
    centro = (p + Z95**2 / (2 * n)) / (1 + Z95**2 / n)
    margen = Z95 * math.sqrt(p * (1 - p) / n + Z95**2 / (4 * n**2)) / (1 + Z95**2 / n)
    return Estimacion(p, max(0.0, centro - margen), min(1.0, centro + margen))


def diferencia_riesgos(a: int, n1: int, c: int, n0: int) -> Estimacion:
    """Diferencia de riesgos (expuestos − no expuestos) con IC 95 % de Wald."""
    if n1 == 0 or n0 == 0:
        return Estimacion(math.nan, math.nan, math.nan)
    p1, p0 = a / n1, c / n0
    ee = math.sqrt(p1 * (1 - p1) / n1 + p0 * (1 - p0) / n0)
    dr = p1 - p0
    if ee == 0:  # ambos grupos en 0 % o 100 %: el IC de Wald no está definido
        return Estimacion(dr, math.nan, math.nan)
    return Estimacion(dr, dr - Z95 * ee, dr + Z95 * ee)


def razon_riesgos(a: int, n1: int, c: int, n0: int) -> Estimacion:
    """Razón de riesgos con IC 95 % en escala logarítmica.

    Si algún grupo tiene 0 eventos se aplica la corrección de Haldane (+0.5 a cada celda).
    Si ambos grupos tienen 0 eventos, la razón no está definida.
    """
    if n1 == 0 or n0 == 0 or (a == 0 and c == 0):
        return Estimacion(math.nan, math.nan, math.nan)
    if a == 0 or c == 0:
        a, c, n1, n0 = a + 0.5, c + 0.5, n1 + 1, n0 + 1
    rr = (a / n1) / (c / n0)
    ee = math.sqrt(1 / a - 1 / n1 + 1 / c - 1 / n0)
    return Estimacion(rr, rr * math.exp(-Z95 * ee), rr * math.exp(Z95 * ee))


def mantel_haenszel_rr(estratos: list[tuple[int, int, int, int]]) -> Estimacion:
    """Razón de riesgos combinada de Mantel-Haenszel.

    `estratos` es una lista de tuplas (a, n1, c, n0). La varianza del logaritmo usa el estimador
    de Greenland y Robins (1985). Se omiten los estratos con algún grupo vacío.
    """
    num = den = var_num = 0.0
    for a, n1, c, n0 in estratos:
        n = n1 + n0
        if n1 == 0 or n0 == 0:
            continue
        num += a * n0 / n
        den += c * n1 / n
        var_num += (n1 * n0 * (a + c) - a * c * n) / n**2
    if num == 0 or den == 0:
        return Estimacion(math.nan, math.nan, math.nan)
    rr = num / den
    ee = math.sqrt(var_num / (num * den))
    return Estimacion(rr, rr * math.exp(-Z95 * ee), rr * math.exp(Z95 * ee))


def smd_continua(x1: list[float], x0: list[float]) -> float:
    """Diferencia de medias estandarizada (d de Cohen con DE combinada)."""
    if len(x1) < 2 or len(x0) < 2:
        return math.nan
    de = math.sqrt((stdev(x1) ** 2 + stdev(x0) ** 2) / 2)
    return (mean(x1) - mean(x0)) / de if de > 0 else 0.0


def smd_binaria(p1: float, p0: float) -> float:
    """Diferencia de medias estandarizada para una proporción."""
    de = math.sqrt((p1 * (1 - p1) + p0 * (1 - p0)) / 2)
    return (p1 - p0) / de if de > 0 else 0.0


def regresion_logistica(X, y, max_iter: int = 50, tol: float = 1e-8):
    """Regresión logística por IRLS. `X` debe incluir el intercepto. Devuelve (coeficientes, errores estándar)."""
    import numpy as np

    X, y = np.asarray(X, dtype=float), np.asarray(y, dtype=float)
    beta = np.zeros(X.shape[1])
    for _ in range(max_iter):
        p = 1 / (1 + np.exp(-X @ beta))
        pesos = np.clip(p * (1 - p), 1e-10, None)
        hessiano = X.T @ (X * pesos[:, None])
        paso = np.linalg.solve(hessiano, X.T @ (y - p))
        beta += paso
        if np.max(np.abs(paso)) < tol:
            break
    p = 1 / (1 + np.exp(-X @ beta))
    covarianza = np.linalg.inv(X.T @ (X * np.clip(p * (1 - p), 1e-10, None)[:, None]))
    return beta, np.sqrt(np.diag(covarianza))


def newcombe_rd(a: int, n1: int, c: int, n0: int) -> Estimacion:
    """Diferencia de riesgos con IC 95 % híbrido de Newcombe (adecuado con n pequeños y ceros)."""
    w1, w0 = wilson(a, n1), wilson(c, n0)
    d = w1.valor - w0.valor
    li = d - math.sqrt((w1.valor - w1.li) ** 2 + (w0.ls - w0.valor) ** 2)
    ls = d + math.sqrt((w1.ls - w1.valor) ** 2 + (w0.valor - w0.li) ** 2)
    return Estimacion(d, li, ls)


def holm(p_valores: list[float]) -> list[float]:
    """Valores p ajustados por Holm-Bonferroni, en el orden original."""
    m = len(p_valores)
    orden = sorted(range(m), key=lambda i: p_valores[i])
    ajustados, maximo = [0.0] * m, 0.0
    for rango, i in enumerate(orden):
        maximo = max(maximo, min(1.0, (m - rango) * p_valores[i]))
        ajustados[i] = maximo
    return ajustados


def hodges_lehmann(x1: list[float], x0: list[float]) -> Estimacion:
    """Diferencia de ubicación (x1 − x0) de Hodges-Lehmann con IC 95 % de Moses."""
    dif = sorted(a - b for a in x1 for b in x0)
    m, n1, n0 = len(dif), len(x1), len(x0)
    centro = (dif[(m - 1) // 2] + dif[m // 2]) / 2
    k = max(0, math.floor(m / 2 - Z95 * math.sqrt(n1 * n0 * (n1 + n0 + 1) / 12)))
    return Estimacion(centro, dif[k], dif[m - k - 1])


def potencia_dos_proporciones(p1: float, p0: float, n1: int, n0: int, alfa: float = 0.05) -> float:
    """Potencia bilateral aproximada para comparar dos proporciones (h de Cohen)."""
    normal = NormalDist()
    h = abs(2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p0)))
    return normal.cdf(h * math.sqrt(n1 * n0 / (n1 + n0)) - normal.inv_cdf(1 - alfa / 2))


def n_por_grupo(p1: float, p0: float, potencia: float = 0.8, alfa: float = 0.05) -> int:
    """Pacientes por grupo (asignación 1:1) para detectar p1 vs. p0 (h de Cohen)."""
    normal = NormalDist()
    h = abs(2 * math.asin(math.sqrt(p1)) - 2 * math.asin(math.sqrt(p0)))
    return math.ceil(2 * ((normal.inv_cdf(1 - alfa / 2) + normal.inv_cdf(potencia)) / h) ** 2)


def ols_hc3(X, y):
    """Mínimos cuadrados con errores robustos HC3. `X` incluye el intercepto. Devuelve (coef, ee, gl)."""
    import numpy as np

    X, y = np.asarray(X, dtype=float), np.asarray(y, dtype=float)
    xtx_inv = np.linalg.inv(X.T @ X)
    beta = xtx_inv @ X.T @ y
    residuos = y - X @ beta
    palanca = np.clip(np.einsum("ij,jk,ik->i", X, xtx_inv, X), 0, 0.999)
    pesos = (residuos / (1 - palanca)) ** 2
    covarianza = xtx_inv @ (X.T @ (X * pesos[:, None])) @ xtx_inv
    return beta, np.sqrt(np.diag(covarianza)), X.shape[0] - X.shape[1]
