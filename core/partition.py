"""
Reparto de la matriz en bandas de filas (una por trabajador) y filas fantasma de cada banda.
En los extremos de la matriz las filas fantasma son ceros (borde muerto).
"""


def row_ranges(h, p):
    """Reparte h filas entre p trabajadores, con balance de carga."""
    p = max(1, min(p, h))              # nunca más trabajadores que filas
    base = h // p
    extra = h % p                      # las primeras `extra` bandas llevan una fila más
    rangos = []
    inicio = 0
    for i in range(p):
        tam = base + (1 if i < extra else 0)
        rangos.append((inicio, inicio + tam))
        inicio += tam
    return rangos


def with_ghost_rows(grid, r_start, r_end):
    """Construye la banda de un trabajador más una fila vecina arriba y otra abajo."""
    h = len(grid)
    ancho = len(grid[0])
    arriba = grid[r_start - 1] if r_start > 0 else bytearray(ancho)   # antes de la fila 0: ceros
    abajo = grid[r_end] if r_end < h else bytearray(ancho)            # después de la última: ceros
    banda = [bytearray(f) for f in grid[r_start:r_end]]
    return [bytearray(arriba)] + banda + [bytearray(abajo)]


def strip_ghost_rows(band_with_ghosts):
    """Quita las filas fantasma y devuelve solo las filas propias de la banda."""
    return band_with_ghosts[1:-1]
