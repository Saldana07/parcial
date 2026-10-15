"""
V4: misma estructura que V2 (hilos, bandas y Barrier), pero cada banda se calcula con NumPy
sumando ocho vistas desplazadas de la matriz.
"""

import numpy as np

from core.v2_threads import ThreadedEngine


class HybridEngine(ThreadedEngine):
    """Mismos hilos persistentes, bandas y Barrier que V2; solo cambia el KERNEL."""
    name = "v4"

    def _preparar_estado(self, initial_grid):
        self.actual = np.array(initial_grid, dtype=np.uint8)      # np.array COPIA
        self.siguiente = np.zeros_like(self.actual)

    def _calcular(self, r_start, r_end):
        # banda con una fila y una columna extra por lado; fuera de la matriz quedan ceros
        h, w = self.actual.shape
        ext = np.zeros((r_end - r_start + 2, w + 2), dtype=np.uint8)
        lo = max(r_start - 1, 0)                  # primera fila real que existe
        hi = min(r_end + 1, h)                    # una pasada de la última fila real
        ext[lo - (r_start - 1):hi - (r_start - 1), 1:w + 1] = self.actual[lo:hi]
        # 8 vistas desplazadas sumadas = vecinos vivos de cada celda de la banda
        vecinos = (ext[:-2, :-2] + ext[:-2, 1:-1] + ext[:-2, 2:] +
                   ext[1:-1, :-2] +                  ext[1:-1, 2:] +
                   ext[2:, :-2] + ext[2:, 1:-1] + ext[2:, 2:])
        viva = ext[1:-1, 1:-1]
        # nace con 3 vecinos o sobrevive con 2 o 3; cada hilo escribe solo su banda
        self.siguiente[r_start:r_end] = (vecinos == 3) | ((vecinos == 2) & (viva == 1))

    def _exportar(self):
        return [bytearray(fila.tobytes()) for fila in self.actual]