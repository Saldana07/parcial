"""
V2: hilos persistentes, cada uno con una banda de filas.
En cada generación todos calculan su banda y esperan en una Barrier, cuya acción intercambia las matrices.
"""

import threading

from core import grid, partition, rules
from core.engine_base import Engine

# Segundos máximos de espera en la barrera: si un hilo falla, los demás no se quedan colgados
TIMEOUT_BARRERA = 120


class ThreadedEngine(Engine):
    name = "v2"

    def __init__(self, initial_grid, workers=1):
        self.h = len(initial_grid)
        self.rangos = partition.row_ranges(self.h, workers)   # p efectivo <= filas
        self.p = len(self.rangos)

        self._preparar_estado(initial_grid)       # crea self.actual y self.siguiente

        self._n = 0                 # generaciones que pide el run() en curso
        self._cerrado = False
        self._error = None          # primera excepción ocurrida en un hilo

        # Barreras de inicio y fin: los p hilos + el hilo que llama a run()
        self._inicio = threading.Barrier(self.p + 1)
        self._fin = threading.Barrier(self.p + 1)
        # Barrera por generación: cuando llegan todos, su acción intercambia las matrices
        self._gen = threading.Barrier(self.p, action=self._intercambiar,
                                      timeout=TIMEOUT_BARRERA)

        # Hilos persistentes: se crean una sola vez
        self._hilos = [threading.Thread(target=self._trabajar, args=(i,), daemon=True)
                       for i in range(self.p)]
        for hilo in self._hilos:
            hilo.start()

    # --- ganchos que V4 (HybridEngine) reemplaza
    def _preparar_estado(self, initial_grid):
        self.actual = grid.copy(initial_grid)
        self.siguiente = grid.new_grid(len(initial_grid), len(initial_grid[0]))

    def _calcular(self, r_start, r_end):
        """Lo que hace UN hilo en UNA generación: leer actual, escribir su banda de siguiente."""
        rules.compute_rows(self.actual, self.siguiente, r_start, r_end)

    def _exportar(self):
        return grid.copy(self.actual)

    # --- sincronización
    def _intercambiar(self):
        """Acción de la barrera: la corre UN solo hilo; los demás están esperando."""
        self.actual, self.siguiente = self.siguiente, self.actual

    def _trabajar(self, i):
        r_start, r_end = self.rangos[i]
        while True:
            self._inicio.wait()                   # espera a que run() lo ponga a trabajar
            if self._cerrado:
                return
            try:
                for _ in range(self._n):
                    self._calcular(r_start, r_end)   # lectura de actual, escritura en MIS filas
                    self._gen.wait()                 # todos escribieron => se hace el swap
            except threading.BrokenBarrierError:
                pass                                 # otro hilo falló; el error real ya se guardó
            except Exception as exc:                 # noqa: BLE001 - se re-lanza en run()
                if self._error is None:
                    self._error = exc
                self._gen.abort()                    # libera a los demás en vez de dejarlos colgados
            self._fin.wait()                         # avisa al llamador de que terminó

    # --- contrato de Engine
    def run(self, generations):
        if self._cerrado:
            raise RuntimeError("El motor ya fue cerrado")
        if generations <= 0:
            return
        self._n = generations
        self._inicio.wait()      # libera a los hilos
        self._fin.wait()         # espera a que todos terminen las n generaciones
        if self._error is not None:
            raise RuntimeError(f"Un hilo falló: {self._error!r}") from self._error

    def step(self):
        self.run(1)

    def snapshot(self):
        return self._exportar()

    def close(self):
        if self._cerrado:
            return
        self._cerrado = True
        try:
            self._inicio.wait(timeout=5)          # despierta a los hilos para que salgan
        except threading.BrokenBarrierError:
            pass
        for hilo in self._hilos:
            hilo.join(timeout=5)
