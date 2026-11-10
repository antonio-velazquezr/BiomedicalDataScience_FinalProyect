"""Funciones estadísticas para tablas 2×2 y la Tabla 1, sin dependencias externas.

Convención de una tabla 2×2 (expuestos = combinación, no expuestos = solo anticoagulante)::

                 evento   sin evento   total
    expuestos      a          b         n1
    no expuestos   c          d         n0
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean, stdev

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
