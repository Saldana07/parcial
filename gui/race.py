"""
Carrera: las versiones corren a la vez un número fijo de generaciones, cada una en su propio proceso.
Gana la que termina primero; devuelve el tiempo y la matriz final de cada una.
"""

import multiprocessing as mp
import time

# estado de cada participante (valor en un entero compartido)
PREPARANDO, LISTO, CORRIENDO, TERMINO, CANCELADO, FALLO = range(6)


def _participante(version, grid, workers, generaciones, estado, progreso, salida, cancelar, cola):
    """Lo que ejecuta CADA proceso de la carrera (a nivel de módulo: debe poder serializarse)."""
    engine = None
    try:
        from core.registry import load_engine_class
        engine = load_engine_class(version)(grid, 1 if version == 1 else workers)
        estado.value = LISTO
        salida.wait()                                   # todos esperan la salida juntos
        paso = max(1, generaciones // 100)              # ~100 actualizaciones de progreso
        hechas = 0
        t0 = time.perf_counter()
        estado.value = CORRIENDO
        while hechas < generaciones:
            if cancelar.is_set():
                estado.value = CANCELADO
                return
            n = min(paso, generaciones - hechas)
            engine.run(n)
            hechas += n
            progreso.value = hechas
        elapsed = time.perf_counter() - t0              # el reloj se detiene ANTES de copiar la matriz
        final = engine.snapshot()
        estado.value = TERMINO
        cola.put((version, elapsed, b"".join(final), len(final[0])))
    except Exception as exc:                            # noqa: BLE001 - se informa a la GUI
        estado.value = FALLO
        cola.put((version, None, f"{type(exc).__name__}: {exc}", 0))
    finally:
        if engine is not None:
            engine.close()


class Race:
    """Una carrera en marcha. La GUI la crea, llama a poll() cada cuadro y lee el estado."""

    def __init__(self, versions, grid, workers, generations):
        ctx = mp.get_context("spawn")
        self.versions = list(versions)
        self.generations = generations
        self._salida = ctx.Event()
        self._cancelar = ctx.Event()
        self._cola = ctx.Queue()
        self._estado = {v: ctx.Value("i", PREPARANDO) for v in self.versions}
        self._progreso = {v: ctx.Value("i", 0) for v in self.versions}
        self.results = {}           # versión -> (segundos, matriz final)
        self.errors = {}            # versión -> mensaje
        self.t_start = None         # reloj del padre en la salida (solo para el cronómetro en vivo)
        self.cancelled = False
        self._procs = {
            v: ctx.Process(target=_participante,
                           args=(v, grid, workers, generations, self._estado[v], self._progreso[v],
                                 self._salida, self._cancelar, self._cola))
            for v in self.versions}
        for p in self._procs.values():
            p.start()

    # --- cada cuadro
    def poll(self):
        """Recoge llegadas, da la salida cuando todos están listos y detecta procesos caídos."""
        while not self._cola.empty():
            version, elapsed, datos, ancho = self._cola.get()
            if elapsed is None:
                self.errors[version] = datos
            else:
                self.results[version] = (elapsed, [bytearray(datos[i:i + ancho])
                                                   for i in range(0, len(datos), ancho)])
        if self.t_start is None and not self.cancelled:
            if all(self._estado[v].value in (LISTO, FALLO) for v in self.versions) \
                    and any(self._estado[v].value == LISTO for v in self.versions):
                self.t_start = time.perf_counter()
                self._salida.set()                      # ¡salida!
        for v, p in self._procs.items():                # un proceso que muere sin avisar no cuelga la GUI
            if not p.is_alive() and self._estado[v].value in (PREPARANDO, LISTO, CORRIENDO):
                self._estado[v].value = FALLO
                self.errors.setdefault(v, "el proceso terminó inesperadamente")

    # --- estado para dibujar
    @property
    def finished(self):
        """Todos llegaron a la meta (o fallaron). Una carrera cancelada no cuenta como terminada."""
        return all(v in self.results or v in self.errors for v in self.versions)

    @property
    def phase(self):
        if self.cancelled:
            return "cancelada"
        if self.finished:
            return "terminada"
        return "preparando" if self.t_start is None else "corriendo"

    @property
    def ranking(self):
        """Versiones que llegaron, de la más rápida a la más lenta (por su tiempo, no por el orden de la cola)."""
        return sorted(self.results, key=lambda v: self.results[v][0])

    def state(self, version):
        return self._estado[version].value

    def done(self, version):
        """Generaciones completadas por `version` (0..generaciones)."""
        return self.generations if version in self.results else self._progreso[version].value

    def elapsed(self, version):
        """Segundos de `version`: su tiempo final si ya llegó; si no, el cronómetro en vivo."""
        if version in self.results:
            return self.results[version][0]
        if self.t_start is None or version in self.errors:
            return 0.0
        return time.perf_counter() - self.t_start

    # --- cierre
    def cancel(self):
        """Detiene la carrera y limpia los procesos (se puede llamar varias veces)."""
        self.cancelled = self.cancelled or not self.finished
        self._cancelar.set()
        self._salida.set()                              # por si alguno seguía esperando la salida
        for p in self._procs.values():
            p.join(timeout=10)
            if p.is_alive():
                p.terminate()
                p.join(timeout=5)
