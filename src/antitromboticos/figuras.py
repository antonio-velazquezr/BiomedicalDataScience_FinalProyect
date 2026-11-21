"""Figuras principales de resultados (gráficas de matplotlib en PDF vectorial).

Genera en ``figuras/principales/``:

1. ``01_atricion.pdf``           de 275 hospitalizaciones a la cohorte final
2. ``02_balance_basal.pdf``      diferencias estandarizadas entre grupos (love plot)
3. ``03_sangrado_principal.pdf`` riesgo de sangrado relevante por grupo e intensidad
4. ``04_forest_desenlaces.pdf``  razón de riesgos de todos los desenlaces
5. ``05_trayectorias.pdf``       Hb y plaquetas día a día desde la fecha índice
6. ``06_replica_omop.pdf``       el resultado principal en las tablas nativas y en OMOP

Los títulos que afirman algo se calculan a partir de los datos (p. ej., solo dicen "sin diferencia
clara" si el IC 95 % cruza 1).

Uso::

    python -m antitromboticos.figuras
"""

from __future__ import annotations

import math
import textwrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import polars as pl  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402
from matplotlib.transforms import blended_transform_factory  # noqa: E402

from antitromboticos.analisis import BINARIOS, conteos  # noqa: E402
from antitromboticos.cohorte import RAIZ, construir  # noqa: E402
from antitromboticos.estadistica import mantel_haenszel_rr, razon_riesgos, smd_binaria, smd_continua, wilson  # noqa: E402

SALIDA = RAIZ / "figuras" / "principales"

# Paleta: dos grupos (slots categóricos 1 y 2 validados) + tintas neutras
COMB, SOLO = "#2a78d6", "#eb6834"
TINTA, TINTA2, TENUE, REJILLA, FONDO = "#0b0b0b", "#52514e", "#8a8984", "#e4e3df", "#ffffff"
NOMBRE = {"combinacion": "Anticoagulante + antiagregante", "solo_anticoagulante": "Solo anticoagulante"}
COLOR = {"combinacion": COMB, "solo_anticoagulante": SOLO}
GRUPOS = ["combinacion", "solo_anticoagulante"]
FUENTE = "Fuente: MIMIC-IV Clinical Database Demo v2.2 (PhysioNet). Estudio observacional descriptivo; IC 95 %."

plt.rcParams.update({
    "font.family": "DejaVu Sans",
    "font.size": 11,
    "axes.edgecolor": REJILLA,
    "axes.labelcolor": TINTA2,
    "axes.titlecolor": TINTA,
    "xtick.color": TINTA2,
    "ytick.color": TINTA2,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "figure.facecolor": FONDO,
    "axes.facecolor": FONDO,
    "savefig.facecolor": FONDO,
    "pdf.fonttype": 42,  # texto editable en el PDF
})


# ----------------------------------------------------------------------------- utilidades
def lienzo(titulo: str, subtitulo: str, nota: str = FUENTE, figsize=(10, 6), **subplots):
    """Figura simple con márgenes automáticos y solo un título. La descripción (`subtitulo`) y las
    aclaraciones metodológicas (`nota`) no se dibujan: se guardan como pie de figura en el INDICE.md
    de la carpeta."""
    fig, ax = plt.subplots(figsize=figsize, layout="constrained", **subplots)
    fig.suptitle(titulo, fontsize=13.5, fontweight="bold", color=TINTA)
    extra = nota.replace(FUENTE, "").strip()
    fig._pie = " ".join(t if t.endswith(".") else t + "." for t in [subtitulo, extra] if t)
    return fig, ax


PIES: dict[str, str] = {}  # archivo -> pie de figura, para los índices


def guardar(fig, nombre: str, carpeta=None) -> None:
    carpeta = carpeta or SALIDA
    carpeta.mkdir(parents=True, exist_ok=True)
    fig.savefig(carpeta / nombre, bbox_inches="tight", pad_inches=0.25)
    PIES[nombre] = getattr(fig, "_pie", "")
    plt.close(fig)


def tabla(con, sql: str) -> pl.DataFrame:
    cur = con.execute(sql)
    columnas = [d[0] for d in cur.description]
    return pl.DataFrame(cur.fetchall(), schema=columnas, orient="row")


def fmt_rr(e) -> str:
    return f"{e.valor:.2f} (IC 95 % {e.li:.2f}–{e.ls:.2f})"


def leyenda_grupos(ax, loc="upper right", **kw) -> None:
    for g in GRUPOS:
        ax.plot([], [], "o", color=COLOR[g], ms=9, label=NOMBRE[g])
    ax.legend(loc=loc, frameon=False, fontsize=10.5, labelcolor=TINTA, handletextpad=0.4, **kw)


def leyenda_figura(fig, y: float | None = None) -> None:
    """Leyenda de los dos grupos, centrada debajo de las gráficas."""
    from matplotlib.lines import Line2D

    marcas = [Line2D([], [], marker="o", ls="", color=COLOR[g], ms=9) for g in GRUPOS]
    fig.legend(marcas, [NOMBRE[g] for g in GRUPOS], loc="outside lower center", ncol=2,
               frameon=False, fontsize=10.5, labelcolor=TINTA, handletextpad=0.4, columnspacing=1.6)


# ----------------------------------------------------------------------------- 1. atrición
def fig_atricion(atricion: pl.DataFrame, df: pl.DataFrame) -> None:
    filas = atricion.sort("paso").rows(named=True)
    motivos = {
        2: "Menores de 18 años", 3: "Estancia < 24 h", 4: "Sin anticoagulante",
        5: "Antiagregante sin solapamiento", 6: "Ingreso por sangrado",
        7: "Sin Hb o plaquetas basales", 8: "Reingresos del mismo paciente",
    }
    cajas = [filas[0]] + [f for f, previo in zip(filas[1:], filas) if f["hospitalizaciones"] != previo["hospitalizaciones"]]
    sin_efecto = [motivos[f["paso"]] for f, previo in zip(filas[1:], filas)
                  if f["hospitalizaciones"] == previo["hospitalizaciones"]]

    fig, ax = lienzo(
        f"De {filas[0]['hospitalizaciones']} hospitalizaciones a {filas[-1]['pacientes']} pacientes analizados",
        "Criterios de inclusión aplicados en orden; un paciente entra con su primera hospitalización elegible",
        nota=FUENTE + (f"  Criterios sin exclusiones: {', '.join(sin_efecto).lower()}." if sin_efecto else ""),
    )
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    def caja(x, y, w, h, texto, borde=TINTA2, fondo=FONDO, peso="normal", color=TINTA, size=11):
        ax.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.006,rounding_size=0.012",
                                    lw=1.2, ec=borde, fc=fondo))
        ax.text(x, y, texto, ha="center", va="center", fontsize=size, color=color, fontweight=peso)

    n_pasos = len(cajas)
    y_top, y_bottom = 0.94, 0.38
    ys = [y_top - i * ((y_top - y_bottom) / (n_pasos - 1)) for i in range(n_pasos)]
    xc, w, h = 0.32, 0.30, 0.072
    for i, (f, y) in enumerate(zip(cajas, ys)):
        final = i == n_pasos - 1
        texto = (f"Cohorte final: {f['pacientes']} pacientes" if final
                 else f"{f['hospitalizaciones']} hospitalizaciones · {f['pacientes']} pacientes")
        caja(xc, y, w, h, texto, peso="bold" if final else "normal")
        if i:
            ax.annotate("", xy=(xc, y + h / 2), xytext=(xc, ys[i - 1] - h / 2),
                        arrowprops=dict(arrowstyle="-|>", color=TENUE, lw=1.2))
            excluidas = cajas[i - 1]["hospitalizaciones"] - f["hospitalizaciones"]
            ym = (ys[i - 1] + y) / 2
            ax.plot([xc, 0.54], [ym, ym], color=TENUE, lw=1)
            caja(0.755, ym, 0.43, 0.052, f"{motivos[f['paso']]}: −{excluidas} hospitalizaciones",
                 borde=REJILLA, color=TINTA2, size=10)

    # Reparto final por grupo e intensidad, debajo de la cohorte final
    y_final, y_grupos = ys[-1], 0.12
    for k, g in enumerate(GRUPOS):
        sub = df.filter(pl.col("grupo") == g)
        prof = sub.filter(pl.col("intensidad") == "profilactica").height
        ter = sub.filter(pl.col("intensidad") == "terapeutica").height
        x = xc + (k - 0.5) * 0.32
        ax.annotate("", xy=(x, y_grupos + 0.075), xytext=(xc, y_final - h / 2),
                    arrowprops=dict(arrowstyle="-|>", color=TENUE, lw=1.2, connectionstyle="angle,angleA=0,angleB=90,rad=0"))
        caja(x, y_grupos, 0.28, 0.15, f"{NOMBRE[g]}\n{sub.height} pacientes\n{prof} con profilaxis · {ter} terapéutica",
             borde=COLOR[g], fondo=FONDO, size=10.5)
    guardar(fig, "01_atricion.pdf")


# ----------------------------------------------------------------------------- 2. balance basal
def fig_balance(df: pl.DataFrame) -> None:
    g1, g0 = df.filter(pl.col("grupo") == "combinacion"), df.filter(pl.col("grupo") == "solo_anticoagulante")
    continuas = {"Edad": "edad", "Hemoglobina basal": "hb_basal", "Plaquetas basales": "plaquetas_basal"}
    binarias = {
        "Mujeres": pl.col("sexo") == "F",
        "Cardiopatía isquémica": pl.col("cardiopatia_isquemica"),
        "Fibrilación auricular": pl.col("fibrilacion_auricular"),
        "Insuficiencia cardiaca": pl.col("insuficiencia_cardiaca"),
        "Tromboembolia venosa": pl.col("tromboembolia_venosa"),
        "En UCI en la fecha índice": pl.col("uci_en_indice"),
        "Anticoagulación terapéutica": pl.col("intensidad") == "terapeutica",
        "Cirugía cardiaca": pl.col("estrato") == "cirugia_cardiaca",
        "Paciente quirúrgico": pl.col("estrato") == "quirurgico",
    }
    smd = {k: smd_continua(g1[c].drop_nulls().to_list(), g0[c].drop_nulls().to_list()) for k, c in continuas.items()}
    smd |= {k: smd_binaria(g1.select(e).to_series().mean(), g0.select(e).to_series().mean()) for k, e in binarias.items()}
    orden = sorted(smd, key=lambda k: abs(smd[k]))
    desbalance = [k for k in reversed(orden) if abs(smd[k]) > 0.1]

    fig, ax = lienzo(
        "Los grupos no son comparables al inicio" if desbalance else "Los grupos son comparables al inicio",
        f"{len(desbalance)} de {len(smd)} características superan una diferencia estandarizada de 0.1; "
        f"las mayores: {', '.join(d[0].lower() + d[1:] for d in desbalance[:3])}",
    )
    ax.axvspan(-0.1, 0.1, color="#f1f0ec", zorder=0)
    ax.axvline(0, color=TENUE, lw=1)
    for i, k in enumerate(orden):
        v = smd[k]
        color = COMB if v > 0 else SOLO
        ax.plot([0, v], [i, i], color=REJILLA, lw=2, zorder=1, solid_capstyle="round")
        ax.plot(v, i, "o", ms=10, color=color if abs(v) > 0.1 else TENUE, mec=FONDO, mew=1.5, zorder=3)
        ax.text(v + (0.04 if v >= 0 else -0.04), i, f"{v:+.2f}", va="center", ha="left" if v >= 0 else "right",
                fontsize=9.5, color=TINTA2)
    ax.set_yticks(range(len(orden)), orden, color=TINTA)
    lim = max(1.0, max(abs(v) for v in smd.values()) + 0.25)
    ax.set_xlim(-lim, lim)
    ax.set_xlabel(f"← mayor en solo anticoagulante          Diferencia estandarizada          "
                  f"mayor en anticoagulante + antiagregante →", labelpad=10)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.text(0, -0.9, "zona de balance aceptable (±0.1)", ha="center", fontsize=9, color=TENUE)
    ax.set_ylim(-1.3, len(orden) - 0.4)
    guardar(fig, "02_balance_basal.pdf")


# ----------------------------------------------------------------------------- 3. desenlace principal
def fig_sangrado(df: pl.DataFrame) -> None:
    col = "sangrado_relevante"
    bloques = [("Todos los pacientes", df), ("Profilaxis", df.filter(pl.col("intensidad") == "profilactica")),
               ("Anticoagulación\nterapéutica", df.filter(pl.col("intensidad") == "terapeutica"))]
    mh = mantel_haenszel_rr([conteos(df.filter(pl.col("intensidad") == e), col) for e in ("profilactica", "terapeutica")])
    sin_dif = mh.li <= 1 <= mh.ls
    a, n1, c, n0 = conteos(df, col)
    fig, ax = lienzo(
        "Añadir un antiagregante no mostró una diferencia clara en sangrado" if sin_dif
        else "Añadir un antiagregante se asoció con una diferencia en sangrado",
        f"Sangrado relevante (caída de Hb ≥ 2 g/dL o transfusión) en los 14 días siguientes · "
        f"RR ajustado por intensidad {fmt_rr(mh)}",
    )
    for i, (nombre, sub) in enumerate(bloques):
        a, n1, c, n0 = conteos(sub, col)
        for g, (ev, n), dx in (("combinacion", (a, n1), -0.13), ("solo_anticoagulante", (c, n0), 0.13)):
            e = wilson(ev, n)
            ax.plot([i + dx, i + dx], [100 * e.li, 100 * e.ls], color=COLOR[g], lw=2.5, solid_capstyle="round")
            ax.plot(i + dx, 100 * e.valor, "o", ms=11, color=COLOR[g], mec=FONDO, mew=1.5, zorder=3)
            ax.text(i + dx + 0.06, 100 * e.valor, f"{100 * e.valor:.0f} %\n{ev}/{n}", va="center", ha="left",
                    fontsize=9.5, color=TINTA2)
    ax.set_xticks(range(len(bloques)), [b[0] for b in bloques], color=TINTA, fontsize=11.5)
    ax.set_xlim(-0.6, len(bloques) - 0.35)
    ax.set_ylim(0, 100)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f} %")
    ax.set_ylabel("Pacientes con sangrado relevante")
    ax.grid(axis="y", color=REJILLA, lw=0.8)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", length=0)
    n_ter = [conteos(bloques[2][1], col)[1], conteos(bloques[2][1], col)[3]]
    ax.text(2, 4, f"n = {n_ter[0]} y {n_ter[1]}: interpretar con cautela", ha="center", fontsize=9, color=TENUE)
    leyenda_grupos(ax, loc="upper left", ncol=2)
    guardar(fig, "03_sangrado_principal.pdf")


# ----------------------------------------------------------------------------- 4. forest de desenlaces
def fig_forest(df: pl.DataFrame) -> None:
    filas = []
    for col, etiqueta in BINARIOS.items():
        if df[col].null_count() == df.height:
            continue
        a, n1, c, n0 = conteos(df, col)
        rr = razon_riesgos(a, n1, c, n0)
        mh = mantel_haenszel_rr([conteos(df.filter(pl.col("intensidad") == e), col) for e in ("profilactica", "terapeutica")])
        est = mh if not math.isnan(mh.valor) else rr
        etiqueta = etiqueta.replace("concentrado eritrocitario", "glóbulos rojos")
        filas.append((etiqueta, est, a, n1, c, n0, col == "sangrado_relevante",
                      not math.isnan(mh.valor)))
    concluyentes = [f[0] for f in filas if not (f[1].li <= 1 <= f[1].ls)]
    fig, ax = lienzo(
        "Ningún desenlace mostró una asociación concluyente" if not concluyentes
        else f"{len(concluyentes)} desenlace(s) con asociación: {', '.join(concluyentes)}",
        "Razón de riesgos, anticoagulante + antiagregante vs. solo anticoagulante (ajustada por intensidad)",
        nota=FUENTE + "  * Sin ajuste: un estrato sin eventos impide la estimación de Mantel-Haenszel.",
    )
    lim_inf, lim_sup = 0.05, 20
    col = blended_transform_factory(ax.transAxes, ax.transData)  # x en fracción del eje, y en filas
    x_rr, x_ev = 1.04, 1.42
    for i, (nombre, e, a, n1, c, n0, principal, ajustado) in enumerate(filas):
        y = len(filas) - 1 - i
        if principal:
            ax.axhspan(y - 0.45, y + 0.45, color="#f1f0ec", zorder=0)
        li, ls = max(e.li, lim_inf), min(e.ls, lim_sup)
        ax.plot([li, ls], [y, y], color=TINTA, lw=2, solid_capstyle="round")
        ax.plot(e.valor, y, "s" if ajustado else "D", ms=9, color=TINTA, mec=FONDO, mew=1.5, zorder=3)
        if e.ls > lim_sup:
            ax.annotate("", xy=(lim_sup, y), xytext=(lim_sup * 0.75, y), arrowprops=dict(arrowstyle="->", color=TINTA))
        ax.text(x_rr, y, f"{e.valor:.2f} ({e.li:.2f}–{e.ls:.2f}){'' if ajustado else ' *'}",
                va="center", fontsize=10.5, color=TINTA, transform=col)
        ax.text(x_ev, y, f"{a}/{n1}  vs  {c}/{n0}", va="center", fontsize=10.5, color=TINTA2, transform=col)
    ax.text(x_rr, len(filas) - 0.45, "RR (IC 95 %)", fontsize=10, color=TENUE, fontweight="bold", transform=col)
    ax.text(x_ev, len(filas) - 0.45, "Eventos: combinación vs. solo AC", fontsize=10, color=TENUE,
            fontweight="bold", transform=col)
    ax.axvline(1, color=TENUE, lw=1, ls=(0, (4, 3)))
    ax.set_xscale("log")
    ax.set_xlim(lim_inf, lim_sup)
    ax.set_xticks([0.1, 0.25, 0.5, 1, 2, 4, 10], ["0.1", "0.25", "0.5", "1", "2", "4", "10"])
    ax.minorticks_off()
    ax.set_yticks(range(len(filas)), [f[0] for f in reversed(filas)], color=TINTA)
    ax.set_ylim(-0.8, len(filas) - 0.2)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", color=REJILLA, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("← menos frecuente con la combinación      más frecuente →", labelpad=8)
    guardar(fig, "04_forest_desenlaces.pdf")


# ----------------------------------------------------------------------------- 5. trayectorias
def fig_trayectorias(con, max_dia: int = 7, n_min: int = 10) -> None:
    serie = tabla(con, f"""
        WITH x AS (
            SELECT c.grupo, c.subject_id, l.itemid,
                   1 + floor(date_diff('minute', c.t_indice, l.charttime) / 1440.0)::INT AS dia,
                   CASE l.itemid WHEN 51222 THEN l.valuenum - c.hb_basal
                                 ELSE 100.0 * (l.valuenum - c.plaquetas_basal) / c.plaquetas_basal END AS cambio
            FROM cohorte_analitica c
            JOIN labevents l ON l.subject_id = c.subject_id AND l.itemid IN (51222, 51265)
             AND l.valuenum IS NOT NULL AND l.charttime > c.t_indice AND l.charttime <= c.t_fin_seguimiento
        ),
        por_paciente AS (  -- el peor valor del día (nadir) de cada paciente
            SELECT grupo, subject_id, itemid, dia, min(cambio) AS cambio FROM x WHERE dia <= {max_dia} GROUP BY ALL
        )
        SELECT grupo, itemid, dia, count(*) AS n, median(cambio) AS mediana,
               quantile_cont(cambio, 0.25) AS q1, quantile_cont(cambio, 0.75) AS q3
        FROM por_paciente GROUP BY ALL
        UNION ALL
        SELECT grupo, itemid, 0, count(*), 0, 0, 0
        FROM cohorte_analitica, (VALUES (51222), (51265)) AS t(itemid) GROUP BY ALL
        ORDER BY grupo, itemid, dia
    """)
    fig, axes = lienzo(
        "Hemoglobina y plaquetas siguen trayectorias que se superponen",
        "Cambio respecto al valor basal en los días siguientes a la fecha índice: mediana (línea) y "
        "rango intercuartílico (banda)",
        nota=FUENTE + f"  Se muestran los días con al menos {n_min} pacientes medidos por grupo; "
                      "cada paciente aporta su valor más bajo del día.",
        ncols=2,
    )
    leyenda_figura(fig, y=0.845)
    for ax, (item, titulo, unidad) in zip(axes, [(51222, "Hemoglobina", "g/dL"), (51265, "Plaquetas", "%")]):
        for g in GRUPOS:
            s = serie.filter((pl.col("grupo") == g) & (pl.col("itemid") == item) & (pl.col("n") >= n_min)).sort("dia")
            # cortar en el primer día que no llega al mínimo para no unir huecos
            dias = s["dia"].to_list()
            corte = next((i for i, d in enumerate(dias) if d != i), len(dias))
            s = s.head(corte)
            ax.fill_between(s["dia"], s["q1"], s["q3"], color=COLOR[g], alpha=0.10, lw=0)
            ax.plot(s["dia"], s["mediana"], "-o", color=COLOR[g], lw=2, ms=6, mec=FONDO, mew=1)
        ax.axhline(0, color=TENUE, lw=1)
        ax.set_title(titulo, loc="left", fontsize=13, color=TINTA, fontweight="bold")
        ax.set_xlabel("Días desde la fecha índice")
        ax.set_ylabel(f"Cambio respecto a la basal ({unidad})")
        ax.set_xticks(range(0, max_dia + 1))
        ax.grid(axis="y", color=REJILLA, lw=0.8)
        ax.set_axisbelow(True)
    axes[0].axhline(-2, color=TENUE, lw=1, ls=(0, (4, 3)))
    axes[0].text(0.1, -2.05, "umbral de sangrado (−2 g/dL)", ha="left", va="top", fontsize=9, color=TENUE)
    guardar(fig, "05_trayectorias.pdf")


# ----------------------------------------------------------------------------- 6. réplica OMOP
def fig_replica(dfs: dict[str, pl.DataFrame]) -> None:
    filas = []
    for fuente, etiqueta in (("mimic", "Tablas nativas de MIMIC-IV"), ("omop", "OMOP CDM 5.3.1")):
        df = dfs[fuente]
        a, n1, c, n0 = conteos(df, "sangrado_relevante")
        filas.append((etiqueta, "cruda", razon_riesgos(a, n1, c, n0), df.height))
        filas.append((etiqueta, "ajustada por intensidad",
                      mantel_haenszel_rr([conteos(df.filter(pl.col("intensidad") == e), "sangrado_relevante")
                                          for e in ("profilactica", "terapeutica")]), df.height))
    coinciden = all(f[2].li <= 1 <= f[2].ls for f in filas)
    fig, ax = lienzo(
        "El resultado se replica al construir la cohorte sobre OMOP" if coinciden
        else "El resultado difiere entre las dos fuentes",
        "Razón de riesgos de sangrado relevante con la misma definición de cohorte en dos modelos de datos",
        nota=FUENTE.replace("PhysioNet)", "PhysioNet) y su versión OMOP v0.9")
             + "  En OMOP no hay transfusiones: el sangrado es solo la caída de Hb ≥ 2 g/dL.",
    )
    for i, (fuente, tipo, e, n) in enumerate(filas):
        y = len(filas) - 1 - i
        ax.plot([e.li, e.ls], [y, y], color=TINTA, lw=2, solid_capstyle="round")
        ax.plot(e.valor, y, "s" if tipo != "cruda" else "o", ms=9, color=TINTA if tipo != "cruda" else FONDO,
                mec=TINTA, mew=1.8, zorder=3)
        ax.text(1.04, y, f"{e.valor:.2f} ({e.li:.2f}–{e.ls:.2f})", va="center", fontsize=10.5, color=TINTA,
                transform=blended_transform_factory(ax.transAxes, ax.transData))
    ax.set_yticks(range(len(filas)), [f"{f[0]} (n = {f[3]})\nRR {f[1]}" for f in reversed(filas)], color=TINTA,
                  fontsize=10.5)
    ax.axvline(1, color=TENUE, lw=1, ls=(0, (4, 3)))
    ax.set_xscale("log")
    ax.set_xlim(0.4, 2.2)
    ax.set_xticks([0.5, 0.75, 1, 1.5, 2], ["0.5", "0.75", "1", "1.5", "2"])
    ax.minorticks_off()
    ax.set_ylim(-0.6, len(filas) - 0.4)
    for y in (1.5,):
        ax.axhline(y, color=REJILLA, lw=1)
    ax.tick_params(axis="y", length=0)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", color=REJILLA, lw=0.8)
    ax.set_axisbelow(True)
    ax.set_xlabel("Razón de riesgos (IC 95 %, escala log)")
    guardar(fig, "06_replica_omop.pdf")


# ----------------------------------------------------------------------------- main
def main() -> None:
    con = construir("mimic")
    df = tabla(con, "SELECT * FROM cohorte_analitica")
    atricion = tabla(con, "SELECT * FROM atricion")
    df_omop = tabla(construir("omop"), "SELECT * FROM cohorte_analitica")

    fig_atricion(atricion, df)
    fig_balance(df)
    fig_sangrado(df)
    fig_forest(df)
    fig_trayectorias(con)
    fig_replica({"mimic": df, "omop": df_omop})

    filas = "\n".join(f"| [{n}]({n}) | {PIES[n]} |" for n in sorted(PIES) if n[:2].isdigit())
    (SALIDA / "INDICE.md").write_text(
        "# Figuras principales\n\n"
        "Generadas con `python -m antitromboticos.figuras` (PDF vectorial). Fuente: MIMIC-IV Clinical Database "
        "Demo v2.2 (PhysioNet); la figura 06 usa además su versión OMOP v0.9. Estudio observacional descriptivo; "
        "todos los intervalos son IC 95 %.\n\n| Figura | Qué muestra |\n|---|---|\n" + filas + "\n",
        encoding="utf-8",
    )
    print(f"Figuras e INDICE.md escritos en {SALIDA.relative_to(RAIZ)}")


if __name__ == "__main__":
    main()
