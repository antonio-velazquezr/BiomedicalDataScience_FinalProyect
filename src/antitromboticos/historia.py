"""La historia del sangrado: ¿qué hay detrás de cada caída de hemoglobina?

Escribe en ``figuras/historia/`` nueve figuras en PDF, en orden narrativo, y ``HISTORIA.md`` con el
hilo conductor. Los números se calculan con los datos; varios títulos son interpretaciones fijas,
así que deben revisarse si cambian la cohorte o las definiciones.

Las explicaciones son **probables, no causales**: los diagnósticos CIE no tienen fecha, los
procedimientos solo tienen día y los líquidos solo se registran en UCI.

Uso::

    python -m antitromboticos.historia
"""

from __future__ import annotations

import math

import matplotlib.pyplot as plt
import numpy as np
import polars as pl

from antitromboticos.cohorte import FUENTES, RAIZ, SQL_DIR, construir
from antitromboticos.estadistica import Estimacion, Z95, razon_riesgos, regresion_logistica, wilson
from antitromboticos.figuras import (
    COLOR, FONDO, GRUPOS, NOMBRE, PIES, REJILLA, TENUE, TINTA, TINTA2, guardar, leyenda_figura, lienzo, tabla,
)
from antitromboticos.preguntas import conteos, cruza_uno, ejes_limpios, fmt, forest, rr_ajustado

SALIDA = RAIZ / "figuras" / "historia"
EXPLICACIONES = ["Hemorragia documentada", "Cirugía o intervención", "Líquidos IV ≥ 2 L", "Sin causa identificada"]
COLOR_EXPL = dict(zip(EXPLICACIONES, ["#6250d6", "#1baf7a", "#eda100", "#b8b7b1"]))


def cargar() -> pl.DataFrame:
    con = construir("mimic")
    datos = FUENTES["mimic"].datos.as_posix()
    for t in ("procedures_icd", "d_icd_procedures", "d_icd_diagnoses"):
        con.execute(f"CREATE OR REPLACE VIEW {t} AS SELECT * FROM read_csv('{datos}/hosp/{t}.csv.gz', "
                    "sample_size = -1, types = {'icd_code': 'VARCHAR'})")
    con.execute((SQL_DIR / "historia" / "01_causas_sangrado.sql").read_text(encoding="utf-8"))
    return tabla(con, "SELECT * FROM causas")


def pct(a: int, n: int) -> str:
    return f"{100 * a / n:.0f} %" if n else "—"


def punto_ic(ax, x, a, n, color, etiqueta=True, dx=0.05):
    e = wilson(a, n)
    ax.plot([x, x], [100 * e.li, 100 * e.ls], color=color, lw=2.5, solid_capstyle="round")
    ax.plot(x, 100 * e.valor, "o", ms=10, color=color, mec=FONDO, mew=1.4, zorder=3)
    if etiqueta:
        ax.text(x + dx, 100 * e.valor, f"{100 * e.valor:.0f} %\n{a}/{n}", va="center", fontsize=9.5, color=TINTA2)


def eje_pct(ax, tope=100):
    ax.set_ylim(0, tope)
    ax.yaxis.set_major_formatter(lambda v, _: f"{v:.0f} %")
    ejes_limpios(ax)


# ----------------------------------------------------------------------------- acto 1: qué es el "sangrado"
def h01_explicaciones(df) -> dict:
    ev = df.filter(pl.col("sangrado_relevante"))
    n = {e: ev.filter(pl.col("explicacion") == e).height for e in EXPLICACIONES}
    fig, ax = lienzo(f"Solo {n[EXPLICACIONES[0]]} de {ev.height} «sangrados» tienen una hemorragia documentada",
                     "Explicación más probable de cada evento, con jerarquía: hemorragia documentada (CIE) > cirugía o "
                     "intervención en los 2 días previos > ≥ 2 L de líquidos IV en 48 h > sin causa identificada",
                     figsize=(9, 4.6))
    y = range(len(EXPLICACIONES))
    ax.barh(y, [n[e] for e in EXPLICACIONES], color=[COLOR_EXPL[e] for e in EXPLICACIONES], height=0.62)
    for i, e in enumerate(EXPLICACIONES):
        ax.text(n[e] + 0.3, i, f"{n[e]} ({pct(n[e], ev.height)})", va="center", color=TINTA)
    ax.set_yticks(list(y), EXPLICACIONES, color=TINTA)
    ax.invert_yaxis()
    ax.set_xlim(0, max(n.values()) * 1.2)
    ax.set_xlabel(f"Pacientes con caída de Hb ≥ 2 g/dL o transfusión (n = {ev.height})")
    ax.xaxis.get_major_locator().set_params(integer=True)
    ax.tick_params(axis="y", length=0)
    ejes_limpios(ax, "x")
    guardar(fig, "H01_que_hay_detras.pdf", SALIDA)
    return {"n": n, "total": ev.height}


def h02_por_grupo(df) -> dict:
    ev = df.filter(pl.col("sangrado_relevante"))
    fig, ax = lienzo("La hemorragia documentada pesa más en el grupo con la combinación",
                     "Composición de los eventos por grupo. Cada segmento indica pacientes y porcentaje de los eventos de "
                     "ese grupo", figsize=(9.5, 4.2))
    salida = {}
    for k, g in enumerate(GRUPOS):
        sub = ev.filter(pl.col("grupo") == g)
        izq = 0.0
        for e in EXPLICACIONES:
            c = sub.filter(pl.col("explicacion") == e).height
            ancho = 100 * c / sub.height
            ax.barh(k, ancho, left=izq, color=COLOR_EXPL[e], edgecolor=FONDO, lw=2, height=0.6,
                    label=e if k == 0 else None)
            if c:
                ax.text(izq + ancho / 2, k, f"{c} ({ancho:.0f} %)", ha="center", va="center", fontsize=9.5, color=TINTA)
            izq += ancho
            salida[(g, e)] = c
    ax.set_yticks([0, 1], [f"{NOMBRE[g]}\n({ev.filter(pl.col('grupo') == g).height} eventos)" for g in GRUPOS], color=TINTA)
    ax.invert_yaxis()
    ax.set_xlim(0, 100)
    ax.xaxis.set_major_formatter(lambda v, _: f"{v:.0f} %")
    ax.tick_params(axis="y", length=0)
    fig.legend(loc="outside lower center", ncol=4, frameon=False, fontsize=9.5)
    guardar(fig, "H02_explicacion_por_grupo.pdf", SALIDA)
    return salida


def h03_que_distingue(df) -> dict:
    variables = [("Hemorragia documentada", "hemorragia_cie", df),
                 ("Cirugía o intervención (≤ 2 días)", "cirugia_48h", df),
                 ("Líquidos IV ≥ 2 L en 48 h (solo UCI)", "liquidos_2l", df.filter(pl.col("uci_ventana")))]
    resultado = {}
    for nombre, col, d in variables:
        si, no = d.filter(pl.col("sangrado_relevante")), d.filter(~pl.col("sangrado_relevante"))
        resultado[nombre] = (int(si[col].sum()), si.height, int(no[col].sum()), no.height)
    mayor = max(resultado, key=lambda k: razon_riesgos(*resultado[k]).valor)
    fig, ax = lienzo(f"Lo que más separa a quienes caen de quienes no: {mayor.split(' (')[0].lower()}",
                     "Frecuencia de cada posible causa en pacientes con y sin evento, en una ventana equivalente (sin "
                     "evento: alrededor del nadir de Hb). IC 95 %", figsize=(9.5, 5))
    colores = {"ev": "#6250d6", "no": TENUE}
    for i, (nombre, (a, n1, c, n0)) in enumerate(resultado.items()):
        punto_ic(ax, i - 0.14, a, n1, colores["ev"])
        punto_ic(ax, i + 0.14, c, n0, colores["no"])
    ax.set_xticks(range(len(resultado)), [k.replace(" (", "\n(") for k in resultado], color=TINTA)
    ax.set_xlim(-0.5, len(resultado) - 0.3)
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel("Pacientes")
    eje_pct(ax, 70)
    ax.plot([], [], "o", color=colores["ev"], ms=9, label="Con caída de Hb o transfusión")
    ax.plot([], [], "o", color=colores["no"], ms=9, label="Sin evento")
    fig.legend(loc="outside lower center", ncol=2, frameon=False, fontsize=10)
    guardar(fig, "H03_que_distingue.pdf", SALIDA)
    return resultado


# ----------------------------------------------------------------------------- acto 2: de dónde viene
def h04_sitio(df) -> dict:
    d = df.filter(pl.col("sangrado_documentado"))
    conteo = {s: [d.filter((pl.col("sitio") == s) & (pl.col("grupo") == g)).height for g in GRUPOS]
              for s in d["sitio"].unique().to_list()}
    orden = sorted(conteo, key=lambda s: -sum(conteo[s]))
    fig, ax = lienzo(f"El origen documentado más frecuente: {orden[0].lower()}",
                     f"Sitio de la hemorragia en los {d.height} pacientes con evento y hemorragia documentada",
                     figsize=(9, 4.4))
    izq = np.zeros(len(orden))
    for k, g in enumerate(GRUPOS):
        v = np.array([conteo[s][k] for s in orden])
        ax.barh(range(len(orden)), v, left=izq, color=COLOR[g], edgecolor=FONDO, lw=2, height=0.6)
        for i, x in enumerate(v):
            if x:
                ax.text(izq[i] + x / 2, i, str(x), ha="center", va="center", color=FONDO, fontweight="bold")
        izq += v
    ax.set_yticks(range(len(orden)), orden, color=TINTA)
    ax.invert_yaxis()
    ax.set_xlabel("Pacientes")
    ax.xaxis.get_major_locator().set_params(integer=True)
    ax.tick_params(axis="y", length=0)
    ejes_limpios(ax, "x")
    leyenda_figura(fig)
    guardar(fig, "H04_sitio_hemorragia.pdf", SALIDA)
    return {"orden": orden, "conteo": conteo, "total": d.height}


def h05_procedimiento(df) -> dict:
    fig, ax = lienzo("La hemorragia documentada se concentra en quienes tienen combinación y procedimiento",
                     "Riesgo de evento con hemorragia documentada según procedimiento mayor o vascular durante la "
                     "hospitalización y grupo. Exploratorio: grupos muy pequeños", figsize=(9.5, 5))
    res = {}
    for i, (proc, nombre) in enumerate(((False, "Sin procedimiento"), (True, "Con procedimiento"))):
        sub = df.filter(pl.col("procedimiento_hosp") == proc)
        for g, dx in zip(GRUPOS, (-0.13, 0.13)):
            s = sub.filter(pl.col("grupo") == g)
            a, n = int(s["sangrado_documentado"].sum()), s.height
            punto_ic(ax, i + dx, a, n, COLOR[g])
            res[(proc, g)] = (a, n)
    ax.set_xticks([0, 1], ["Sin procedimiento", "Con procedimiento"], color=TINTA)
    ax.set_xlim(-0.5, 1.6)
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel("Evento con hemorragia documentada")
    eje_pct(ax, 80)
    leyenda_figura(fig)
    guardar(fig, "H05_procedimiento_y_combinacion.pdf", SALIDA)
    return res


# ----------------------------------------------------------------------------- acto 3: por qué cae la Hb sin hemorragia
def h06_hb_basal(df) -> dict:
    d = df.filter(pl.col("caida_hb_max").is_not_null())
    x, y = d["hb_basal"].to_numpy(), d["caida_hb_max"].to_numpy()
    r = float(np.corrcoef(x, y)[0, 1])
    fig, axes = lienzo("Quien llega con la hemoglobina más alta tiene más margen para caer",
                       f"Izquierda: Hb basal vs. caída máxima (r = {r:.2f}). Derecha: riesgo de evento por tercil de Hb "
                       "basal. Compatible con hemoconcentración al ingreso y con que una caída absoluta es más probable "
                       "desde un valor alto", ncols=2, figsize=(10.5, 4.8))
    ax = axes[0]
    for g in GRUPOS:
        s = d.filter(pl.col("grupo") == g)
        ax.scatter(s["hb_basal"], s["caida_hb_max"], s=34, color=COLOR[g], alpha=0.7, lw=0)
    m, b = np.polyfit(x, y, 1)
    xs = np.array([x.min(), x.max()])
    ax.plot(xs, m * xs + b, color=TINTA, lw=1.8)
    ax.axhline(2, color=TENUE, lw=1, ls=(0, (4, 3)))
    ax.set_xlabel("Hb basal (g/dL)")
    ax.set_ylabel("Caída máxima de Hb (g/dL)")
    ejes_limpios(ax)
    ax = axes[1]
    q1, q2 = np.quantile(df["hb_basal"].to_numpy(), [1 / 3, 2 / 3])
    bandas = [(f"< {q1:.1f}", pl.col("hb_basal") < q1), (f"{q1:.1f}–{q2:.1f}", (pl.col("hb_basal") >= q1) & (pl.col("hb_basal") < q2)),
              (f"≥ {q2:.1f}", pl.col("hb_basal") >= q2)]
    riesgos = []
    for i, (_, cond) in enumerate(bandas):
        s = df.filter(cond)
        a, n = int(s["sangrado_relevante"].sum()), s.height
        punto_ic(ax, i, a, n, TINTA, dx=0.08)
        riesgos.append((a, n))
    ax.set_xticks(range(3), [b[0] for b in bandas], color=TINTA)
    ax.set_xlim(-0.4, 2.6)
    ax.set_xlabel("Tercil de Hb basal (g/dL)")
    ax.set_ylabel("Pacientes con evento")
    eje_pct(ax)
    leyenda_figura(fig)
    guardar(fig, "H06_hb_basal.pdf", SALIDA)
    return {"r": r, "riesgos": riesgos, "bandas": [b[0] for b in bandas]}


def h07_vigilancia(df, corte: int = 3) -> dict:
    d = df.filter((pl.col("dias_seguimiento") > 2) &
                  (pl.col("t_evento").is_null() | (pl.col("t_evento") > pl.col("t_indice") + pl.duration(hours=48))))
    alta, baja = d.filter(pl.col("n_hb_48h") >= corte), d.filter(pl.col("n_hb_48h") < corte)
    a, n1, c, n0 = int(alta["sangrado_relevante"].sum()), alta.height, int(baja["sangrado_relevante"].sum()), baja.height
    rr = razon_riesgos(a, n1, c, n0)
    fig, ax = lienzo("Medir más la hemoglobina temprano anticipa más eventos después",
                     f"Análisis de referencia a 48 h: pacientes aún en seguimiento y sin evento a las 48 h (n = {d.height}), "
                     f"según las Hb medidas en esas 48 h. RR {fmt(rr)}. El corte de {corte} se eligió después de ver los "
                     "datos; más mediciones también puede reflejar pacientes más graves", figsize=(7.5, 4.8))
    punto_ic(ax, 0, c, n0, TENUE, dx=0.04)
    punto_ic(ax, 1, a, n1, "#6250d6", dx=0.04)
    ax.set_xticks([0, 1], [f"< {corte} Hb en 48 h", f"≥ {corte} Hb en 48 h"], color=TINTA)
    ax.set_xlim(-0.5, 1.6)
    ax.tick_params(axis="x", length=0)
    ax.set_ylabel("Evento después de las 48 h")
    eje_pct(ax)
    guardar(fig, "H07_vigilancia_temprana.pdf", SALIDA)
    return {"a": a, "n1": n1, "c": c, "n0": n0, "rr": rr, "n": d.height}


def h08_modelo(df) -> dict:
    d = df.with_columns(
        (pl.col("grupo") == "combinacion").cast(pl.Float64).alias("combinacion"),
        (pl.col("hb_basal") - pl.col("hb_basal").mean()).alias("hb"),
        ((pl.col("edad") - pl.col("edad").mean()) / 10).alias("edad10"),
        pl.col("uci_en_indice").cast(pl.Float64).alias("uci"),
        (pl.col("estrato") != "medico").cast(pl.Float64).alias("quirurgico"),
    )
    nombres = [("combinacion", "Combinación (vs. solo anticoagulante)"), ("hb", "Hb basal (por cada 1 g/dL)"),
               ("edad10", "Edad (por cada 10 años)"), ("uci", "En UCI en la fecha índice"),
               ("quirurgico", "Paciente quirúrgico")]
    X = np.column_stack([np.ones(d.height)] + [d[c].to_numpy() for c, _ in nombres])
    beta, ee = regresion_logistica(X, d["sangrado_relevante"].cast(pl.Float64).to_numpy())
    filas, odds = [], {}
    for i, (c, etq) in enumerate(nombres, 1):
        e = Estimacion(math.exp(beta[i]), math.exp(beta[i] - Z95 * ee[i]), math.exp(beta[i] + Z95 * ee[i]))
        filas.append((etq, e, ""))
        odds[c] = e
    claros = [etq for etq, e, _ in filas if not cruza_uno(e)]
    solo_hb = claros == ["Hb basal (por cada 1 g/dL)"]
    fig, ax = lienzo("Al ajustar, solo la Hb basal muestra una asociación clara con el evento" if solo_hb
                     else "Modelo multivariable de caída de Hb o transfusión",
                     f"Regresión logística con {d.height} pacientes y {int(d['sangrado_relevante'].sum())} eventos. Razón de "
                     "momios con IC 95 %. Solo variables conocidas al inicio. La asociación con Hb basal está en parte "
                     "acoplada a la definición del desenlace (caída = basal − valor posterior)", figsize=(9.5, 4.4))
    forest(ax, filas, lim=(0.25, 4), xlabel="Razón de momios (IC 95 %, escala log)")
    guardar(fig, "H08_modelo_multivariable.pdf", SALIDA)
    return {"odds": odds, "claros": claros}


# ----------------------------------------------------------------------------- acto 4: la señal
def h09_especificidad(df) -> dict:
    definiciones = [("Caída de Hb ≥ 1 g/dL", "caida_1"), ("Sangrado relevante (principal)", "sangrado_relevante"),
                    ("Caída de Hb ≥ 3 g/dL", "caida_3"), ("Caída de Hb ≥ 4 g/dL", "caida_4"),
                    ("Evento con hemorragia documentada", "sangrado_documentado")]
    filas, res = [], {}
    for etq, col in definiciones:
        a, n1, c, n0 = conteos(df, col)
        e = rr_ajustado(df, col=col)
        filas.append((etq, e, f"{a}/{n1} vs. {c}/{n0}"))
        res[col] = (e, a, n1, c, n0)
    fig, ax = lienzo("Con una definición más específica, la señal de la combinación aumenta, sin ser concluyente",
                     "RR ajustado por intensidad, de la definición más amplia a la más específica. Análisis post hoc: "
                     "genera hipótesis, no las confirma", figsize=(10, 4.8))
    forest(ax, filas, lim=(0.25, 10), resaltar={len(filas) - 1})
    guardar(fig, "H09_senal_por_definicion.pdf", SALIDA)
    return res


# ----------------------------------------------------------------------------- narrativa
def escribir_historia(df, r) -> None:
    n, total = r["h01"]["n"], r["h01"]["total"]
    doc = n["Hemorragia documentada"]
    h9 = r["h09"]
    e_doc, a, n1, c, n0 = h9["sangrado_documentado"]
    e_pri = h9["sangrado_relevante"][0]
    tx = int(df.filter(pl.col("transfusion_gr"))["transfusion_gr"].sum())
    tx_doc = df.filter(pl.col("transfusion_gr") & pl.col("hemorragia_cie")).height
    sitio = r["h04"]
    proc = r["h05"]
    h6, h7, h8 = r["h06"], r["h07"], r["h08"]
    texto = f"""# La historia del sangrado

> **Hilo fijado para la presentación (2026-11-20).** La pregunta confirmatoria sigue siendo la de la propuesta; este
> análisis de causas es exploratorio y post hoc.

**Pregunta:** ¿cuál es la razón primaria del sangrado en pacientes con anticoagulante, con o sin antiagregante?

**Respuesta corta:** los datos no identifican una sola causa, y la mayoría de lo que llamamos «sangrado» no tiene una
hemorragia documentada (eso no descarta que algunos hayan sangrado). De {total} eventos definidos por laboratorio o transfusión, solo {doc} ({pct(doc, total)}) tienen una hemorragia
documentada. Entre esos, el origen más frecuente es **{sitio['orden'][0].lower()}** ({sum(sitio['conteo'][sitio['orden'][0]])} de {sitio['total']}).

Generado con `python -m antitromboticos.historia`. Cohorte: MIMIC-IV Demo v2.2, {df.height} pacientes.

## Hilo de la presentación

### 1. Casi la mitad «sangra», pero ¿de verdad sangra?

- **[H01](H01_que_hay_detras.pdf):** {total} de {df.height} pacientes cumplen la definición. Explicación más probable:
  hemorragia documentada {n['Hemorragia documentada']}, cirugía o intervención {n['Cirugía o intervención']},
  líquidos IV {n['Líquidos IV ≥ 2 L']} y **sin causa identificada {n['Sin causa identificada']}**.
- **[H02](H02_explicacion_por_grupo.pdf):** la composición cambia por grupo: la hemorragia documentada explica
  {r['h02'][('combinacion', 'Hemorragia documentada')]} eventos con la combinación y
  {r['h02'][('solo_anticoagulante', 'Hemorragia documentada')]} sin antiagregante.
- **[H03](H03_que_distingue.pdf):** el diagnóstico de hemorragia es lo que mejor separa a quienes tienen evento
  ({r['h03']['Hemorragia documentada'][0]}/{r['h03']['Hemorragia documentada'][1]} vs.
  {r['h03']['Hemorragia documentada'][2]}/{r['h03']['Hemorragia documentada'][3]}). {tx_doc} de las {tx} transfusiones
  ocurrieron en pacientes con hemorragia documentada. En cambio, la cirugía reciente
  ({r['h03']['Cirugía o intervención (≤ 2 días)'][0]}/{r['h03']['Cirugía o intervención (≤ 2 días)'][1]} vs.
  {r['h03']['Cirugía o intervención (≤ 2 días)'][2]}/{r['h03']['Cirugía o intervención (≤ 2 días)'][3]}) y los líquidos IV
  ({r['h03']['Líquidos IV ≥ 2 L en 48 h (solo UCI)'][0]}/{r['h03']['Líquidos IV ≥ 2 L en 48 h (solo UCI)'][1]} vs.
  {r['h03']['Líquidos IV ≥ 2 L en 48 h (solo UCI)'][2]}/{r['h03']['Líquidos IV ≥ 2 L en 48 h (solo UCI)'][3]}) **no son más
  frecuentes en quienes tienen evento**: por sí solos no explican las caídas.

### 2. Cuando sí hay hemorragia, ¿de dónde viene?

- **[H04](H04_sitio_hemorragia.pdf):** {', '.join(f"{s.lower()} ({sum(sitio['conteo'][s])})" for s in sitio['orden'])}.
- **[H05](H05_procedimiento_y_combinacion.pdf):** con procedimiento, la hemorragia documentada aparece en
  {proc[(True, 'combinacion')][0]}/{proc[(True, 'combinacion')][1]} con la combinación y
  {proc[(True, 'solo_anticoagulante')][0]}/{proc[(True, 'solo_anticoagulante')][1]} sin antiagregante; sin procedimiento, en
  {proc[(False, 'combinacion')][0]}/{proc[(False, 'combinacion')][1]} y
  {proc[(False, 'solo_anticoagulante')][0]}/{proc[(False, 'solo_anticoagulante')][1]}.

### 3. Si no es hemorragia, ¿por qué cae la hemoglobina?

- **[H06](H06_hb_basal.pdf):** quien llega con Hb más alta cae más (r = {h6['r']:.2f}). Riesgo por tercil:
  {', '.join(f"{b}: {pct(x, m)}" for b, (x, m) in zip(h6['bandas'], h6['riesgos']))}.
- **[H07](H07_vigilancia_temprana.pdf):** quienes tuvieron ≥ 3 Hb en las primeras 48 h tuvieron más eventos después
  ({h7['a']}/{h7['n1']} vs. {h7['c']}/{h7['n0']}; RR {fmt(h7['rr'])}). Puede reflejar detección, flebotomía o mayor gravedad.
- **[H08](H08_modelo_multivariable.pdf):** al ajustar a la vez, Hb basal: OR {fmt(h8['odds']['hb'])} por g/dL; combinación:
  OR {fmt(h8['odds']['combinacion'])}.

### 4. Entonces, ¿la combinación aumenta el sangrado?

- **[H09](H09_senal_por_definicion.pdf):** con la definición amplia, RR {fmt(e_pri)}. Con evento y hemorragia documentada:
  {a}/{n1} vs. {c}/{n0}, **RR {fmt(e_doc)}**. La dirección es la esperada por la farmacología, pero el intervalo
  {'incluye' if cruza_uno(e_doc) else 'no incluye'} el 1.

## Mensaje final

1. La caída de Hb ≥ 2 g/dL **no equivale a sangrado**: es un desenlace sensible pero poco específico.
2. Cuando hay hemorragia documentada, la fuente más frecuente es **{sitio['orden'][0].lower()}**.
3. La combinación **podría** aumentar el sangrado verdadero, pero estos datos solo permiten plantearlo como hipótesis.
4. Siguiente paso: repetir el análisis, ya definido, en MIMIC-IV completo.

## Cautelas para decirlas en voz alta

- **No es causalidad.** Las categorías son explicaciones probables y la jerarquía influye en los conteos.
- **Análisis post hoc.** Esta historia surgió después de ver los datos; H05, H07 y H09 generan hipótesis.
- **Los CIE no tienen fecha.** Una hemorragia documentada pudo ocurrir antes de la fecha índice, y el código pudo
  asignarse justamente porque se observó la caída de Hb.
- **Los procedimientos solo tienen día**, y los **líquidos solo se miden en UCI**: «sin causa identificada» incluye
  pacientes de piso cuyo aporte de líquidos no conocemos.
- **La flebotomía no se midió en volumen.**
- **Acoplamiento matemático en H06.** La caída se calcula como basal − nadir, así que parte de su correlación con la Hb
  basal es aritmética y regresión a la media. No demuestra por sí sola hemoconcentración.
- **Muestra pequeña:** {doc} eventos con hemorragia documentada.

## Pies de figura

""" + "\n".join(f"- **{k.split('_')[0]}.** {v}" for k, v in sorted(PIES.items()) if k.startswith("H")) + "\n"
    (SALIDA / "HISTORIA.md").write_text(texto, encoding="utf-8")


def main() -> None:
    df = cargar()
    r = {
        "h01": h01_explicaciones(df), "h02": h02_por_grupo(df), "h03": h03_que_distingue(df), "h04": h04_sitio(df),
        "h05": h05_procedimiento(df), "h06": h06_hb_basal(df), "h07": h07_vigilancia(df), "h08": h08_modelo(df),
        "h09": h09_especificidad(df),
    }
    plt.close("all")
    escribir_historia(df, r)
    print(f"{len(r)} figuras y HISTORIA.md en {SALIDA.relative_to(RAIZ)}")
    print("OR:", {k: fmt(v) for k, v in r["h08"]["odds"].items()})
    print("RR:", {k: (fmt(v[0]), f"{v[1]}/{v[2]} vs {v[3]}/{v[4]}") for k, v in r["h09"].items()})
    print("H07:", r["h07"]["a"], r["h07"]["n1"], r["h07"]["c"], r["h07"]["n0"], fmt(r["h07"]["rr"]))
    print("H05:", r["h05"])


if __name__ == "__main__":
    main()
