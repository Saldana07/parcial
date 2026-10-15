"""
V1 secuencial: un solo hilo calcula todas las filas y luego intercambia las matrices actual y siguiente.
Es la base contra la que se miden las demás versiones.
"""

from core import grid, rules
from core.engine_base import Engine


class SequentialEngine(Engine):
    name = "v1"

    def __init__(self, initial_grid, workers=1):
        # workers no se usa: V1 es secuencial
        self.actual = grid.copy(initial_grid)
        self.siguiente = grid.new_grid(len(initial_grid), len(initial_grid[0]))

    def run(self, generations):
        h = len(self.actual)
        for _ in range(generations):
            rules.compute_rows(self.actual, self.siguiente, 0, h)
            self.actual, self.siguiente = self.siguiente, self.actual   # swap de referencias

    def step(self):
        self.run(1)

    def snapshot(self):
        return grid.copy(self.actual)

    def close(self):
        pass        # V1 no tiene hilos ni procesos que liberar
