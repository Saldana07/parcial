"""
Constantes compartidas por las versiones, la GUI y las mediciones: frontera, semilla, tamaños y trabajadores.
"""

# --- Juego: fuera de la matriz todo cuenta como célula muerta (borde muerto)
FRONTERA = "muerta"

SEMILLA = 12345          # Semilla con la que arranca la GUI (se puede cambiar escribiéndola en la interfaz)
DENSIDAD = 0.30          # Fracción aproximada de celdas vivas al generar un tablero aleatorio

# --- Paralelismo: versión con la que arranca la GUI ("hilos" = V2, "procesos" = V3)
MODO_PARALELO = "hilos"
TRABAJADORES = [1, 2, 4, 8, 16]   # Hilos (V2, V4) o procesos (V3). Equipo: 8 núcleos físicos / 16 lógicos

# --- GUI
GUI_TAMANOS = [5, 100, 500, 1000]       # tamaños de la matriz que ofrece la interfaz
GUI_TAMANO = 100                        # tamaño con el que arranca (debe estar en GUI_TAMANOS)
GUI_VERSIONES = [1, 2, 3, 4]            # 1 = secuencial, 2 = hilos, 3 = procesos, 4 = hilos + NumPy
GUI_TRABAJADORES = 4                    # trabajadores con los que arranca (debe estar en TRABAJADORES)
GUI_CARRERA_GENERACIONES = [50, 100, 200, 500]   # opciones de "Generaciones" de la Carrera
GUI_CARRERA_DEFAULT = 200                        # con cuántas arranca (debe estar en la lista)

# --- Análisis de rendimiento (cada versión se mide sola; tarda unos minutos)
ANALISIS_TAMANOS = [100, 500, 1000]     # los del enunciado
ANALISIS_TRABAJADORES = [1, 2, 4, 8]    # hilos (V2, V4) o procesos (V3)
ANALISIS_GENERACIONES = 20              # generaciones cronometradas por medición
ANALISIS_REPETICIONES = 3               # se reporta la MEDIANA de las repeticiones
