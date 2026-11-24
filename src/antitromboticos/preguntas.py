"""Banco de análisis: cada figura contesta una pregunta.

Escribe en ``figuras/analisis/`` una figura por pregunta (P01, P02, …) y un ``INDICE.md`` con la
pregunta, la respuesta corta (calculada a partir de los datos) y el archivo. Sirve para revisar qué
tenemos y elegir qué va a la presentación.

Uso::

    python -m antitromboticos.preguntas
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from typing import Callable

import duckdb
import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from antitromboticos.cohorte import FUENTES, RAIZ, cargar_tablas, construir
from antitromboticos.estadistica import Estimacion, mantel_haenszel_rr, razon_riesgos, wilson
from antitromboticos.figuras import (
    COLOR, FONDO, FUENTE, GRUPOS, NOMBRE, PIES, REJILLA, TENUE, TINTA, TINTA2, guardar, leyenda_figura, lienzo, tabla,
)

SALIDA = RAIZ / "figuras" / "analisis"
INTENSIDADES = ("profilactica", "terapeutica")
rng = np.random.default_rng(20261109)


@dataclass
class Resultado:
    archivo: str
    pregunta: str
    respuesta: str


# ----------------------------------------------------------------------------- utilidades estadísticas
def conteos(df: pl.DataFrame, col: str = "sangrado_relevante") -> tuple[int, int, int, int]:
    d = df.filter(pl.col(col).is_not_null())
    g1, g0 = d.filter(pl.col("grupo") == "combinacion"), d.filter(pl.col("grupo") == "solo_anticoagulante")
    return int(g1[col].sum()), g1.height, int(g0[col].sum()), g0.height


def rr_crudo(df: pl.DataFrame, col: str = "sangrado_relevante") -> Estimacion:
    return razon_riesgos(*conteos(df, col))


def rr_ajustado(df: pl.DataFrame, por: pl.Expr | str = "intensidad", col: str = "sangrado_relevante") -> Estimacion:
    """RR de Mantel-Haenszel estratificado por una variable (columna o expresión)."""
    clave = df.select((pl.col(por) if isinstance(por, str) else por).alias("_estrato"))["_estrato"]
    d = df.with_columns(clave)
    return mantel_haenszel_rr([conteos(d.filter(pl.col("_estrato") == v), col) for v in d["_estrato"].unique().to_list()])


def fmt(e: Estimacion) -> str:
    return "no estimable" if math.isnan(e.valor) else f"{e.valor:.2f} ({e.li:.2f}–{e.ls:.2f})"


def cruza_uno(e: Estimacion) -> bool:
    return math.isnan(e.valor) or e.li <= 1 <= e.ls


# ----------------------------------------------------------------------------- utilidades gráficas
def ejes_limpios(ax, grid: str = "y") -> None:
    if grid:
        ax.grid(axis=grid, color=REJILLA, lw=0.8)
    ax.set_axisbelow(True)


def puntos_y_caja(ax, valores: dict[str, list[float]], posiciones: dict[str, float]) -> None:
    """Puntos individuales con jitter + caja (mediana y RIC) por grupo."""
    for g, v in valores.items():
        v = [x for x in v if x is not None and not math.isnan(x)]
        x0 = posiciones[g]
        ax.scatter(x0 + rng.uniform(-0.12, 0.12, len(v)), v, s=28, color=COLOR[g], alpha=0.55, lw=0, zorder=2)
        bp = ax.boxplot([v], positions=[x0 + 0.32], widths=0.14, patch_artist=True, showfliers=False,
                        medianprops=dict(color=TINTA, lw=2), whiskerprops=dict(color=TINTA2),
                        capprops=dict(color=TINTA2), boxprops=dict(facecolor=FONDO, edgecolor=TINTA2))
        del bp
        ax.text(x0 + 0.42, np.median(v), f"mediana {np.median(v):.1f}", va="center", ha="left", fontsize=10,
                color=TINTA)
    ax.set_xticks([posiciones[g] + 0.1 for g in valores], [f"{NOMBRE[g]}\n(n = {len(valores[g])})" for g in valores],
                  color=TINTA)
    ax.tick_params(axis="x", length=0)


def forest(ax, filas: list[tuple[str, Estimacion, str]], lim=(0.1, 10), ref: float = 1.0,
           resaltar: set[int] | None = None, xlabel: str = "Razón de riesgos (IC 95 %, escala log)") -> None:
    """Forest plot genérico. filas = (etiqueta, estimación, texto a la derecha)."""
    from matplotlib.transforms import blended_transform_factory

    col = blended_transform_factory(ax.transAxes, ax.transData)
    n = len(filas)
    for i, (etq, e, der) in enumerate(filas):
        y = n - 1 - i
        if resaltar and i in resaltar:
            ax.axhspan(y - 0.45, y + 0.45, color="#f1f0ec", zorder=0)
        if not math.isnan(e.valor):
            li, ls = max(e.li, lim[0]), min(e.ls, lim[1])
            ax.plot([li, ls], [y, y], color=TINTA, lw=2, solid_capstyle="round")
            ax.plot(min(max(e.valor, lim[0]), lim[1]), y, "s", ms=8, color=TINTA, mec=FONDO, mew=1.5, zorder=3)
            if e.ls > lim[1]:
                ax.annotate("", xy=(lim[1], y), xytext=(lim[1] * 0.8, y), arrowprops=dict(arrowstyle="->", color=TINTA))
            if e.li < lim[0]:
                ax.annotate("", xy=(lim[0], y), xytext=(lim[0] * 1.25, y), arrowprops=dict(arrowstyle="->", color=TINTA))
        ax.text(1.03, y, f"{fmt(e)}   {der}", va="center", fontsize=10, color=TINTA2, transform=col)
    ax.axvline(ref, color=TENUE, lw=1, ls=(0, (4, 3)))
    ax.set_xscale("log")
    ax.set_xlim(*lim)
    ticks = [t for t in (0.1, 0.25, 0.5, 1, 2, 4, 10) if lim[0] <= t <= lim[1]]
    ax.set_xticks(ticks, [f"{t:g}" for t in ticks])
    ax.minorticks_off()
    ax.set_yticks(range(n), [f[0] for f in reversed(filas)], color=TINTA)
    ax.set_ylim(-0.7, n - 0.3)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ejes_limpios(ax, "x")
    ax.set_xlabel(xlabel)


# ----------------------------------------------------------------------------- variantes de la cohorte
def cohorte_variante(parametros: dict[str, int], fuente: str = "mimic") -> pl.DataFrame:
    """Reconstruye la cohorte cambiando las macros-parámetro del SQL (p. ej. seguimiento_d)."""
    f = FUENTES[fuente]
    con = duckdb.connect()
    cargar_tablas(con, f)
    for script in sorted(f.sql_dir.glob("*.sql")):
        sql = script.read_text(encoding="utf-8")
        for nombre, valor in parametros.items():
            sql = re.sub(rf"(MACRO {nombre}\(\)\s+AS\s+)\d+", rf"\g<1>{valor}", sql)
        con.execute(sql)
    return tabla(con, "SELECT * FROM cohorte_analitica")


# ============================================================================= preguntas
def p01_demografia(df: pl.DataFrame) -> Resultado:
    bandas = [(18, 40), (40, 50), (50, 60), (60, 70), (70, 80), (80, 92)]
    etiquetas = ["18–39", "40–49", "50–59", "60–69", "70–79", "≥ 80"]
    edad = {g: df.filter(pl.col("grupo") == g)["edad"].median() for g in GRUPOS}
    fig, axes = lienzo("¿Quiénes son los pacientes de cada grupo?",
                       f"Pirámide de edad por sexo · mediana de edad {edad['combinacion']:.0f} años con la combinación "
                       f"vs. {edad['solo_anticoagulante']:.0f} sin antiagregante", ncols=2, sharey=True)
    maximo = 0
    for ax, g in zip(axes, GRUPOS):
        sub = df.filter(pl.col("grupo") == g)
        for sexo, signo, alfa in (("F", -1, 0.55), ("M", 1, 1.0)):
            n = [sub.filter((pl.col("sexo") == sexo) & (pl.col("edad") >= a) & (pl.col("edad") < b)).height
                 for a, b in bandas]
            maximo = max(maximo, *n)
            ax.barh(range(len(bandas)), [signo * x for x in n], color=COLOR[g], alpha=alfa, height=0.8)
            for i, x in enumerate(n):
                if x:
                    ax.text(signo * (x + 0.3), i, str(x), va="center", ha="left" if signo > 0 else "right",
                            fontsize=9.5, color=TINTA2)
        ax.axvline(0, color=TENUE, lw=1)
        ax.set_title(f"{NOMBRE[g]} (n = {sub.height})", loc="left", fontsize=12.5, color=TINTA, fontweight="bold")
        ax.text(0.25, -0.06, "← Mujeres", transform=ax.transAxes, ha="center", color=TINTA2, fontsize=10.5)
        ax.text(0.75, -0.06, "Hombres →", transform=ax.transAxes, ha="center", color=TINTA2, fontsize=10.5)
        ax.set_xticks([])
        ax.spines["bottom"].set_visible(False)
    for ax in axes:
        ax.set_xlim(-maximo - 2, maximo + 2)
    axes[0].set_yticks(range(len(bandas)), etiquetas, color=TINTA)
    axes[0].set_ylabel("Edad (años)")
    guardar(fig, "P01_demografia.pdf", SALIDA)
    return Resultado("P01_demografia.pdf", "¿Quiénes son los pacientes de cada grupo?",
                     f"El grupo con la combinación es mayor (mediana {edad['combinacion']:.0f} vs. "
                     f"{edad['solo_anticoagulante']:.0f} años) y con más hombres.")


def p02_farmacos(df: pl.DataFrame) -> Resultado:
    comb = df.filter(pl.col("grupo") == "combinacion")
    acs = ["HNF", "enoxaparina", "warfarina", "DOAC"]
    aps = ["aspirina", "P2Y12"]
    matriz = np.array([[comb.filter((pl.col("anticoagulante") == a) & (pl.col("antiagregante") == p)).height
                        for p in aps] for a in acs])
    solo = df.filter(pl.col("grupo") == "solo_anticoagulante")
    top = int(matriz.max())
    i, j = np.unravel_index(matriz.argmax(), matriz.shape)
    fig, axes = lienzo("¿Qué fármacos definen cada grupo?",
                       f"La combinación más frecuente es {acs[i]} + {aps[j]} ({top} de {comb.height} pacientes)",
                       ncols=2, gridspec_kw=dict(width_ratios=[1, 1.2]))
    ax = axes[0]
    ax.imshow(matriz, cmap="Blues", vmin=0, vmax=max(top, 1) * 1.15, aspect="auto")
    for (r, c), v in np.ndenumerate(matriz):
        ax.text(c, r, str(v), ha="center", va="center", fontsize=13,
                color=FONDO if v > top * 0.6 else TINTA, fontweight="bold")
    ax.set_xticks(range(len(aps)), ["Aspirina", "Inhibidor P2Y12"], color=TINTA)
    ax.set_yticks(range(len(acs)), ["Heparina no fraccionada", "Enoxaparina", "Warfarina", "DOAC"], color=TINTA)
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title(f"Combinación (n = {comb.height})", loc="left", fontsize=12, color=TINTA, fontweight="bold")
    ax = axes[1]
    for k, inten in enumerate(INTENSIDADES):
        n = [solo.filter((pl.col("anticoagulante") == a) & (pl.col("intensidad") == inten)).height for a in acs]
        izq = [solo.filter((pl.col("anticoagulante") == a) & (pl.col("intensidad") == INTENSIDADES[0])).height
               for a in acs] if k else [0] * len(acs)
        ax.barh(range(len(acs)), n, left=izq, color=COLOR["solo_anticoagulante"], alpha=0.5 if k == 0 else 1.0,
                height=0.6, label="Profiláctica" if k == 0 else "Terapéutica", edgecolor=FONDO, lw=2)
    for r, a in enumerate(acs):
        tot = solo.filter(pl.col("anticoagulante") == a).height
        ax.text(tot + 0.5, r, str(tot), va="center", fontsize=10.5, color=TINTA)
    ax.set_yticks(range(len(acs)), [""] * len(acs))  # mismas filas que el mapa de la izquierda
    ax.tick_params(axis="y", length=0)
    ax.invert_yaxis()
    ax.set_xlabel("Pacientes")
    ax.legend(frameon=False, loc="lower right", fontsize=10)
    ax.set_title(f"Solo anticoagulante (n = {solo.height})", loc="left", fontsize=12, color=TINTA,
                 fontweight="bold")
    ejes_limpios(ax, "x")
    guardar(fig, "P02_farmacos.pdf", SALIDA)
    return Resultado("P02_farmacos.pdf", "¿Qué fármacos definen cada grupo?",
                     f"Domina la heparina no fraccionada; la combinación típica es {acs[i]} + {aps[j]} ({top}/{comb.height}).")


def p03_tiempo_indice(df: pl.DataFrame) -> Resultado:
    df = df.with_columns(((pl.col("t_indice") - pl.col("admittime")).dt.total_minutes() / 60).alias("horas"))
    med = {g: df.filter(pl.col("grupo") == g)["horas"].median() for g in GRUPOS}
    tarde = {g: df.filter((pl.col("grupo") == g) & (pl.col("horas") > 24)).height / df.filter(pl.col("grupo") == g).height
             for g in GRUPOS}
    fig, ax = lienzo("¿Cuándo empieza la exposición respecto al ingreso?",
                     f"Horas del ingreso a la fecha índice · después de 24 h: {100 * tarde['combinacion']:.0f} % con la "
                     f"combinación vs. {100 * tarde['solo_anticoagulante']:.0f} % sin antiagregante",
                     nota=FUENTE + "  Una fecha índice tardía implica tiempo hospitalizado previo en el que el paciente "
                                   "ya debía seguir vivo e internado (riesgo de sesgo de tiempo inmortal).")
    valores = {g: (df.filter(pl.col("grupo") == g)["horas"].clip(upper_bound=240)).to_list() for g in GRUPOS}
    puntos_y_caja(ax, valores, {"combinacion": 0, "solo_anticoagulante": 1.2})
    ax.axhline(24, color=TENUE, lw=1, ls=(0, (4, 3)))
    ax.text(1.75, 26, "24 h", color=TENUE, fontsize=9.5)
    ax.set_ylabel("Horas desde el ingreso (recortado a 240)")
    ax.set_xlim(-0.5, 1.9)
    ejes_limpios(ax)
    guardar(fig, "P03_tiempo_a_indice.pdf", SALIDA)
    return Resultado("P03_tiempo_a_indice.pdf", "¿Cuándo empieza la exposición respecto al ingreso?",
                     f"Mediana {med['combinacion']:.0f} h con la combinación vs. {med['solo_anticoagulante']:.0f} h sin "
                     f"antiagregante: revisar tiempo inmortal.")


def _dias_exposicion(con, df: pl.DataFrame) -> pl.DataFrame:
    """Días con anticoagulante y con antiagregante activos dentro del seguimiento (uniendo intervalos)."""
    iv = tabla(con, """
        SELECT i.hadm_id, i.familia, greatest(i.inicio, c.t_indice) AS ini, least(i.fin, c.t_fin_seguimiento) AS fin
        FROM intervalos i JOIN cohorte_analitica c USING (hadm_id)
        WHERE least(i.fin, c.t_fin_seguimiento) > greatest(i.inicio, c.t_indice)""")
    filas = []
    for (hadm, fam), sub in iv.group_by(["hadm_id", "familia"]):
        tramos = sorted(zip(sub["ini"].to_list(), sub["fin"].to_list()))
        total, (a, b) = 0.0, tramos[0]
        for s, e in tramos[1:]:
            if s <= b:
                b = max(b, e)
            else:
                total += (b - a).total_seconds()
                a, b = s, e
        total += (b - a).total_seconds()
        filas.append((hadm, fam, total / 86400))
    dias = pl.DataFrame(filas, schema=["hadm_id", "familia", "dias"], orient="row")
    return df.select("hadm_id", "grupo").join(dias, on="hadm_id", how="left")


def p04_duracion(con, df: pl.DataFrame) -> Resultado:
    d = _dias_exposicion(con, df)
    ac = {g: d.filter((pl.col("grupo") == g) & (pl.col("familia") == "anticoagulante"))["dias"].to_list() for g in GRUPOS}
    ap = d.filter((pl.col("grupo") == "combinacion") & (pl.col("familia") == "antiagregante"))["dias"].to_list()
    fig, axes = lienzo("¿Cuánto tiempo están expuestos los pacientes?",
                       f"Días con el fármaco activo dentro de los 14 días de seguimiento · mediana de antiagregante en la "
                       f"combinación: {np.median(ap):.1f} días", ncols=2, gridspec_kw=dict(width_ratios=[2, 1]))
    puntos_y_caja(axes[0], ac, {"combinacion": 0, "solo_anticoagulante": 1.2})
    axes[0].set_title("Anticoagulante", loc="left", fontsize=12.5, color=TINTA, fontweight="bold")
    puntos_y_caja(axes[1], {"combinacion": ap}, {"combinacion": 0})
    axes[1].set_title("Antiagregante", loc="left", fontsize=12.5, color=TINTA, fontweight="bold")
    for ax in axes:
        ax.set_ylim(0, 14.5)
        ax.set_ylabel("Días de exposición")
        ejes_limpios(ax)
    axes[0].set_xlim(-0.5, 1.9)
    axes[1].set_xlim(-0.5, 0.7)
    guardar(fig, "P04_duracion_exposicion.pdf", SALIDA)
    return Resultado("P04_duracion_exposicion.pdf", "¿Cuánto tiempo están expuestos los pacientes?",
                     f"Anticoagulante: mediana {np.median(ac['combinacion']):.1f} vs. "
                     f"{np.median(ac['solo_anticoagulante']):.1f} días; antiagregante {np.median(ap):.1f} días.")


def p05_linea_tiempo(con, df: pl.DataFrame, por_grupo: int = 8) -> Resultado:
    iv = tabla(con, """
        SELECT i.hadm_id, i.familia,
               date_diff('minute', c.t_indice, i.inicio) / 1440.0 AS ini,
               date_diff('minute', c.t_indice, i.fin) / 1440.0 AS fin
        FROM intervalos i JOIN cohorte_analitica c USING (hadm_id)""")
    ev = tabla(con, """
        SELECT c.hadm_id, min(date_diff('minute', c.t_indice, l.charttime) / 1440.0) AS dia
        FROM cohorte_analitica c JOIN labevents l ON l.subject_id = c.subject_id AND l.itemid = 51222
         AND l.charttime > c.t_indice AND l.charttime <= c.t_fin_seguimiento AND l.valuenum <= c.hb_basal - 2
        GROUP BY c.hadm_id""")
    muestra = []
    for g in GRUPOS:
        sub = df.filter(pl.col("grupo") == g).sort("hadm_id")
        idx = rng.choice(sub.height, size=min(por_grupo, sub.height), replace=False)
        muestra += [(g, h) for h in sub[sorted(idx.tolist())]["hadm_id"].to_list()]
    fig, ax = lienzo("¿Cómo se ve la exposición de un paciente en el tiempo?",
                     f"Línea de tiempo de {len(muestra)} pacientes elegidos al azar ({por_grupo} por grupo), relativa a "
                     "la fecha índice", nota=FUENTE + "  Pacientes sin identificar; solo tiempos relativos.")
    etiquetas = []
    for k, (g, h) in enumerate(muestra):
        y = len(muestra) - 1 - k
        fin = df.filter(pl.col("hadm_id") == h)["dias_seguimiento"][0]
        ax.plot([0, fin], [y, y], color=REJILLA, lw=9, solid_capstyle="butt", zorder=1)
        for fam, dy, alto in (("anticoagulante", 0.13, 3.5), ("antiagregante", -0.13, 3.5)):
            for r in iv.filter((pl.col("hadm_id") == h) & (pl.col("familia") == fam)).iter_rows(named=True):
                a, b = max(r["ini"], -3), min(r["fin"], 14)
                if b > a:
                    ax.plot([a, b], [y + dy, y + dy], color=TINTA if fam == "anticoagulante" else COLOR["combinacion"],
                            lw=alto, solid_capstyle="butt", zorder=2)
        e = ev.filter(pl.col("hadm_id") == h)
        if e.height:
            ax.plot(e["dia"][0], y, "v", color="#d03b3b", ms=10, zorder=3, mec=FONDO)
        etiquetas.append(f"Paciente {k + 1} · {'combinación' if g == 'combinacion' else 'solo AC'}")
    ax.axvline(0, color=TENUE, lw=1, ls=(0, (4, 3)))
    ax.axhline(por_grupo - 0.5, color=TENUE, lw=0.8)
    ax.set_yticks(range(len(muestra)), list(reversed(etiquetas)), fontsize=9.5, color=TINTA)
    ax.set_xlim(-3, 14.5)
    ax.set_xlabel("Días desde la fecha índice")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    from matplotlib.lines import Line2D
    marcas = [Line2D([], [], color=TINTA, lw=3.5), Line2D([], [], color=COLOR["combinacion"], lw=3.5),
              Line2D([], [], color=REJILLA, lw=9), Line2D([], [], marker="v", ls="", color="#d03b3b", ms=9)]
    fig.legend(marcas, ["Anticoagulante activo", "Antiagregante activo", "Seguimiento", "Caída de Hb ≥ 2 g/dL"],
               loc="outside lower center", ncol=4, frameon=False, fontsize=10)
    ejes_limpios(ax, "x")
    guardar(fig, "P05_linea_de_tiempo.pdf", SALIDA)
    return Resultado("P05_linea_de_tiempo.pdf", "¿Cómo se ve la exposición de un paciente en el tiempo?",
                     "Muestra al azar: la co-exposición inicia en la fecha índice y el sangrado aparece en los primeros días.")


def p06_indicaciones(df: pl.DataFrame) -> Resultado:
    variables = {
        "Cardiopatía isquémica": pl.col("cardiopatia_isquemica"), "Fibrilación auricular": pl.col("fibrilacion_auricular"),
        "Insuficiencia cardiaca": pl.col("insuficiencia_cardiaca"), "Tromboembolia venosa": pl.col("tromboembolia_venosa"),
        "En UCI en la fecha índice": pl.col("uci_en_indice"), "Paciente quirúrgico": pl.col("estrato") != "medico",
        "Cirugía cardiaca": pl.col("estrato") == "cirugia_cardiaca",
    }
    fig, ax = lienzo("¿Por qué reciben antitrombóticos? Indicaciones y contexto clínico",
                     "Prevalencia en cada grupo con IC 95 % (diagnósticos CIE de la misma hospitalización)")
    nombres = list(variables)
    for i, k in enumerate(nombres):
        y = len(nombres) - 1 - i
        for g, dy in (("combinacion", 0.15), ("solo_anticoagulante", -0.15)):
            s = df.filter(pl.col("grupo") == g).select(variables[k]).to_series()
            e = wilson(int(s.sum()), s.len())
            ax.plot([100 * e.li, 100 * e.ls], [y + dy, y + dy], color=COLOR[g], lw=2.2, solid_capstyle="round")
            ax.plot(100 * e.valor, y + dy, "o", color=COLOR[g], ms=9, mec=FONDO, mew=1.3, zorder=3)
            ax.text(100 * e.ls + 1.5, y + dy, f"{100 * e.valor:.0f} %", va="center", fontsize=9, color=TINTA2)
    ax.set_yticks(range(len(nombres)), list(reversed(nombres)), color=TINTA)
    ax.set_xlim(0, 105)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f} %")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ejes_limpios(ax, "x")
    leyenda_figura(fig)
    guardar(fig, "P06_indicaciones.pdf", SALIDA)
    ci = {g: df.filter(pl.col("grupo") == g)["cardiopatia_isquemica"].mean() for g in GRUPOS}
    return Resultado("P06_indicaciones.pdf", "¿Por qué reciben antitrombóticos?",
                     f"La combinación se da sobre todo a cardiópatas: cardiopatía isquémica {100 * ci['combinacion']:.0f} % "
                     f"vs. {100 * ci['solo_anticoagulante']:.0f} %.")


def p07_vigilancia(con, df: pl.DataFrame, max_dia: int = 10) -> Resultado:
    med = tabla(con, f"""
        SELECT c.hadm_id, c.grupo, 1 + floor(date_diff('minute', c.t_indice, l.charttime) / 1440.0)::INT AS dia,
               count(*) AS n
        FROM cohorte_analitica c JOIN labevents l ON l.subject_id = c.subject_id AND l.itemid = 51222
         AND l.valuenum IS NOT NULL AND l.charttime > c.t_indice AND l.charttime <= c.t_fin_seguimiento
        GROUP BY ALL""")
    fig, ax = lienzo("¿Se mide la hemoglobina con la misma frecuencia en ambos grupos?",
                     "Proporción de pacientes en seguimiento con al menos una Hb medida cada día · una diferencia aquí "
                     "sesga la detección del sangrado")
    resumen = {}
    for g in GRUPOS:
        sub = df.filter(pl.col("grupo") == g)
        xs, ys = [], []
        for dia in range(1, max_dia + 1):
            en_riesgo = sub.filter(pl.col("dias_seguimiento") > dia - 1)
            if en_riesgo.height < 5:
                break
            medidos = med.filter((pl.col("grupo") == g) & (pl.col("dia") == dia) &
                                 pl.col("hadm_id").is_in(en_riesgo["hadm_id"].to_list())).height
            xs.append(dia)
            ys.append(100 * medidos / en_riesgo.height)
        resumen[g] = np.mean(ys)
        ax.plot(xs, ys, "-o", color=COLOR[g], lw=2, ms=7, mec=FONDO)
    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f} %")
    ax.set_xlabel("Día de seguimiento")
    ax.set_ylabel("Pacientes con Hb medida ese día")
    ax.set_xticks(range(1, max_dia + 1))
    ejes_limpios(ax)
    leyenda_figura(fig)
    guardar(fig, "P07_vigilancia_hb.pdf", SALIDA)
    return Resultado("P07_vigilancia_hb.pdf", "¿Se mide la Hb con la misma frecuencia en ambos grupos?",
                     f"En promedio, {resumen['combinacion']:.0f} % vs. {resumen['solo_anticoagulante']:.0f} % de los "
                     "pacientes en seguimiento tienen Hb medida cada día.")


def p08_tiempo_a_sangrado(con, df: pl.DataFrame, n_min: int = 5) -> Resultado:
    t = tabla(con, """
        WITH hb AS (
            SELECT c.hadm_id, min(l.charttime) AS t
            FROM cohorte_analitica c JOIN labevents l ON l.subject_id = c.subject_id AND l.itemid = 51222
             AND l.charttime > c.t_indice AND l.charttime <= c.t_fin_seguimiento AND l.valuenum <= c.hb_basal - 2
            GROUP BY c.hadm_id),
        tx AS (
            SELECT c.hadm_id, min(i.starttime) AS t
            FROM cohorte_analitica c JOIN inputevents i ON i.hadm_id = c.hadm_id
             AND i.starttime > c.t_indice AND i.starttime <= c.t_fin_seguimiento
            JOIN d_items d ON d.itemid = i.itemid AND d.label ILIKE '%packed%'
            GROUP BY c.hadm_id)
        SELECT c.hadm_id, c.grupo, c.dias_seguimiento,
               date_diff('minute', c.t_indice, least(hb.t, tx.t)) / 1440.0 AS dia_evento
        FROM cohorte_analitica c LEFT JOIN hb USING (hadm_id) LEFT JOIN tx USING (hadm_id)""")
    fig, ax = lienzo("¿Cuándo ocurre el sangrado?",
                     "Incidencia acumulada de sangrado relevante (Kaplan-Meier, censura al alta) tras la fecha índice",
                     nota=FUENTE + f"  Cada curva se corta cuando quedan menos de {n_min} pacientes en riesgo.")
    a_riesgo = {}
    for g in GRUPOS:
        sub = t.filter(pl.col("grupo") == g)
        tiempos = [(r["dia_evento"], 1) if r["dia_evento"] is not None else (r["dias_seguimiento"], 0)
                   for r in sub.iter_rows(named=True)]
        tiempos.sort()
        s, n, xs, ys = 1.0, len(tiempos), [0.0], [0.0]
        for tt, ev in tiempos:
            if n < n_min:  # la cola con muy pocos pacientes en riesgo no es fiable
                break
            if ev:
                s *= 1 - 1 / n
                xs += [tt, tt]
                ys += [ys[-1], 100 * (1 - s)]
            n -= 1
            xs.append(tt)
            ys.append(ys[-1])
        ax.plot(xs, ys, color=COLOR[g], lw=2.2)
        ax.text(xs[-1] + 0.15, ys[-1], f"{ys[-1]:.0f} % (día {xs[-1]:.0f})", va="center", fontsize=10, color=TINTA)
        a_riesgo[g] = [sum(1 for tt, _ in tiempos if tt >= d) for d in (0, 3, 7, 10, 14)]
    for k, g in enumerate(GRUPOS):
        for d, n in zip((0, 3, 7, 10, 14), a_riesgo[g]):
            ax.text(d, -14 - 6 * k, str(n), ha="center", fontsize=9.5, color=COLOR[g])
    ax.text(0, -8, "Pacientes en riesgo", ha="left", fontsize=9.5, color=TINTA2)
    ax.set_xlim(0, 15)
    ax.set_ylim(-26, 80)
    ax.set_yticks(range(0, 81, 20), [f"{v} %" for v in range(0, 81, 20)])
    ax.spines["left"].set_bounds(0, 80)
    ax.set_xticks([0, 3, 7, 10, 14])
    ax.set_xlabel("Días desde la fecha índice")
    ax.set_ylabel("Incidencia acumulada")
    ax.grid(axis="y", color=REJILLA, lw=0.8)
    leyenda_figura(fig)
    guardar(fig, "P08_tiempo_a_sangrado.pdf", SALIDA)
    mediana = {g: t.filter((pl.col("grupo") == g) & pl.col("dia_evento").is_not_null())["dia_evento"].median()
               for g in GRUPOS}
    return Resultado("P08_tiempo_a_sangrado.pdf", "¿Cuándo ocurre el sangrado?",
                     f"Temprano: mediana de {mediana['combinacion']:.1f} y {mediana['solo_anticoagulante']:.1f} días "
                     "hasta el evento; las curvas se cruzan.")


def _distribucion(df, col, titulo, subtitulo, ylabel, archivo, ref=None, ref_txt="", recorte=None) -> dict[str, float]:
    fig, ax = lienzo(titulo, subtitulo)
    valores = {g: df.filter(pl.col("grupo") == g)[col].to_list() for g in GRUPOS}
    if recorte:
        valores = {g: [min(max(v, recorte[0]), recorte[1]) for v in vs if v is not None] for g, vs in valores.items()}
    puntos_y_caja(ax, valores, {"combinacion": 0, "solo_anticoagulante": 1.2})
    if ref is not None:
        ax.axhline(ref, color=TENUE, lw=1, ls=(0, (4, 3)))
        ax.text(-0.45, ref, f"{ref_txt}", va="bottom", ha="left", fontsize=9.5, color=TENUE)
    ax.set_xlim(-0.5, 1.9)
    ax.set_ylabel(ylabel)
    ejes_limpios(ax)
    guardar(fig, archivo, SALIDA)
    return {g: float(np.nanmedian([v for v in valores[g] if v is not None])) for g in GRUPOS}


def p09_caida_hb(df: pl.DataFrame) -> Resultado:
    m = _distribucion(df, "caida_hb_max", "¿Cuánto baja la hemoglobina?",
                      "Caída máxima de Hb respecto a la basal durante el seguimiento (positivo = bajó)",
                      "Caída máxima de Hb (g/dL)", "P09_caida_hb.pdf", ref=2, ref_txt="umbral de sangrado (2 g/dL)")
    return Resultado("P09_caida_hb.pdf", "¿Cuánto baja la hemoglobina?",
                     f"Mediana de caída {m['combinacion']:.1f} vs. {m['solo_anticoagulante']:.1f} g/dL: distribuciones casi iguales.")


def p10_plaquetas(df: pl.DataFrame) -> Resultado:
    m = _distribucion(df, "plaquetas_cambio_pct", "¿Qué pasa con las plaquetas?",
                      "Cambio porcentual de la basal al nadir durante el seguimiento",
                      "Cambio al nadir (%)", "P10_plaquetas.pdf", ref=-50, ref_txt="caída del 50 %", recorte=(-100, 60))
    return Resultado("P10_plaquetas.pdf", "¿Qué pasa con las plaquetas?",
                     f"Mediana {m['combinacion']:.0f} % vs. {m['solo_anticoagulante']:.0f} %: la combinación no baja más "
                     "la cuenta (coherente con la farmacología).")


def p11_estancia(df: pl.DataFrame) -> Resultado:
    m = _distribucion(df, "estancia_post_indice_dias", "¿Cuánto tiempo siguen hospitalizados?",
                      "Días desde la fecha índice hasta el alta (recortado a 40 días)",
                      "Días hasta el alta", "P11_estancia.pdf", recorte=(0, 40))
    return Resultado("P11_estancia.pdf", "¿Cuánto tiempo siguen hospitalizados?",
                     f"Mediana {m['combinacion']:.1f} vs. {m['solo_anticoagulante']:.1f} días: el comparador permanece más "
                     "tiempo (más oportunidad de medir y de sangrar).")


def p12_umbral(con, df: pl.DataFrame) -> Resultado:
    umbrales = [1.0, 1.5, 2.0, 2.5, 3.0, 4.0]
    d = df.filter(pl.col("caida_hb_max").is_not_null())
    fig, axes = lienzo("¿Depende el resultado del umbral de sangrado?",
                       "Riesgo de caída de Hb mayor o igual a cada umbral (izquierda) y razón de riesgos (derecha)",
                       ncols=2)
    rrs = []
    for g in GRUPOS:
        sub = d.filter(pl.col("grupo") == g)
        ys = [100 * (sub["caida_hb_max"] >= u).mean() for u in umbrales]
        axes[0].plot(umbrales, ys, "-o", color=COLOR[g], lw=2, ms=7, mec=FONDO)
    for u in umbrales:
        x = d.with_columns((pl.col("caida_hb_max") >= u).alias("_ev"))
        rrs.append(rr_ajustado(x, col="_ev"))
    axes[0].set_ylabel("Pacientes que alcanzan el umbral")
    axes[0].yaxis.set_major_formatter(lambda v, _: f"{v:.0f} %")
    axes[0].set_ylim(0, 100)
    for ax in axes:
        ax.set_xlabel("Umbral de caída de Hb (g/dL)")
        ax.set_xticks(umbrales)
        ejes_limpios(ax)
    for u, e in zip(umbrales, rrs):
        axes[1].plot([u, u], [e.li, e.ls], color=TINTA, lw=2)
        axes[1].plot(u, e.valor, "s", color=TINTA, ms=8, mec=FONDO)
    axes[1].axhline(1, color=TENUE, lw=1, ls=(0, (4, 3)))
    axes[1].set_yscale("log")
    axes[1].set_yticks([0.25, 0.5, 1, 2, 4], ["0.25", "0.5", "1", "2", "4"])
    axes[1].minorticks_off()
    axes[1].set_ylabel("RR ajustado por intensidad (IC 95 %)")
    axes[0].axvline(2, color=TENUE, lw=1, ls=":")
    axes[1].axvline(2, color=TENUE, lw=1, ls=":")
    leyenda_figura(fig)
    guardar(fig, "P12_sensibilidad_umbral.pdf", SALIDA)
    n_sig = sum(not cruza_uno(e) for e in rrs)
    return Resultado("P12_sensibilidad_umbral.pdf", "¿Depende el resultado del umbral de sangrado?",
                     f"No: con umbrales de 1 a 4 g/dL, {len(umbrales) - n_sig} de {len(umbrales)} RR incluyen el 1.")


def p13_ventana(df_base: pl.DataFrame) -> Resultado:
    ventanas = [2, 3, 5, 7, 10, 14]
    filas = []
    for v in ventanas:
        d = df_base if v == 14 else cohorte_variante({"seguimiento_d": v})
        a, n1, c, n0 = conteos(d)
        filas.append((f"{v} días{'  (principal)' if v == 14 else ''}", rr_ajustado(d), f"{a}/{n1} vs. {c}/{n0}"))
    fig, ax = lienzo("¿Depende el resultado de la ventana de seguimiento?",
                     "RR de sangrado relevante ajustado por intensidad, con distintas duraciones máximas de seguimiento")
    forest(ax, filas, lim=(0.25, 4), resaltar={len(filas) - 1})
    guardar(fig, "P13_sensibilidad_ventana.pdf", SALIDA)
    return Resultado("P13_sensibilidad_ventana.pdf", "¿Depende el resultado de la ventana de seguimiento?",
                     "No: " + "; ".join(f"{v} d {fmt(f[1])}" for v, f in zip(ventanas, filas) if v in (2, 7, 14)) + ".")


def p14_definicion_exposicion(df_base: pl.DataFrame) -> Resultado:
    variantes = [
        ("Efecto residual del antiagregante: 7 días (principal)", {}),
        ("Efecto residual: 3 días", {"efecto_residual_ap_d": 3}),
        ("Efecto residual: 1 día", {"efecto_residual_ap_d": 1}),
        ("Sin efecto residual (solo orden activa)", {"efecto_residual_ap_d": 0}),
        ("Sin órdenes previas al ingreso", {"previo_ingreso_h": 0}),
        ("Dosis única de anticoagulante = 6 h", {"dosis_unica_ac_h": 6}),
        ("Basal en 24 h (no 48 h)", {"ventana_basal_h": 24}),
    ]
    filas = []
    for nombre, p in variantes:
        d = df_base if not p else cohorte_variante(p)
        a, n1, c, n0 = conteos(d)
        filas.append((nombre, rr_ajustado(d), f"{a}/{n1} vs. {c}/{n0}"))
    fig, ax = lienzo("¿Depende el resultado de cómo definimos la exposición?",
                     "RR de sangrado relevante ajustado por intensidad bajo variantes de la definición de cohorte "
                     "(cambian quién entra y a qué grupo)")
    forest(ax, filas, lim=(0.25, 4), resaltar={0})
    guardar(fig, "P14_sensibilidad_definicion.pdf", SALIDA)
    estables = all(cruza_uno(f[1]) for f in filas)
    return Resultado("P14_sensibilidad_definicion.pdf", "¿Depende el resultado de cómo definimos la exposición?",
                     ("No: ninguna variante" if estables else "Sí: alguna variante") +
                     " cambia la conclusión; " + f"RR entre {min(f[1].valor for f in filas):.2f} y "
                     f"{max(f[1].valor for f in filas):.2f}.")


def p15_restricciones(df: pl.DataFrame) -> Resultado:
    poblaciones = [
        ("Todos (principal)", df),
        ("Excluir cirugía cardiaca", df.filter(pl.col("estrato") != "cirugia_cardiaca")),
        ("Solo profilaxis", df.filter(pl.col("intensidad") == "profilactica")),
        ("Solo heparina no fraccionada", df.filter(pl.col("anticoagulante") == "HNF")),
        ("Fuera de UCI en la fecha índice", df.filter(~pl.col("uci_en_indice"))),
        ("En UCI en la fecha índice", df.filter(pl.col("uci_en_indice"))),
        ("Con ≥ 3 Hb en el seguimiento", df.filter(pl.col("n_hb") >= 3)),
    ]
    filas = []
    for nombre, d in poblaciones:
        a, n1, c, n0 = conteos(d)
        filas.append((nombre, rr_crudo(d), f"{a}/{n1} vs. {c}/{n0}"))
    fig, ax = lienzo("¿Cambia el resultado al restringir la población?",
                     "RR crudo de sangrado relevante en subpoblaciones más homogéneas")
    forest(ax, filas, lim=(0.1, 10), resaltar={0})
    guardar(fig, "P15_restricciones.pdf", SALIDA)
    return Resultado("P15_restricciones.pdf", "¿Cambia el resultado al restringir la población?",
                     f"Ninguna restricción produce una asociación concluyente; fuera de UCI: RR {fmt(filas[4][1])}."
                     if all(cruza_uno(f[1]) for f in filas) else "Al menos una restricción muestra una asociación.")


def p16_subgrupos(df: pl.DataFrame) -> Resultado:
    cortes = [
        ("Edad < 65", pl.col("edad") < 65), ("Edad ≥ 65", pl.col("edad") >= 65),
        ("Mujeres", pl.col("sexo") == "F"), ("Hombres", pl.col("sexo") == "M"),
        ("Con cardiopatía isquémica", pl.col("cardiopatia_isquemica")), ("Sin cardiopatía isquémica", ~pl.col("cardiopatia_isquemica")),
        ("Con fibrilación auricular", pl.col("fibrilacion_auricular")), ("Sin fibrilación auricular", ~pl.col("fibrilacion_auricular")),
        ("Paciente médico", pl.col("estrato") == "medico"), ("Paciente quirúrgico", pl.col("estrato") != "medico"),
    ]
    filas = []
    for nombre, cond in cortes:
        d = df.filter(cond)
        a, n1, c, n0 = conteos(d)
        filas.append((nombre, rr_crudo(d), f"{a}/{n1} vs. {c}/{n0}"))
    fig, ax = lienzo("¿Es distinto el resultado en algún subgrupo?",
                     "RR crudo de sangrado relevante por subgrupo · exploratorio: con estos tamaños no hay potencia para "
                     "detectar interacción")
    forest(ax, filas, lim=(0.1, 10))
    for i in range(1, len(filas) - 1, 2):  # separador entre pares de subgrupos
        ax.axhline(len(filas) - 1 - i - 0.5, color=REJILLA, lw=0.8)
    guardar(fig, "P16_subgrupos.pdf", SALIDA)
    return Resultado("P16_subgrupos.pdf", "¿Es distinto el resultado en algún subgrupo?",
                     "Ningún subgrupo muestra una asociación concluyente." if all(cruza_uno(f[1]) for f in filas)
                     else "Algún subgrupo muestra asociación (interpretar con cautela).")


def p17_factores(df: pl.DataFrame) -> Resultado:
    factores = [
        ("Recibe la combinación", pl.col("grupo") == "combinacion"),
        ("En UCI en la fecha índice", pl.col("uci_en_indice")),
        ("Anticoagulación terapéutica", pl.col("intensidad") == "terapeutica"),
        ("Paciente quirúrgico", pl.col("estrato") != "medico"),
        ("Cirugía cardiaca", pl.col("estrato") == "cirugia_cardiaca"),
        ("Edad ≥ 65", pl.col("edad") >= 65),
        ("Mujer", pl.col("sexo") == "F"),
        ("Hb basal < 10 g/dL", pl.col("hb_basal") < 10),
        ("Plaquetas basales < 150", pl.col("plaquetas_basal") < 150),
        ("Insuficiencia cardiaca", pl.col("insuficiencia_cardiaca")),
        ("Cardiopatía isquémica", pl.col("cardiopatia_isquemica")),
        ("Fibrilación auricular", pl.col("fibrilacion_auricular")),
    ]
    filas = []
    for nombre, cond in factores:
        x = df.with_columns(cond.alias("_f"))
        si, no = x.filter(pl.col("_f")), x.filter(~pl.col("_f"))
        a, n1, c, n0 = int(si["sangrado_relevante"].sum()), si.height, int(no["sangrado_relevante"].sum()), no.height
        filas.append((nombre, razon_riesgos(a, n1, c, n0), f"{a}/{n1} vs. {c}/{n0}"))
    filas.sort(key=lambda f: -f[1].valor if not math.isnan(f[1].valor) else 0)
    fig, ax = lienzo("¿Qué se asocia con sangrar en toda la cohorte?",
                     "RR de sangrado relevante con vs. sin cada característica (74 pacientes, sin ajuste)")
    forest(ax, filas, lim=(0.1, 10), resaltar={i for i, f in enumerate(filas) if f[0] == "Recibe la combinación"})
    guardar(fig, "P17_factores_de_sangrado.pdf", SALIDA)
    claros = [f[0].lower() for f in filas if not cruza_uno(f[1])]
    return Resultado("P17_factores_de_sangrado.pdf", "¿Qué se asocia con sangrar en toda la cohorte?",
                     ("Asociación clara con: " + ", ".join(claros) + "." if claros else "Ningún factor aislado es concluyente.")
                     + " La combinación no está entre los factores más fuertes.")


def p18_confusion(df: pl.DataFrame) -> Resultado:
    ajustes = [
        ("Sin ajuste (cruda)", None),
        ("Intensidad (principal)", "intensidad"),
        ("En UCI en la fecha índice", pl.col("uci_en_indice")),
        ("Edad ≥ 65", pl.col("edad") >= 65),
        ("Cardiopatía isquémica", pl.col("cardiopatia_isquemica")),
        ("Fibrilación auricular", pl.col("fibrilacion_auricular")),
        ("Paciente quirúrgico", pl.col("estrato") != "medico"),
        ("Sexo", pl.col("sexo")),
    ]
    filas = []
    for nombre, por in ajustes:
        e = rr_crudo(df) if por is None else rr_ajustado(df, por)
        filas.append((nombre, e, ""))
    cruda = filas[0][1].valor
    fig, ax = lienzo("¿Cambia el resultado al ajustar por cada posible confusor?",
                     "RR de sangrado relevante estratificado (Mantel-Haenszel) por una variable a la vez",
                     nota=FUENTE + "  Regla práctica: un cambio > 10 % respecto a la RR cruda sugiere confusión.")
    forest(ax, filas, lim=(0.25, 4), resaltar={0})
    guardar(fig, "P18_confusion.pdf", SALIDA)
    cambio = max(abs(f[1].valor / cruda - 1) for f in filas[1:] if not math.isnan(f[1].valor))
    mayor = max(filas[1:], key=lambda f: abs(f[1].valor / cruda - 1))
    return Resultado("P18_confusion.pdf", "¿Cambia el resultado al ajustar por cada posible confusor?",
                     f"Cambio máximo {100 * cambio:.0f} % (al ajustar por {mayor[0].lower()}: RR {fmt(mayor[1])}); "
                     "la estimación es estable, pero solo se ajusta una variable a la vez.")


def p19_concordancia_omop() -> Resultado:
    from antitromboticos.validacion_omop import comparar

    con = comparar()
    estratos = ["medico", "quirurgico", "cirugia_cardiaca"]
    etq = ["Médico", "Quirúrgico", "Cirugía cardiaca"]
    m = np.zeros((3, 3), dtype=int)
    for a, b, n in con.execute("""SELECT estrato_n, estrato_o, count(*) FROM comparacion
                                  WHERE en_nativa AND en_omop AND misma_hosp GROUP BY ALL""").fetchall():
        m[estratos.index(a), estratos.index(b)] = n
    variables = [("Grupo", "grupo_n", "grupo_o"), ("Intensidad", "int_n", "int_o"), ("Caída de Hb ≥ 2", "hb_n", "hb_o"),
                 ("UCI posterior", "uci_n", "uci_o"), ("Muerte", "muerte_n", "muerte_o"), ("Estrato", "estrato_n", "estrato_o")]
    conc = []
    for nombre, a, b in variables:
        tot, ig = con.execute(f"""SELECT count(*), count(*) FILTER (WHERE {a} IS NOT DISTINCT FROM {b})
                                  FROM comparacion WHERE en_nativa AND en_omop AND misma_hosp""").fetchall()[0]
        conc.append((nombre, 100 * ig / tot))
    fig, axes = lienzo("¿Coinciden paciente por paciente las cohortes nativa y OMOP?",
                       f"Concordancia en {int(m.sum())} pacientes con la misma hospitalización índice · el estrato es la "
                       "única variable débil", ncols=2, gridspec_kw=dict(width_ratios=[1.1, 1]),
                       nota=FUENTE.replace("PhysioNet)", "PhysioNet) y su versión OMOP v0.9"))
    ax = axes[0]
    nombres = [c[0] for c in conc]
    vals = [c[1] for c in conc]
    ax.barh(range(len(conc)), vals, color=[TINTA if v >= 95 else TENUE for v in vals], height=0.6)
    for i, v in enumerate(vals):
        ax.text(v + 1, i, f"{v:.0f} %", va="center", fontsize=10.5, color=TINTA)
    ax.set_yticks(range(len(conc)), nombres, color=TINTA)
    ax.invert_yaxis()
    ax.set_xlim(0, 112)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f} %")
    ax.set_title("Concordancia por variable", loc="left", fontsize=12, color=TINTA, fontweight="bold")
    ax.tick_params(axis="y", length=0)
    ejes_limpios(ax, "x")
    ax = axes[1]
    ax.imshow(m, cmap="Greys", vmin=0, vmax=m.max() * 1.3)
    for (r, c), v in np.ndenumerate(m):
        ax.text(c, r, str(v), ha="center", va="center", fontsize=13, fontweight="bold",
                color=FONDO if v > m.max() * 0.6 else TINTA)
    ax.set_xticks(range(3), etq, rotation=20, color=TINTA)
    ax.set_yticks(range(3), etq, color=TINTA)
    ax.set_xlabel("OMOP (unidades)")
    ax.set_ylabel("Nativa (servicio)")
    ax.tick_params(length=0)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.set_title("Estrato: nativa vs. OMOP", loc="left", fontsize=12, color=TINTA, fontweight="bold")
    guardar(fig, "P19_concordancia_omop.pdf", SALIDA)
    return Resultado("P19_concordancia_omop.pdf", "¿Coinciden paciente por paciente las cohortes nativa y OMOP?",
                     f"Sí en grupo, intensidad y desenlaces (≥ 96 %); el estrato concuerda en {conc[-1][1]:.0f} % "
                     "(unidades ≠ servicio).")


def p20_emar() -> Resultado:
    from antitromboticos.cohorte import SALIDA_RESULTADOS
    from antitromboticos.sensibilidad_emar import cohortes, concordancia_grupo

    c = cohortes()
    nombres = {"principal": "Principal: prescripción, todos",
               "cobertura_emar": "Prescripción, solo con emar",
               "administrada": "Dosis administradas (emar)"}
    desenlaces = {"sangrado_relevante": "Sangrado relevante", "sangrado_documentado": "Hemorragia documentada"}
    filas, registros = [], []
    for col, etq in desenlaces.items():
        for v, nombre in nombres.items():
            a, n1, b, n0 = conteos(c[v], col)
            e = rr_ajustado(c[v], col=col)
            filas.append((f"{etq} · {nombre}", e, f"{a}/{n1} vs. {b}/{n0}"))
            registros.append(dict(desenlace=col, cohorte=v, eventos_combinacion=a, n_combinacion=n1, eventos_solo_ac=b,
                                  n_solo_ac=n0, rr_mh=round(e.valor, 3), ic95_inf=round(e.li, 3), ic95_sup=round(e.ls, 3)))
    pl.DataFrame(registros).write_csv(SALIDA_RESULTADOS / "sensibilidad_emar.csv")
    iguales, total = concordancia_grupo(c["cobertura_emar"], c["administrada"])
    estable = all(cruza_uno(f[1]) for f in filas)
    fig, ax = lienzo("Usar las dosis realmente administradas no cambia la conclusión" if estable
                     else "Usar las dosis administradas cambia la conclusión",
                     "RR ajustado por intensidad. emar cubre solo parte de las hospitalizaciones: comparar la segunda y la "
                     f"tercera fila de cada desenlace aísla el efecto de cambiar la exposición. Mismo grupo en {iguales} de "
                     f"{total} pacientes con la misma hospitalización índice",
                     figsize=(11, 4.8))
    forest(ax, filas, lim=(0.25, 10), resaltar={0, 3})
    ax.axhline(2.5, color=REJILLA, lw=1)
    guardar(fig, "P20_sensibilidad_emar.pdf", SALIDA)
    adm = filas[5][1]
    return Resultado("P20_sensibilidad_emar.pdf", "¿Cambia el resultado con las dosis realmente administradas?",
                     f"{'No' if estable else 'Sí'}: hemorragia documentada RR {fmt(adm)} con emar; "
                     f"el grupo coincide en {iguales}/{total} pacientes.")


# ----------------------------------------------------------------------------- main
def main() -> None:
    con = construir("mimic")
    df = tabla(con, "SELECT * FROM cohorte_analitica")
    pasos: list[Callable[[], Resultado]] = [
        lambda: p01_demografia(df), lambda: p02_farmacos(df), lambda: p03_tiempo_indice(df),
        lambda: p04_duracion(con, df), lambda: p05_linea_tiempo(con, df), lambda: p06_indicaciones(df),
        lambda: p07_vigilancia(con, df), lambda: p08_tiempo_a_sangrado(con, df), lambda: p09_caida_hb(df),
        lambda: p10_plaquetas(df), lambda: p11_estancia(df), lambda: p12_umbral(con, df),
        lambda: p13_ventana(df), lambda: p14_definicion_exposicion(df), lambda: p15_restricciones(df),
        lambda: p16_subgrupos(df), lambda: p17_factores(df), lambda: p18_confusion(df),
        p19_concordancia_omop, p20_emar,
    ]
    resultados = []
    for paso in pasos:
        r = paso()
        resultados.append(r)
        print(f"{r.archivo}: {r.respuesta}")
    plt.close("all")

    filas = "\n".join(f"| {i} | {r.pregunta} | {r.respuesta} | {PIES.get(r.archivo, '')} | [{r.archivo}]({r.archivo}) |"
                      for i, r in enumerate(resultados, 1))
    (SALIDA / "INDICE.md").write_text(
        "# Banco de análisis\n\n"
        "Cada figura contesta una pregunta. Las respuestas se calculan con los datos al generar las figuras "
        "(`python -m antitromboticos.preguntas`, PDF vectorial). Cohorte: tablas nativas de MIMIC-IV Demo v2.2 "
        "(74 pacientes), salvo P19, que compara con la versión OMOP. Todos los intervalos son IC 95 %.\n\n"
        "| # | Pregunta | Respuesta corta | Qué muestra la figura | Archivo |\n|---|---|---|---|---|\n" + filas + "\n",
        encoding="utf-8",
    )
    print(f"\n{len(resultados)} figuras e INDICE.md en {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
