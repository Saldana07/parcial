"""
V3: pool de procesos persistente. En cada generación cada proceso recibe su banda con filas fantasma,
la calcula y la devuelve; el proceso principal ensambla la matriz nueva.
"""

import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed

from core import grid, partition, rules
from core.engine_base import Engine


def _calentar(_):
    """Tarea de calentamiento: devuelve el PID del proceso que la ejecutó."""
    time.sleep(0.1)       # mientras duerme, el pool crea otro proceso para la siguiente tarea
    return os.getpid()


def _worker_compute_band(band_with_ghosts):
    """Función del trabajador (a nivel de módulo, serializable)."""
    n = len(band_with_ghosts)
    ancho = len(band_with_ghosts[0])
    salida = [None] + [bytearray(ancho) for _ in range(n - 2)] + [None]
    # se calculan solo las filas propias; las fantasma aportan los vecinos
    rules.compute_rows(band_with_ghosts, salida, 1, n - 1)
    return partition.strip_ghost_rows(salida)


class ProcessEngine(Engine):
    name = "v3"

    def __init__(self, initial_grid, workers=1):
        self.actual = grid.copy(initial_grid)
        self.rangos = partition.row_ranges(len(self.actual), workers)
        self.p = len(self.rangos)
        self._cerrado = False
        # Pool persistente: se crea una sola vez
        self.pool = ProcessPoolExecutor(max_workers=self.p)
        # Calentamiento: espera a que los p procesos estén vivos antes de medir
        pids = set()
        for _ in range(50):
            pids.update(self.pool.map(_calentar, range(self.p)))
            if len(pids) >= self.p:
                break

    def run(self, generations):
        if self._cerrado:
            raise RuntimeError("El motor ya fue cerrado")
        for _ in range(generations):
            futuros = {}
            for i, (r_start, r_end) in enumerate(self.rangos):
                banda = partition.with_ghost_rows(self.actual, r_start, r_end)   # copia = comunicación
                futuros[self.pool.submit(_worker_compute_band, banda)] = i
            # as_completed devuelve por orden de llegada: se guarda el índice de cada banda
            resultados = [None] * self.p
            for futuro in as_completed(futuros):
                resultados[futuros[futuro]] = futuro.result()
            # ensamblar en orden; esperar a todos es la sincronización
            nueva = []
            for banda_nueva in resultados:
                nueva.extend(banda_nueva)
            self.actual = nueva

    def step(self):
        self.run(1)

    def snapshot(self):
        return grid.copy(self.actual)

    def close(self):
        if self._cerrado:
            return
        self._cerrado = True
        self.pool.shutdown(wait=True, cancel_futures=True)