"""Análisis descriptivo: Tabla 1, desenlaces por grupo y forest plot.

Construye la cohorte (ver `cohorte.py`) y escribe en `resultados/` solo tablas agregadas:

* ``tabla1.csv``                características basales por grupo, con diferencia estandarizada
* ``desenlaces_binarios.csv``   riesgos con IC 95 %, diferencia y razón de riesgos, global, por
                                intensidad y combinada de Mantel-Haenszel
* ``desenlaces_continuos.csv``  mediana [RIC] por grupo
* ``resultados.md``             las tres tablas en un reporte legible

y la figura ``figuras/07_forest_rr.png``.

Con ``--fuente omop`` usa la cohorte OMOP y escribe en ``resultados/omop/`` y
``figuras/08_forest_rr_omop.png``.

Uso::

    python -m antitromboticos.analisis
    python -m antitromboticos.analisis --fuente omop
"""

from __future__ import annotations

import argparse
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import polars as pl  # noqa: E402

from antitromboticos.cohorte import FUENTES, RAIZ, construir, exportar  # noqa: E402
from antitromboticos.estadistica import (  # noqa: E402
    Estimacion,
    diferencia_riesgos,
    mantel_haenszel_rr,
    razon_riesgos,
    smd_binaria,
    smd_continua,
    wilson,
)

FIGURAS = RAIZ / "figuras"
EXPUESTO, COMPARADOR = "combinacion", "solo_anticoagulante"
ETIQUETA_GRUPO = {EXPUESTO: "Combinación", COMPARADOR: "Solo anticoagulante"}
ESTRATOS = ["profilactica", "terapeutica"]

BINARIOS = {
    "sangrado_relevante": "Sangrado relevante (principal)",
    "caida_hb_2": "Caída de Hb ≥ 2 g/dL",
    "transfusion_gr": "Transfusión de concentrado eritrocitario",
    "plaquetas_caida_50": "Caída de plaquetas ≥ 50 %",
    "trombocitopenia_nueva": "Trombocitopenia nueva (< 100k)",
    "uci_posterior": "Ingreso a UCI posterior",
    "muerte": "Muerte hospitalaria",
}
CONTINUOS = {
    "caida_hb_max": "Caída máxima de Hb (g/dL)",
    "plaquetas_cambio_pct": "Cambio de plaquetas al nadir (%)",
    "estancia_post_indice_dias": "Estancia desde la fecha índice (días)",
}

# Paleta categórica validada (slots 1 y 2) y tinta de texto
AZUL, NARANJA = "#2a78d6", "#eb6834"
TINTA, TINTA_2, REJILLA = "#0b0b0b", "#52514e", "#e4e3df"


# ----------------------------------------------------------------------------- formato
def pct(e: Estimacion) -> str:
    return "—" if math.isnan(e.valor) else f"{100 * e.valor:.0f} % ({100 * e.li:.0f}–{100 * e.ls:.0f})"


def razon(e: Estimacion) -> str:
    return "—" if math.isnan(e.valor) else f"{e.valor:.2f} ({e.li:.2f}–{e.ls:.2f})"


def dif(e: Estimacion) -> str:
    def pp(x: float) -> str:
        return f"{int(round(100 * x)):+d}"

    if math.isnan(e.valor):
        return "—"
    if math.isnan(e.li):
        return f"{pp(e.valor)} (IC no estimable)"
    return f"{pp(e.valor)} ({pp(e.li)} a {pp(e.ls)})"


def mediana_ric(s: pl.Series) -> str:
    s = s.drop_nulls()
    if s.is_empty():
        return "—"
    return f"{s.median():.1f} [{s.quantile(0.25, 'linear'):.1f}–{s.quantile(0.75, 'linear'):.1f}]"


def n_pct(s: pl.Series) -> str:
    s = s.drop_nulls()
    return f"{int(s.sum())} ({100 * s.mean():.0f} %)" if len(s) else "—"


def a_markdown(df: pl.DataFrame) -> str:
    filas = ["| " + " | ".join(df.columns) + " |", "|" + "---|" * len(df.columns)]
    filas += ["| " + " | ".join(str(v) for v in r) + " |" for r in df.iter_rows()]
    return "\n".join(filas)


# ----------------------------------------------------------------------------- tablas
def tabla1(df: pl.DataFrame) -> pl.DataFrame:
    g1, g0 = df.filter(pl.col("grupo") == EXPUESTO), df.filter(pl.col("grupo") == COMPARADOR)
    filas: list[tuple[str, str, str, str]] = [("n", str(g1.height), str(g0.height), "")]

    def continua(nombre: str, col: str) -> None:
        smd = smd_continua(g1[col].drop_nulls().to_list(), g0[col].drop_nulls().to_list())
        filas.append((nombre, mediana_ric(g1[col]), mediana_ric(g0[col]), f"{abs(smd):.2f}"))

    def binaria(nombre: str, expr: pl.Expr) -> None:
        s1, s0 = g1.select(expr).to_series(), g0.select(expr).to_series()
        smd = smd_binaria(s1.mean(), s0.mean())
        filas.append((nombre, n_pct(s1), n_pct(s0), f"{abs(smd):.2f}"))

    continua("Edad, años", "edad")
    binaria("Mujeres", pl.col("sexo") == "F")
    binaria("Estrato: médico", pl.col("estrato") == "medico")
    binaria("Estrato: quirúrgico", pl.col("estrato") == "quirurgico")
    binaria("Estrato: cirugía cardiaca", pl.col("estrato") == "cirugia_cardiaca")
    binaria("En UCI en la fecha índice", pl.col("uci_en_indice"))
    binaria("Anticoagulación terapéutica", pl.col("intensidad") == "terapeutica")
    for farmaco, etiqueta in [("HNF", "HNF"), ("enoxaparina", "Enoxaparina"), ("warfarina", "Warfarina"), ("DOAC", "DOAC")]:
        binaria(f"Anticoagulante: {etiqueta}", pl.col("anticoagulante") == farmaco)
    binaria("Fibrilación auricular", pl.col("fibrilacion_auricular"))
    binaria("Cardiopatía isquémica", pl.col("cardiopatia_isquemica"))
    binaria("Tromboembolia venosa", pl.col("tromboembolia_venosa"))
    binaria("Insuficiencia cardiaca", pl.col("insuficiencia_cardiaca"))
    continua("Plaquetas basales (×10⁹/L)", "plaquetas_basal")
    continua("Hb basal (g/dL)", "hb_basal")
    continua("Días de seguimiento", "dias_seguimiento")

    return pl.DataFrame(
        filas,
        schema=["Característica", ETIQUETA_GRUPO[EXPUESTO], ETIQUETA_GRUPO[COMPARADOR], "|DME|"],
        orient="row",
    )


def conteos(df: pl.DataFrame, col: str) -> tuple[int, int, int, int]:
    """(a, n1, c, n0) para un desenlace binario, omitiendo valores nulos."""
    d = df.filter(pl.col(col).is_not_null())
    g1, g0 = d.filter(pl.col("grupo") == EXPUESTO), d.filter(pl.col("grupo") == COMPARADOR)
    return int(g1[col].sum()), g1.height, int(g0[col].sum()), g0.height


def desenlaces_binarios(df: pl.DataFrame) -> pl.DataFrame:
    filas = []
    for col, etiqueta in BINARIOS.items():
        if df[col].null_count() == df.height:  # desenlace no disponible en esta fuente (p. ej. transfusión en OMOP)
            continue
        bloques = [("Todos", df)] + [(e, df.filter(pl.col("intensidad") == e)) for e in ESTRATOS]
        for estrato, sub in bloques:
            a, n1, c, n0 = conteos(sub, col)
            rr = razon_riesgos(a, n1, c, n0)
            filas.append({
                "desenlace": col, "etiqueta": etiqueta, "estrato": estrato,
                "a": a, "n1": n1, "c": c, "n0": n0,
                "riesgo_combinacion": pct(wilson(a, n1)), "riesgo_solo_ac": pct(wilson(c, n0)),
                "dif_riesgos_pp": dif(diferencia_riesgos(a, n1, c, n0)), "razon_riesgos": razon(rr),
                "rr": rr.valor, "rr_li": rr.li, "rr_ls": rr.ls,
            })
        mh = mantel_haenszel_rr([conteos(df.filter(pl.col("intensidad") == e), col) for e in ESTRATOS])
        filas.append({
            "desenlace": col, "etiqueta": etiqueta, "estrato": "Mantel-Haenszel",
            "a": None, "n1": None, "c": None, "n0": None,
            "riesgo_combinacion": "", "riesgo_solo_ac": "", "dif_riesgos_pp": "", "razon_riesgos": razon(mh),
            "rr": mh.valor, "rr_li": mh.li, "rr_ls": mh.ls,
        })
    return pl.DataFrame(filas)


def desenlaces_continuos(df: pl.DataFrame) -> pl.DataFrame:
    filas = []
    for col, etiqueta in CONTINUOS.items():
        g1, g0 = df.filter(pl.col("grupo") == EXPUESTO), df.filter(pl.col("grupo") == COMPARADOR)
        filas.append({
            "Desenlace": etiqueta,
            ETIQUETA_GRUPO[EXPUESTO]: mediana_ric(g1[col]),
            ETIQUETA_GRUPO[COMPARADOR]: mediana_ric(g0[col]),
        })
    return pl.DataFrame(filas)


# ----------------------------------------------------------------------------- figura
def forest_plot(bin_: pl.DataFrame, destino: Path) -> None:
    """Razón de riesgos cruda y ajustada por intensidad (Mantel-Haenszel), escala logarítmica."""
    lim_inf, lim_sup = 0.05, 20.0
    disponibles = set(bin_["desenlace"].to_list())
    desenlaces = [c for c in BINARIOS if c in disponibles]
    fig, ax = plt.subplots(figsize=(8.5, 0.62 * len(desenlaces) + 1.4))

    for i, col in enumerate(desenlaces):
        y = len(desenlaces) - 1 - i
        for estrato, color, marca, dy, nombre in [
            ("Todos", AZUL, "o", 0.14, "Cruda"),
            ("Mantel-Haenszel", NARANJA, "s", -0.14, "Ajustada por intensidad (M-H)"),
        ]:
            r = bin_.filter((pl.col("desenlace") == col) & (pl.col("estrato") == estrato)).row(0, named=True)
            if r["rr"] is None or math.isnan(r["rr"]):
                continue
            li, ls = max(r["rr_li"], lim_inf), min(r["rr_ls"], lim_sup)
            ax.plot([li, ls], [y + dy, y + dy], color=color, lw=2, solid_capstyle="round")
            ax.plot(r["rr"], y + dy, marca, color=color, ms=8, mec="white", mew=1.5,
                    label=nombre if i == 0 else None, zorder=3)
            if r["rr_ls"] > lim_sup:
                ax.annotate("", xy=(lim_sup, y + dy), xytext=(lim_sup * 0.8, y + dy),
                            arrowprops=dict(arrowstyle="->", color=color, lw=1.5))
        todos = bin_.filter((pl.col("desenlace") == col) & (pl.col("estrato") == "Todos")).row(0, named=True)
        ax.text(lim_sup * 1.25, y, f"{todos['a']}/{todos['n1']}  vs  {todos['c']}/{todos['n0']}",
                va="center", fontsize=9, color=TINTA_2)

    ax.axvline(1, color=TINTA_2, lw=1, ls=(0, (4, 3)))
    ax.set_xscale("log")
    ax.set_xlim(lim_inf, lim_sup)
    ax.set_xticks([0.1, 0.25, 0.5, 1, 2, 4, 10])
    ax.set_xticklabels(["0.1", "0.25", "0.5", "1", "2", "4", "10"])
    ax.set_yticks(range(len(desenlaces)))
    ax.set_yticklabels([BINARIOS[c] for c in reversed(desenlaces)], color=TINTA)
    ax.tick_params(colors=TINTA_2, length=0)
    ax.grid(axis="x", color=REJILLA, lw=0.8)
    ax.set_axisbelow(True)
    for lado in ("top", "right", "left"):
        ax.spines[lado].set_visible(False)
    ax.spines["bottom"].set_color(REJILLA)
    ax.set_xlabel("Razón de riesgos, combinación vs. solo anticoagulante (IC 95 %, escala log)", color=TINTA_2)
    ax.text(lim_sup * 1.25, len(desenlaces) - 0.35, "eventos/n", fontsize=9, color=TINTA_2, va="bottom")
    ax.set_title("Desenlaces con anticoagulante + antiagregante", loc="left", color=TINTA, fontsize=12, pad=26)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, frameon=False, fontsize=9, borderaxespad=0.2)
    ax.text(1, -0.12, "← menor riesgo con la combinación   ·   mayor riesgo →", transform=ax.get_xaxis_transform(),
            ha="center", va="top", fontsize=8, color=TINTA_2)
    fig.savefig(destino, dpi=150, bbox_inches="tight", facecolor="#fcfcfb")
    plt.close(fig)


# ----------------------------------------------------------------------------- main
def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--fuente", choices=list(FUENTES), default="mimic")
    args = parser.parse_args()

    con = construir(args.fuente)
    df = pl.read_parquet(exportar(con, args.fuente))
    salida = FUENTES[args.fuente].resultados
    figura = "07_forest_rr.png" if args.fuente == "mimic" else f"08_forest_rr_{args.fuente}.png"

    t1 = tabla1(df)
    bin_ = desenlaces_binarios(df)
    cont = desenlaces_continuos(df)

    salida.mkdir(parents=True, exist_ok=True)
    FIGURAS.mkdir(exist_ok=True)
    t1.write_csv(salida / "tabla1.csv")
    bin_.drop("rr", "rr_li", "rr_ls").write_csv(salida / "desenlaces_binarios.csv")
    cont.write_csv(salida / "desenlaces_continuos.csv")
    forest_plot(bin_, FIGURAS / figura)

    tabla_bin = bin_.select(
        pl.col("etiqueta").alias("Desenlace"),
        pl.col("estrato").alias("Estrato"),
        pl.col("riesgo_combinacion").alias("Combinación, % (IC 95 %)"),
        pl.col("riesgo_solo_ac").alias("Solo AC, % (IC 95 %)"),
        pl.col("dif_riesgos_pp").alias("Diferencia, pp (IC 95 %)"),
        pl.col("razon_riesgos").alias("RR (IC 95 %)"),
    )
    nota_fuente = (
        "Fuente: MIMIC-IV Demo v2.2, tablas nativas."
        if args.fuente == "mimic"
        else "Fuente: MIMIC-IV demo en OMOP CDM 5.3.1 (v0.9). Sin transfusiones: el sangrado relevante "
             "es solo la caída de Hb ≥ 2 g/dL. Sin exclusión por diagnóstico principal de sangrado. "
             "Ver docs/omop.md."
    )
    reporte = "\n\n".join([
        f"# Resultados ({args.fuente})",
        nota_fuente,
        f"Generado por `python -m antitromboticos.analisis --fuente {args.fuente}`. "
        "Combinación = anticoagulante + antiagregante; "
        "comparador = solo anticoagulante. |DME| = diferencia de medias estandarizada (> 0.10 sugiere desbalance). "
        "Riesgos con IC de Wilson; diferencia con IC de Wald; RR con IC logarítmico (corrección de Haldane "
        "si un grupo tiene 0 eventos); RR de Mantel-Haenszel combinado entre estratos de intensidad.",
        "## Tabla 1. Características basales", a_markdown(t1),
        "## Tabla 2. Desenlaces binarios", a_markdown(tabla_bin),
        "## Tabla 3. Desenlaces continuos, mediana [RIC]", a_markdown(cont),
        "## Figura", f"![Forest plot]({'../' * (len(salida.relative_to(RAIZ).parts))}figuras/{figura})",
    ])
    (salida / "resultados.md").write_text(reporte + "\n", encoding="utf-8")

    with pl.Config(tbl_rows=50, tbl_cols=10, fmt_str_lengths=40, tbl_width_chars=200):
        print(t1)
        print(tabla_bin)
        print(cont)


if __name__ == "__main__":
    main()
