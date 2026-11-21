# La historia del sangrado

> **Hilo fijado para la presentación (2026-11-20).** La pregunta confirmatoria sigue siendo la de la propuesta; este
> análisis de causas es exploratorio y post hoc.

**Pregunta:** ¿cuál es la razón primaria del sangrado en pacientes con anticoagulante, con o sin antiagregante?

**Respuesta corta:** los datos no identifican una sola causa, y la mayoría de lo que llamamos «sangrado» no tiene una
hemorragia documentada (eso no descarta que algunos hayan sangrado). De 38 eventos definidos por laboratorio o transfusión, solo 11 (29 %) tienen una hemorragia
documentada. Entre esos, el origen más frecuente es **asociada a procedimiento** (5 de 11).

Generado con `python -m antitromboticos.historia`. Cohorte: MIMIC-IV Demo v2.2, 74 pacientes.

## Hilo de la presentación

### 1. Casi la mitad «sangra», pero ¿de verdad sangra?

- **[H01](H01_que_hay_detras.pdf):** 38 de 74 pacientes cumplen la definición. Explicación más probable:
  hemorragia documentada 11, cirugía o intervención 5,
  líquidos IV 5 y **sin causa identificada 17**.
- **[H02](H02_explicacion_por_grupo.pdf):** la composición cambia por grupo: la hemorragia documentada explica
  7 eventos con la combinación y
  4 sin antiagregante.
- **[H03](H03_que_distingue.pdf):** el diagnóstico de hemorragia es lo que mejor separa a quienes tienen evento
  (11/38 vs.
  3/36). 4 de las 5 transfusiones
  ocurrieron en pacientes con hemorragia documentada. En cambio, la cirugía reciente
  (10/38 vs.
  11/36) y los líquidos IV
  (7/29 vs.
  7/19) **no son más
  frecuentes en quienes tienen evento**: por sí solos no explican las caídas.

### 2. Cuando sí hay hemorragia, ¿de dónde viene?

- **[H04](H04_sitio_hemorragia.pdf):** asociada a procedimiento (5), digestiva (3), anemia aguda por hemorragia (sin sitio) (2), urinaria (1).
- **[H05](H05_procedimiento_y_combinacion.pdf):** con procedimiento, la hemorragia documentada aparece en
  6/18 con la combinación y
  2/22 sin antiagregante; sin procedimiento, en
  1/15 y
  2/19.

### 3. Si no es hemorragia, ¿por qué cae la hemoglobina?

- **[H06](H06_hb_basal.pdf):** quien llega con Hb más alta cae más (r = 0.40). Riesgo por tercil:
  < 11.0: 38 %, 11.0–12.7: 48 %, ≥ 12.7: 68 %.
- **[H07](H07_vigilancia_temprana.pdf):** quienes tuvieron ≥ 3 Hb en las primeras 48 h tuvieron más eventos después
  (11/16 vs. 12/37; RR 2.12 (1.20–3.75)). Puede reflejar detección, flebotomía o mayor gravedad.
- **[H08](H08_modelo_multivariable.pdf):** al ajustar a la vez, Hb basal: OR 1.35 (1.05–1.74) por g/dL; combinación:
  OR 0.73 (0.25–2.14).

### 4. Entonces, ¿la combinación aumenta el sangrado?

- **[H09](H09_senal_por_definicion.pdf):** con la definición amplia, RR 0.91 (0.59–1.40). Con evento y hemorragia documentada:
  7/33 vs. 4/41, **RR 2.15 (0.72–6.37)**. La dirección es la esperada por la farmacología, pero el intervalo
  incluye el 1.

## Mensaje final

1. La caída de Hb ≥ 2 g/dL **no equivale a sangrado**: es un desenlace sensible pero poco específico.
2. Cuando hay hemorragia documentada, la fuente más frecuente es **asociada a procedimiento**.
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
- **Muestra pequeña:** 11 eventos con hemorragia documentada.

## Pies de figura

- **H01.** Explicación más probable de cada evento, con jerarquía: hemorragia documentada (CIE) > cirugía o intervención en los 2 días previos > ≥ 2 L de líquidos IV en 48 h > sin causa identificada.
- **H02.** Composición de los eventos por grupo. Cada segmento indica pacientes y porcentaje de los eventos de ese grupo.
- **H03.** Frecuencia de cada posible causa en pacientes con y sin evento, en una ventana equivalente (sin evento: alrededor del nadir de Hb). IC 95 %.
- **H04.** Sitio de la hemorragia en los 11 pacientes con evento y hemorragia documentada.
- **H05.** Riesgo de evento con hemorragia documentada según procedimiento mayor o vascular durante la hospitalización y grupo. Exploratorio: grupos muy pequeños.
- **H06.** Izquierda: Hb basal vs. caída máxima (r = 0.40). Derecha: riesgo de evento por tercil de Hb basal. Compatible con hemoconcentración al ingreso y con que una caída absoluta es más probable desde un valor alto.
- **H07.** Análisis de referencia a 48 h: pacientes aún en seguimiento y sin evento a las 48 h (n = 53), según las Hb medidas en esas 48 h. RR 2.12 (1.20–3.75). El corte de 3 se eligió después de ver los datos; más mediciones también puede reflejar pacientes más graves.
- **H08.** Regresión logística con 74 pacientes y 38 eventos. Razón de momios con IC 95 %. Solo variables conocidas al inicio. La asociación con Hb basal está en parte acoplada a la definición del desenlace (caída = basal − valor posterior).
- **H09.** RR ajustado por intensidad, de la definición más amplia a la más específica. Análisis post hoc: genera hipótesis, no las confirma.
