# Juego de la Vida — secuencial vs. paralelo

## Estructura

```
config.py               constantes: semilla, densidad, tamaños, trabajadores
core/
  rules.py              reglas del juego y cálculo de un rango de filas
  grid.py               la matriz (lista de bytearray) y sus utilidades
  partition.py          reparto en bandas de filas y filas fantasma
  engine_base.py        contrato común: run, step, snapshot, close
  registry.py           lista de versiones y carga bajo demanda
  v1_sequential.py      V1 secuencial
  v2_threads.py         V2 hilos
  v3_processes.py       V3 procesos
  v4_hybrid.py          V4 hilos + NumPy
gui/
  app.py                ventana, modos y bucle principal
  controls.py           botones, teclado y panel lateral
  renderer.py           dibujo del tablero y colores
  race.py               la carrera (un proceso por versión)
graficas.py             análisis de rendimiento y su gráfica
benchmark_carrera.py    carreras repetidas, CSV y Excel
```

## Cómo ejecutarlo

Desde esta carpeta, en PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Interfaz gráfica:

```powershell
python -m gui.app
```

Análisis de rendimiento (guarda PNG y CSV en `graficas/`):

```powershell
python -m graficas
```

Carreras repetidas para el informe (guarda CSV y Excel en `resultados/`; el Excel necesita `pip install openpyxl`):

```powershell
python benchmark_carrera.py
```
