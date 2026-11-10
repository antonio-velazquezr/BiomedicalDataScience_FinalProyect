# Trombocitopenia durante la tromboprofilaxis con heparina

Estudio de farmacovigilancia (Modalidad A del proyecto final del curso de ciencia de datos en salud).
Describe la incidencia y la temporalidad de la trombocitopenia durante la tromboprofilaxis con heparina
en pacientes hospitalizados, con estratificación por cirugía. Ver [docs/propuesta.md](docs/propuesta.md).

> **Estado:** en desarrollo. Hasta ahora: propuesta y exploración inicial.

## Datos

Este repositorio **no contiene datos**. Para reproducir el trabajo:

1. Descarga *MIMIC-IV Clinical Database Demo* **v2.2** desde PhysioNet
   (<https://physionet.org/content/mimic-iv-demo/2.2/>). El acceso es abierto y la licencia es ODbL.
2. Descomprime el archivo en `data/raw/`, de modo que quede `data/raw/mimic-iv-clinical-database-demo-2.2/`.
3. Verifica la integridad con `sha256sum -c SHA256SUMS.txt` dentro de esa carpeta.

## Entorno (provisional)

```bash
python -m venv .venv
.venv/Scripts/python -m pip install polars matplotlib jupyter
```

El entorno definitivo se fijará con `pyproject.toml` y Docker.

## Estructura

```
docs/        propuesta y documentación
notebooks/   exploración (no es lógica de producción)
figuras/     figuras generadas
```

## Uso de asistentes de IA

En la planeación, la exploración de datos y la redacción se usó Claude Code (Anthropic). Todas las
decisiones de diseño y su interpretación son responsabilidad del autor.
