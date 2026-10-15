"""
La matriz del juego: lista de bytearray, una por fila, con celdas 0/1.
Crear, llenar al azar con una semilla, copiar y comparar matrices.
"""

import random


def new_grid(h, w):
    """Crea una matriz h x w con todas las celdas muertas."""
    return [bytearray(w) for _ in range(h)]


def randomize(grid, seed, density):
    """Llena la matriz con celdas vivas al azar, de forma reproducible."""
    rng = random.Random(seed)          # generador propio: no toca el global
    for fila in grid:
        for c in range(len(fila)):
            fila[c] = 1 if rng.random() < density else 0
    return grid


def copy(grid):
    """Copia profunda de la matriz (cada versión y cada tablero parten de su propia copia)."""
    return [bytearray(fila) for fila in grid]


def equals(a, b):
    """True si ambas matrices son idénticas celda a celda (comparación directa)."""
    if len(a) != len(b):
        return False
    for fila_a, fila_b in zip(a, b):
        if fila_a != fila_b:       # bytearray == bytearray compara el contenido
            return False
    return True
