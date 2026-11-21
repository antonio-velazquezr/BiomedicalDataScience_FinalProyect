# Validación: cohorte OMOP vs. cohorte nativa

Generado por `python -m antitromboticos.validacion_omop`. Compara paciente por paciente la cohorte
construida sobre OMOP CDM (`sql/omop/`) con la construida sobre las tablas nativas de MIMIC (`sql/`).

## Pertenencia a la cohorte

| | Pacientes |
|---|---|
| En ambas cohortes | 74 |
| Solo en la nativa | 0 |
| Solo en OMOP | 6 |
| … de ellos, excluidos en la nativa por diagnóstico principal de sangrado | 6 |
| En ambas, con la misma hospitalización índice | 71 |

## Concordancia de variables (pacientes en ambas, misma hospitalización)

| Variable | Concordancia |
|---|---|
| Grupo de exposición | 71/71 (100 %) |
| Intensidad | 70/71 (99 %) |
| Fecha índice | 69/71 (97 %) |
| Estrato (servicio vs. unidades) | 53/71 (75 %) |
| Caída de Hb ≥ 2 g/dL | 70/71 (99 %) |
| UCI posterior | 68/71 (96 %) |
| Muerte hospitalaria | 71/71 (100 %) |

## Discordancias de estrato

| Nativa (servicio) | OMOP (unidades) | Pacientes |
|---|---|---|
| medico | quirurgico | 8 |
| quirurgico | cirugia_cardiaca | 4 |
| medico | cirugia_cardiaca | 3 |
| quirurgico | medico | 3 |
