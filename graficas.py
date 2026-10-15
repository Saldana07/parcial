"""
Análisis de rendimiento: mide cada versión sola, una tras otra, por tamaño y nº de hilos/procesos,
y guarda la gráfica (PNG) y los datos (CSV) en graficas/. Uso: botón de la GUI o python -m graficas.
"""

import argparse
import csv
import multiprocessing as mp
import os
import queue
import statistics
import time

import config

CARPETA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "graficas")

NOMBRES = {1: "V1 Secuencial", 2: "V2 Hilos", 3: "V3 Procesos", 4: "V4 Hilos+NumPy"}
# mismos colores que la GUI (gui/controls.py), en hexadecimal para matplotlib
COLORES = {1: "#96aabe", 2: "#5694ff", 3: "#ff9942", 4: "#5cce78"}


# --- 1. medir
def medir(tamanos, trabajadores, generaciones, repeticiones, semilla, progreso=None, cancelar=None):
    """Mide cada versión SOLA, una tras otra. Devuelve la lista de filas, o None si se canceló."""
    from core import grid as grid_mod
    from core.registry import load_engine_class

    planes = [(t, v, p) for t in tamanos for v in config.GUI_VERSIONES
              for p in ([1] if v == 1 else trabajadores)]
    filas = []
    final_v1 = {}
    for i, (t, v, p) in enumerate(planes):
        if cancelar is not None and cancelar.is_set():
            return None
        if progreso:
            unidad = "proceso" if v == 3 else "hilo"
            progreso(i, len(planes), f"V{v} · matriz {t}x{t} · {p} {unidad}{'s' if p > 1 else ''}")
        inicial = grid_mod.new_grid(t, t)
        grid_mod.randomize(inicial, semilla, config.DENSIDAD)     # la MISMA matriz para todas
        t0 = time.perf_counter()
        motor = load_engine_class(v)(inicial, p)
        arranque = time.perf_counter() - t0
        try:
            motor.run(1)                                          # calentamiento (no se cronometra)
            tiempos = []
            for _ in range(repeticiones):
                t0 = time.perf_counter()
                motor.run(generaciones)                           # LO ÚNICO que se cronometra
                tiempos.append(time.perf_counter() - t0)
            final = motor.snapshot()
        finally:
            motor.close()
        if v == 1:
            final_v1[t] = final
        segundos = statistics.median(tiempos)
        filas.append({"version": v, "tamano": t, "trabajadores": p, "generaciones": generaciones,
                      "repeticiones": repeticiones, "segundos": segundos,
                      "ms_gen": segundos * 1000 / generaciones, "arranque_s": arranque,
                      "correcto": v == 1 or grid_mod.equals(final_v1[t], final)})
    if progreso:
        progreso(len(planes), len(planes), "Dibujando la gráfica")
    return filas


# --- 2. graficar
def graficar(filas, p_ref, semilla, carpeta=None):
    """Dibuja los tres paneles y guarda PNG + CSV. Devuelve la ruta del PNG."""
    import matplotlib
    matplotlib.use("Agg")                                         # sin ventanas: solo el archivo
    import matplotlib.pyplot as plt
    from matplotlib.ticker import LogFormatter, NullLocator, ScalarFormatter

    class _LogPlano(LogFormatter):
        def _num_to_string(self, x, vmin, vmax):                  # 0.6 en vez de 6e-01
            return f"{x:g}"

    carpeta = carpeta or CARPETA
    ms = {(f["version"], f["tamano"], f["trabajadores"]): f["ms_gen"] for f in filas}
    tamanos = sorted({f["tamano"] for f in filas})
    trabajadores = sorted({f["trabajadores"] for f in filas if f["version"] != 1})
    if p_ref not in trabajadores:                                 # el más cercano a lo elegido en la GUI
        p_ref = min(trabajadores, key=lambda p: abs(p - p_ref))
    t_max = tamanos[-1]
    paralelas = [v for v in (2, 3, 4) if v in {f["version"] for f in filas}]

    def ejes(ax, xs, base, xlabel, ylabel, titulo):
        ax.set_xscale("log", base=base)
        ax.set_xticks(xs)
        ax.xaxis.set_major_formatter(ScalarFormatter())
        ax.xaxis.set_minor_locator(NullLocator())
        ax.set_yscale("log")
        ax.yaxis.set_major_formatter(_LogPlano(minor_thresholds=(2, 0.4)))
        ax.yaxis.set_minor_formatter(_LogPlano(minor_thresholds=(2, 0.4)))
        ax.set_xlabel(xlabel)
        ax.set_ylabel(ylabel)
        ax.set_title(titulo, fontsize=11)
        ax.grid(True, which="both", alpha=0.3)
        ax.legend(fontsize=8, loc="best")

    fig, (a1, a2, a3) = plt.subplots(1, 3, figsize=(17, 5.3))

    # --- 1. tiempo vs tamaño de la matriz
    a1.plot(tamanos, [ms[(1, t, 1)] for t in tamanos], "--", marker="s", color="black", label=NOMBRES[1])
    for v in paralelas:
        a1.plot(tamanos, [ms[(v, t, p_ref)] for t in tamanos], marker="o", color=COLORES[v],
                label=f"{NOMBRES[v]} ({p_ref})")
    ejes(a1, tamanos, 10, "Tamaño de la matriz (lado)", "Tiempo por generación (ms)",
         f"Tiempo vs. tamaño de la matriz\n(V2–V4 con {p_ref} hilos/procesos)")

    # --- 2. tiempo vs número de hilos/procesos
    a2.axhline(ms[(1, t_max, 1)], color="black", linestyle="--", label=NOMBRES[1])
    for v in paralelas:
        a2.plot(trabajadores, [ms[(v, t_max, p)] for p in trabajadores], marker="o", color=COLORES[v],
                label=NOMBRES[v])
    ejes(a2, trabajadores, 2, "Hilos / procesos", "Tiempo por generación (ms)",
         f"Tiempo vs. número de hilos/procesos\n(matriz {t_max}×{t_max})")

    # --- 3. speedup contra V1
    a3.plot(trabajadores, trabajadores, "k:", label="ideal S = p")
    a3.axhline(1.0, color="#999999", linewidth=0.8)
    for v in paralelas:
        a3.plot(trabajadores, [ms[(1, t_max, 1)] / ms[(v, t_max, p)] for p in trabajadores],
                marker="o", color=COLORES[v], label=NOMBRES[v])
    ejes(a3, trabajadores, 2, "Hilos / procesos", "Speedup = T(V1) / T(versión)",
         f"Speedup contra V1\n(matriz {t_max}×{t_max}; V4 incluye la ganancia de NumPy)")

    gen, rep = filas[0]["generaciones"], filas[0]["repeticiones"]
    fig.suptitle(f"Análisis de rendimiento · {gen} generaciones × {rep} repeticiones (mediana) · semilla {semilla}",
                 fontsize=13, y=0.99)
    malos = sorted({f"V{f['version']} {f['tamano']}x{f['tamano']} p={f['trabajadores']}" for f in filas if not f["correcto"]})
    veredicto = ("Correctitud: todas las versiones dieron la misma matriz final que V1." if not malos
                 else "OJO, difieren de V1: " + ", ".join(malos))
    fig.text(0.5, 0.01, "Cada versión se ejecutó SOLA, una tras otra (no compiten entre sí). Tiempo por generación = "
             "tiempo cronometrado / generaciones; el arranque de hilos/procesos no se cuenta. " + veredicto,
             ha="center", fontsize=8.5, color="#444444")
    fig.tight_layout(rect=(0, 0.04, 1, 0.95))

    os.makedirs(carpeta, exist_ok=True)
    base = os.path.join(carpeta, f"analisis_rendimiento_{time.strftime('%Y%m%d_%H%M%S')}")
    fig.savefig(base + ".png", dpi=130)
    plt.close(fig)
    with open(base + ".csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)
    return base + ".png"


def analizar(tamanos, trabajadores, generaciones, repeticiones, semilla, p_ref,
             carpeta=None, progreso=None, cancelar=None):
    """medir + graficar. Devuelve la ruta del PNG, o None si se canceló."""
    filas = medir(tamanos, trabajadores, generaciones, repeticiones, semilla, progreso, cancelar)
    if filas is None:
        return None
    return graficar(filas, p_ref, semilla, carpeta)


# --- 3. en segundo plano (para la GUI)
def _proceso(params, cola, cancelar):
    """Lo que corre el proceso hijo: el análisis completo, avisando el progreso por la cola."""
    try:
        ruta = analizar(**params, progreso=lambda i, n, txt: cola.put(("progreso", i, n, txt)), cancelar=cancelar)
        cola.put(("cancelado",) if ruta is None else ("fin", ruta))
    except Exception as exc:                                      # noqa: BLE001 - se informa a la GUI
        cola.put(("error", f"{type(exc).__name__}: {exc}"))


class Analisis:
    """Un análisis corriendo en un proceso aparte. La GUI llama a poll() cada cuadro."""

    def __init__(self, **params):
        ctx = mp.get_context("spawn")
        self._cola = ctx.Queue()
        self._cancelar = ctx.Event()
        self._proc = ctx.Process(target=_proceso, args=(params, self._cola, self._cancelar))
        self._proc.start()
        self.hechas, self.total, self.texto = 0, 0, "Preparando…"
        self.ruta = None            # PNG resultante
        self.error = None
        self.terminado = False

    def _leer(self, msg):
        if msg[0] == "progreso":
            _, self.hechas, self.total, self.texto = msg
        elif msg[0] == "fin":
            self.ruta, self.terminado = msg[1], True
        elif msg[0] == "error":
            self.error, self.terminado = msg[1], True
        elif msg[0] == "cancelado":
            self.terminado = True

    def poll(self):
        """Lee los avisos del proceso. Si el proceso murió sin avisar, lo marca como error."""
        try:
            while True:
                self._leer(self._cola.get_nowait())
        except queue.Empty:
            pass
        if not self.terminado and not self._proc.is_alive():
            try:                                                  # último aviso que pudo quedar en tránsito
                self._leer(self._cola.get(timeout=1))
            except queue.Empty:
                pass
            if not self.terminado:
                self.error, self.terminado = "el proceso del análisis terminó inesperadamente", True

    def cancel(self):
        """Pide parar (se detiene al terminar la medición en curso) y recoge el proceso."""
        self._cancelar.set()
        self._proc.join(timeout=60)
        if self._proc.is_alive():
            self._proc.terminate()
            self._proc.join(timeout=5)


def parametros(semilla, p_ref):
    """Parámetros del análisis desde config.py (la semilla y el nº de hilos de referencia vienen de la GUI)."""
    return {"tamanos": config.ANALISIS_TAMANOS, "trabajadores": config.ANALISIS_TRABAJADORES,
            "generaciones": config.ANALISIS_GENERACIONES, "repeticiones": config.ANALISIS_REPETICIONES,
            "semilla": semilla, "p_ref": p_ref}


# --- 4. terminal
def main():
    def lista(s):
        return [int(x) for x in s.split(",")]

    ap = argparse.ArgumentParser(description="Análisis de rendimiento: mide cada versión sola y guarda la gráfica")
    ap.add_argument("--tamanos", type=lista, default=config.ANALISIS_TAMANOS, help="p. ej. 100,500,1000")
    ap.add_argument("--trabajadores", type=lista, default=config.ANALISIS_TRABAJADORES, help="p. ej. 1,2,4,8")
    ap.add_argument("--generaciones", type=int, default=config.ANALISIS_GENERACIONES)
    ap.add_argument("--repeticiones", type=int, default=config.ANALISIS_REPETICIONES)
    ap.add_argument("--semilla", type=int, default=config.SEMILLA)
    ap.add_argument("--p", type=int, default=config.GUI_TRABAJADORES, help="hilos/procesos del panel 'vs. tamaño'")
    ap.add_argument("--salida", default=None, help="carpeta del PNG y el CSV (por defecto graficas/)")
    a = ap.parse_args()
    t0 = time.time()

    def progreso(i, n, texto):
        print(f"[{time.time() - t0:6.1f}s] {i}/{n}  {texto}", flush=True)

    ruta = analizar(a.tamanos, a.trabajadores, a.generaciones, a.repeticiones, a.semilla, a.p,
                    a.salida, progreso)
    print("Gráfica:", ruta)
    print("Datos:  ", ruta[:-4] + ".csv")


if __name__ == "__main__":
    main()
