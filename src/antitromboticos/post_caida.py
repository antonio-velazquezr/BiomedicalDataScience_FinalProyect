"""¿Qué pasa después de la primera caída de Hb, con y sin antiagregante?

Compara a los pacientes desde la primera caída de Hb >= 2 g/dL (t0) hasta el alta o 7 días.
Estadística: Fisher exacta, diferencia de riesgos (Newcombe), Mann-Whitney con Hodges-Lehmann,
Kaplan-Meier con log-rank, corrección de Holm y análisis de potencia.

Advertencia de diseño: condicionar a un evento posterior a la exposición introduce sesgo de
selección (*index event bias*), y estos fármacos no se indican para recuperar la Hb. Sin eventos
trombóticos fechados no se puede medir su beneficio.
"""

from __future__ import annotations

import math

import numpy as np
import polars as pl
from scipy import stats

from antitromboticos.cohorte import RAIZ
from antitromboticos.estadistica import (
    Estimacion, Z95, hodges_lehmann, holm, n_por_grupo, newcombe_rd, ols_hc3, potencia_dos_proporciones, wilson,
)
from antitromboticos.figuras import COLOR, FONDO, GRUPOS, NOMBRE, TENUE, TINTA, TINTA2, guardar, leyenda_figura, lienzo, tabla
from antitromboticos.preguntas import ejes_limpios, puntos_y_caja

SALIDA = RAIZ / "figuras" / "historia"
BINARIOS = {
    "recupera_hb": "Recupera Hb (≥ basal − 1 g/dL)",
    "nueva_caida": "Nueva caída ≥ 1 g/dL",
    "transfusion_post": "Transfusión de glóbulos rojos",
    "uci_post": "Ingreso posterior a UCI",
    "muerte": "Muerte hospitalaria",
}
CONTINUOS = {"cambio_hb_72h": "Cambio de Hb a 72 h (g/dL)", "dias_a_alta": "Días hasta el alta"}


def fmt_p(p: float) -> str:
    return "p < 0.001" if p < 0.001 else f"p = {p:.3f}"


def fisher(a: int, n1: int, c: int, n0: int) -> float:
    return float(stats.fisher_exact([[a, n1 - a], [c, n0 - c]]).pvalue)


def grupos(df, col):
    return [df.filter((pl.col("grupo") == g) & pl.col(col).is_not_null())[col] for g in GRUPOS]


def comparar(df) -> dict:
    """Todas las comparaciones, con Holm sobre la familia de 7 desenlaces."""
    res = {}
    for col, etq in BINARIOS.items():
        s1, s0 = grupos(df, col)
        a, n1, c, n0 = int(s1.sum()), s1.len(), int(s0.sum()), s0.len()
        res[col] = dict(etq=etq, a=a, n1=n1, c=c, n0=n0, rd=newcombe_rd(a, n1, c, n0), p=fisher(a, n1, c, n0))
    for col, etq in CONTINUOS.items():
        s1, s0 = grupos(df, col)
        x1, x0 = s1.to_list(), s0.to_list()
        res[col] = dict(etq=etq, n1=len(x1), n0=len(x0), med1=float(np.median(x1)), med0=float(np.median(x0)),
                        hl=hodges_lehmann(x1, x0), p=float(stats.mannwhitneyu(x1, x0, alternative="two-sided").pvalue))
    for col, ajustado in zip(res, holm([r["p"] for r in res.values()])):
        res[col]["p_holm"] = ajustado
    return res


def h10_manejo(df) -> dict:
    fig, ax = lienzo("Tras la caída de Hb, nadie suspendió el antiagregante",
                     "Orden activa en las 24 h posteriores a la primera caída. Sin pacientes que lo suspendieran no se puede "
                     "comparar continuar vs. suspender", figsize=(8.5, 4.8))
    s1, s0 = df.filter(pl.col("grupo") == GRUPOS[0]), df.filter(pl.col("grupo") == GRUPOS[1])
    filas = [("Antiagregante\n(grupo combinación)", int(s1["ap_continua"].sum()), s1.height, COLOR[GRUPOS[0]], 0),
             ("Anticoagulante\n(grupo combinación)", int(s1["ac_continua"].sum()), s1.height, COLOR[GRUPOS[0]], 1),
             ("Anticoagulante\n(solo anticoagulante)", int(s0["ac_continua"].sum()), s0.height, COLOR[GRUPOS[1]], 2)]
    for etq, a, n, color, x in filas:
        e = wilson(a, n)
        ax.plot([x, x], [100 * e.li, 100 * e.ls], color=color, lw=2.5)
        ax.plot(x, 100 * e.valor, "o", ms=10, color=color, mec=FONDO, mew=1.4, zorder=3)
        ax.text(x + 0.06, 100 * e.valor - 3, f"{100 * e.valor:.0f} % ({a}/{n})\nIC 95 % {100 * e.li:.0f}–{100 * e.ls:.0f}",
                va="top", fontsize=9.5, color=TINTA2)
    p = fisher(filas[1][1], filas[1][2], filas[2][1], filas[2][2])
    ax.set_title(f"Continuar anticoagulante, combinación vs. solo: Fisher {fmt_p(p)}", fontsize=10, color=TINTA2)
    ax.set_xticks([0, 1, 2], [f[0] for f in filas], color=TINTA)
    ax.set_xlim(-0.4, 2.6)
    ax.set_ylim(0, 105)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f} %")
    ax.set_ylabel("Continúan el fármaco")
    ax.tick_params(axis="x", length=0)
    ejes_limpios(ax)
    guardar(fig, "H10_manejo_tras_caida.pdf", SALIDA)
    return dict(ap=(filas[0][1], filas[0][2]), ac_comb=(filas[1][1], filas[1][2]), ac_solo=(filas[2][1], filas[2][2]), p=p)


def ajuste_72h(df) -> dict:
    d = df.filter(pl.col("cambio_hb_72h").is_not_null())
    X = np.column_stack([np.ones(d.height), (d["grupo"] == GRUPOS[0]).cast(pl.Float64).to_numpy(),
                         (d["hb_t0"] - d["hb_t0"].mean()).to_numpy(),
                         (d["intensidad"] == "terapeutica").cast(pl.Float64).to_numpy()])
    beta, ee, gl = ols_hc3(X, d["cambio_hb_72h"].to_numpy())
    t = float(stats.t.ppf(0.975, gl))
    p = float(2 * stats.t.sf(abs(beta[1] / ee[1]), gl))
    return dict(e=Estimacion(float(beta[1]), float(beta[1] - t * ee[1]), float(beta[1] + t * ee[1])), p=p, n=d.height)


def h11_trayectoria(con, res, aj) -> None:
    s = tabla(con, """
        WITH x AS (
            SELECT p.grupo, p.hadm_id, 1 + floor(date_diff('minute', p.t0, l.charttime) / 1440.0)::INT AS dia,
                   avg(l.valuenum - p.hb_t0) AS cambio
            FROM post_caida p JOIN labevents l ON l.subject_id = p.subject_id AND l.itemid = 51222
             AND l.valuenum IS NOT NULL AND l.charttime > p.t0 AND l.charttime <= p.t_fin_post
            GROUP BY ALL)
        SELECT grupo, dia, count(*) n, median(cambio) med, quantile_cont(cambio, 0.25) q1, quantile_cont(cambio, 0.75) q3
        FROM x WHERE dia <= 5 GROUP BY ALL ORDER BY grupo, dia""")
    r = res["cambio_hb_72h"]
    fig, ax = lienzo("Después de la caída, la Hb evoluciona de forma similar en ambos grupos" if r["p"] >= 0.05
                     else "Después de la caída, la Hb evoluciona distinto entre grupos",
                     "Cambio respecto a la Hb en t0: mediana (línea) y rango intercuartílico (banda), días con al menos 5 "
                     "pacientes por grupo. Modelo ajustado por Hb en t0 e intensidad, con errores HC3", figsize=(9.5, 5.4))
    for g in GRUPOS:
        d = s.filter((pl.col("grupo") == g) & (pl.col("n") >= 5))
        x, m, a, b = [0] + d["dia"].to_list(), [0] + d["med"].to_list(), [0] + d["q1"].to_list(), [0] + d["q3"].to_list()
        ax.fill_between(x, a, b, color=COLOR[g], alpha=0.12, lw=0)
        ax.plot(x, m, "-o", color=COLOR[g], lw=2, ms=6, mec=FONDO)
    ax.axhline(0, color=TENUE, lw=1)
    ax.set_title(f"72 h: mediana {r['med1']:+.1f} vs. {r['med0']:+.1f} g/dL · Hodges-Lehmann {r['hl'].valor:+.2f} "
                 f"(IC 95 % {r['hl'].li:+.2f} a {r['hl'].ls:+.2f}) · Mann-Whitney {fmt_p(r['p'])}\n"
                 f"Ajustado: {aj['e'].valor:+.2f} g/dL (IC 95 % {aj['e'].li:+.2f} a {aj['e'].ls:+.2f}), {fmt_p(aj['p'])}, "
                 f"n = {aj['n']}", fontsize=9.5, color=TINTA2)
    ax.set_xlabel("Días desde la primera caída de Hb")
    ax.set_ylabel("Cambio de Hb desde t0 (g/dL)")
    ejes_limpios(ax)
    leyenda_figura(fig)
    guardar(fig, "H11_trayectoria_post_caida.pdf", SALIDA)


def h12_recuperacion(df) -> dict:
    d = df.with_columns(pl.coalesce("dias_a_recuperar", "dias_post").alias("t"))
    datos = {g: stats.CensoredData.right_censored(d.filter(pl.col("grupo") == g)["t"].to_numpy(),
                                                  ~d.filter(pl.col("grupo") == g)["recupera_hb"].to_numpy())
             for g in GRUPOS}
    lr = stats.logrank(datos[GRUPOS[0]], datos[GRUPOS[1]])
    fig, ax = lienzo("La recuperación de la Hb fue poco frecuente en ambos grupos",
                     "Kaplan-Meier del tiempo hasta Hb ≥ basal − 1 g/dL, con censura al alta o a los 7 días. El alta temprana "
                     "puede ser censura informativa", figsize=(9.5, 5.4))
    for g in GRUPOS:
        sub = d.filter(pl.col("grupo") == g).sort("t")
        s, n, xs, ys = 1.0, sub.height, [0.0], [0.0]
        for t, ev in zip(sub["t"].to_list(), sub["recupera_hb"].to_list()):
            if ev:
                s *= 1 - 1 / n
            xs.append(t)
            ys.append(100 * (1 - s))
            n -= 1
        ax.step(xs, ys, where="post", color=COLOR[g], lw=2.2)
    for k, g in enumerate(GRUPOS):
        sub = d.filter(pl.col("grupo") == g)
        for dia in (0, 2, 4, 6):
            ax.text(dia, -13 - 6 * k, str(sub.filter(pl.col("t") >= dia).height), ha="center", fontsize=9.5, color=COLOR[g])
    ax.text(0, -8, "Pacientes en riesgo", fontsize=9.5, color=TINTA2)
    ax.set_title(f"Log-rank: χ² = {lr.statistic ** 2:.2f}, {fmt_p(float(lr.pvalue))}", fontsize=10, color=TINTA2)
    ax.set_xlim(-0.2, 7.2)
    ax.set_ylim(-25, 60)
    ax.set_yticks(range(0, 61, 20), [f"{v} %" for v in range(0, 61, 20)])
    ax.spines["left"].set_bounds(0, 60)
    ax.set_xlabel("Días desde la primera caída de Hb")
    ax.set_ylabel("Recuperación acumulada")
    ejes_limpios(ax)
    leyenda_figura(fig)
    guardar(fig, "H12_recuperacion_hb.pdf", SALIDA)
    return dict(chi2=float(lr.statistic ** 2), p=float(lr.pvalue))


def h13_desenlaces(res) -> None:
    filas = [res[c] for c in BINARIOS]
    fig, ax = lienzo("Añadir el antiagregante no mostró beneficio ni daño claro después de la caída"
                     if all(r["p_holm"] >= 0.05 for r in res.values()) else "Algún desenlace difiere tras la caída",
                     "Diferencia de riesgos (combinación − solo anticoagulante) con IC 95 % de Newcombe. p de Fisher exacta y "
                     "corregida por Holm sobre 7 desenlaces", figsize=(11.5, 4.8))
    n = len(filas)
    from matplotlib.transforms import blended_transform_factory
    col = blended_transform_factory(ax.transAxes, ax.transData)
    for i, r in enumerate(filas):
        y = n - 1 - i
        e = r["rd"]
        ax.plot([100 * e.li, 100 * e.ls], [y, y], color=TINTA, lw=2)
        ax.plot(100 * e.valor, y, "s", ms=8, color=TINTA, mec=FONDO, zorder=3)
        ax.text(1.03, y, f"{r['a']}/{r['n1']} vs. {r['c']}/{r['n0']}", va="center", fontsize=9.5, color=TINTA2, transform=col)
        ax.text(1.27, y, f"{100 * e.valor:+.0f} ({100 * e.li:+.0f} a {100 * e.ls:+.0f})", va="center", fontsize=9.5,
                color=TINTA, transform=col)
        ax.text(1.56, y, f"{r['p']:.3f}", va="center", fontsize=9.5, color=TINTA, transform=col)
        ax.text(1.71, y, f"{r['p_holm']:.3f}", va="center", fontsize=9.5, color=TINTA, transform=col)
    for x, t in ((1.03, "Eventos"), (1.27, "DR, pp (IC 95 %)"), (1.56, "p"), (1.71, "p Holm")):
        ax.text(x, n - 0.42, t, fontsize=9.5, fontweight="bold", color=TENUE, transform=col)
    ax.axvline(0, color=TENUE, lw=1, ls=(0, (4, 3)))
    ax.set_yticks(range(n), [r["etq"] for r in reversed(filas)], color=TINTA)
    ax.set_ylim(-0.7, n - 0.2)
    ax.set_xlabel("Diferencia de riesgos (puntos porcentuales)")
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ejes_limpios(ax, "x")
    guardar(fig, "H13_desenlaces_post_caida.pdf", SALIDA)


def h14_continuos(df, res) -> None:
    fig, axes = lienzo("Cambio de Hb a 72 h y días hasta el alta",
                       "Puntos: pacientes; caja: mediana y rango intercuartílico. Diferencia de Hodges-Lehmann con IC 95 % de "
                       "Moses y Mann-Whitney bilateral; p Holm sobre 7 desenlaces", ncols=2, figsize=(11, 5))
    for ax, col in zip(axes, CONTINUOS):
        r = res[col]
        v = dict(zip(GRUPOS, [x.to_list() for x in grupos(df, col)]))
        puntos_y_caja(ax, v, {GRUPOS[0]: 0, GRUPOS[1]: 1.25})
        ax.set_xticks([0.1, 1.35], [f"Combinación\n(n = {r['n1']})", f"Solo anticoagulante\n(n = {r['n0']})"], color=TINTA)
        ax.set_xlim(-0.45, 2.3)
        ax.set_ylabel(r["etq"])
        ax.set_title(f"HL {r['hl'].valor:+.2f} ({r['hl'].li:+.2f} a {r['hl'].ls:+.2f}) · {fmt_p(r['p'])} · Holm {r['p_holm']:.3f}",
                     fontsize=9.5, color=TINTA2)
        ejes_limpios(ax)
    guardar(fig, "H14_hb_72h_y_estancia.pdf", SALIDA)


def h15_potencia(df_cohorte) -> dict:
    d = df_cohorte
    s1, s0 = d.filter(pl.col("grupo") == GRUPOS[0]), d.filter(pl.col("grupo") == GRUPOS[1])
    n1, n0 = s1.height, s0.height
    p0 = float(s0["sangrado_documentado"].mean())
    p1 = float(s1["sangrado_documentado"].mean())
    rr_ref = 2.0  # efecto hipotético clínicamente plausible; no se usa el efecto observado
    rrs = np.linspace(1.1, 5, 120)
    rrs_validos = rrs[rrs * p0 < 1]
    pot = [100 * potencia_dos_proporciones(float(r * p0), p0, n1, n0) for r in rrs_validos]
    necesarios = [n_por_grupo(float(r * p0), p0) for r in rrs_validos]
    pot_ref = potencia_dos_proporciones(rr_ref * p0, p0, n1, n0)
    n_ref = n_por_grupo(rr_ref * p0, p0)
    rr_80 = float(next((r for r, x in zip(rrs_validos, pot) if x >= 80), math.nan))
    fig, axes = lienzo(f"El estudio solo tiene 80 % de potencia para un RR ≥ {rr_80:.1f}",
                       f"Hemorragia documentada, riesgo de referencia {100 * p0:.0f} %, α = 0.05 bilateral (h de Cohen). Para un "
                       f"RR hipotético de {rr_ref:.0f}, la potencia es {100 * pot_ref:.0f} % y se requieren {n_ref} pacientes por "
                       "grupo. No se usa potencia post hoc con el efecto observado",
                       ncols=2, figsize=(11, 4.8))
    axes[0].plot(rrs_validos, pot, color=TINTA, lw=2)
    axes[0].axhline(80, color=TENUE, lw=1, ls=(0, (4, 3)))
    axes[0].axvline(rr_ref, color=COLOR[GRUPOS[0]], lw=1.5)
    axes[0].text(rr_ref + 0.05, 5, f"RR hipotético {rr_ref:.0f}\npotencia {100 * pot_ref:.0f} %", color=TINTA2, fontsize=9.5)
    axes[0].set(xlabel="RR verdadero", ylabel=f"Potencia con n = {n1} y {n0}", ylim=(0, 100))
    axes[0].yaxis.set_major_formatter(lambda v, _: f"{v:.0f} %")
    axes[1].plot(rrs_validos, necesarios, color=TINTA, lw=2)
    axes[1].axhline((n1 + n0) / 2, color=TENUE, lw=1, ls=(0, (4, 3)))
    axes[1].text(rrs_validos[-1], (n1 + n0) / 2 * 1.08, "tamaño actual (promedio por grupo)", ha="right", color=TINTA2, fontsize=9.5)
    axes[1].axvline(rr_ref, color=COLOR[GRUPOS[0]], lw=1.5)
    axes[1].text(rr_ref + 0.05, n_ref * 1.1, f"{n_ref} por grupo", color=TINTA2, fontsize=9.5)
    axes[1].set_yscale("log")
    axes[1].set(xlabel="RR verdadero", ylabel="Pacientes por grupo para 80 % de potencia")
    for ax in axes:
        ejes_limpios(ax)
    guardar(fig, "H15_potencia.pdf", SALIDA)
    return dict(p0=p0, p1=p1, rr_ref=rr_ref, pot=pot_ref, n=n_ref, rr80=rr_80)


def generar(con, cohorte: pl.DataFrame) -> dict:
    df = tabla(con, "SELECT * FROM post_caida")
    res = comparar(df)
    aj = ajuste_72h(df)
    salida = dict(n=df.height, n1=df.filter(pl.col("grupo") == GRUPOS[0]).height,
                  n0=df.filter(pl.col("grupo") == GRUPOS[1]).height, res=res, ajuste=aj, manejo=h10_manejo(df))
    h11_trayectoria(con, res, aj)
    salida["logrank"] = h12_recuperacion(df)
    h13_desenlaces(res)
    h14_continuos(df, res)
    salida["potencia"] = h15_potencia(cohorte)
    return salida
