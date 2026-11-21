# Figuras principales

Generadas con `python -m antitromboticos.figuras` (PDF vectorial). Fuente: MIMIC-IV Clinical Database Demo v2.2 (PhysioNet); la figura 06 usa además su versión OMOP v0.9. Estudio observacional descriptivo; todos los intervalos son IC 95 %.

| Figura | Qué muestra |
|---|---|
| [01_atricion.pdf](01_atricion.pdf) | Criterios de inclusión aplicados en orden; un paciente entra con su primera hospitalización elegible. Criterios sin exclusiones: menores de 18 años, antiagregante sin solapamiento. |
| [02_balance_basal.pdf](02_balance_basal.pdf) | 11 de 12 características superan una diferencia estandarizada de 0.1; las mayores: cardiopatía isquémica, edad, en UCI en la fecha índice. |
| [03_sangrado_principal.pdf](03_sangrado_principal.pdf) | Sangrado relevante (caída de Hb ≥ 2 g/dL o transfusión) en los 14 días siguientes · RR ajustado por intensidad 0.91 (IC 95 % 0.59–1.40). |
| [04_forest_desenlaces.pdf](04_forest_desenlaces.pdf) | Razón de riesgos, anticoagulante + antiagregante vs. solo anticoagulante (ajustada por intensidad). * Sin ajuste: un estrato sin eventos impide la estimación de Mantel-Haenszel. |
| [05_trayectorias.pdf](05_trayectorias.pdf) | Cambio respecto al valor basal en los días siguientes a la fecha índice: mediana (línea) y rango intercuartílico (banda). Se muestran los días con al menos 10 pacientes medidos por grupo; cada paciente aporta su valor más bajo del día. |
| [06_replica_omop.pdf](06_replica_omop.pdf) | Razón de riesgos de sangrado relevante con la misma definición de cohorte en dos modelos de datos. Fuente: MIMIC-IV Clinical Database Demo v2.2 (PhysioNet) y su versión OMOP v0.9. Estudio observacional descriptivo; IC 95 %.  En OMOP no hay transfusiones: el sangrado es solo la caída de Hb ≥ 2 g/dL. |
