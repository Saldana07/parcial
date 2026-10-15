"""
Reglas del Juego de la Vida con borde muerto.
compute_rows calcula un rango de filas leyendo de src y escribiendo en dst (doble búfer);
next_cell_state y count_neighbors son la regla célula a célula, como referencia.
"""

_CERO = b"\x00"


def next_cell_state(current, neighbors):
    """Aplica las 4 reglas a una celda."""
    if current == 1:
        if neighbors < 2:
            return 0          # soledad
        if neighbors > 3:
            return 0          # sobrepoblación
        return 1              # 2 o 3 vecinos: sobrevive
    return 1 if neighbors == 3 else 0     # muerta: nace con exactamente 3


def count_neighbors(src, r, c):
    """Cuenta los vecinos vivos (8 direcciones) de la celda (r, c)."""
    h = len(src)
    w = len(src[0])
    total = 0
    for dr in (-1, 0, 1):
        for dc in (-1, 0, 1):
            if dr == 0 and dc == 0:
                continue                      # la celda no es su propio vecino
            rr = r + dr
            cc = c + dc
            if 0 <= rr < h and 0 <= cc < w:   # fuera de la matriz = muerta (no suma)
                total += src[rr][cc]
    return total


def compute_rows(src, dst, r_start, r_end):
    """Calcula las filas [r_start, r_end) de la siguiente generación."""
    h = len(src)
    ceros = bytes(len(src[0]))                # fila de ceros para los bordes superior/inferior
    for r in range(r_start, r_end):
        arriba = src[r - 1] if r > 0 else ceros
        centro = src[r]
        abajo = src[r + 1] if r + 1 < h else ceros
        # relleno de 1 columna muerta por lado (incluye las esquinas)
        arriba = _CERO + arriba + _CERO
        centro = _CERO + centro + _CERO
        abajo = _CERO + abajo + _CERO
        # suma vertical: vecinos de arriba + centro + abajo, columna a columna
        col = [x + y + z for x, y, z in zip(arriba, centro, abajo)]
        # s = suma de la ventana 3x3 con la celda incluida: vive si s == 3, o si s == 4 y ya estaba viva
        dst[r][:] = bytes([
            1 if (s := c0 + c1 + c2) == 3 or (s == 4 and viva) else 0
            for c0, c1, c2, viva in zip(col, col[1:], col[2:], centro[1:])
        ])
