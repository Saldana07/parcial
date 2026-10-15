"""
Dibuja el tablero (franjas por trabajador, células que nacen y mueren) y define la paleta de colores.
"""

import numpy as np
import pygame

# --- Paleta de la interfaz
COLOR_BG = (14, 17, 24)
COLOR_PANEL = (22, 26, 36)
COLOR_CARD = (30, 35, 48)
COLOR_EDGE = (46, 53, 70)
COLOR_TEXT = (228, 232, 240)
COLOR_BODY = (196, 203, 218)
COLOR_DIM = (136, 146, 166)
COLOR_ACCENT = (255, 184, 76)
COLOR_ON_BG = (34, 56, 92)
COLOR_ON_EDGE = (86, 148, 255)
COLOR_BTN = (40, 46, 62)
COLOR_BTN_HI = (54, 62, 84)
COLOR_BTN_OFF = (28, 32, 43)
COLOR_OK = (110, 220, 140)
COLOR_WARN = (255, 184, 76)
COLOR_BAD = (240, 100, 100)

# --- Colores de las celdas
COLOR_DEAD = (24, 28, 38)
COLOR_ALIVE = (132, 226, 196)
COLOR_NEWBORN = (255, 236, 130)
COLOR_DIED = (226, 72, 92)
COLOR_LINES = (40, 46, 60)

# Un color por hilo (se repiten si hay más de 8). Evita el rojo para no confundirlo con "muere".
BAND_COLORS = [
    (86, 148, 255),    # azul
    (255, 153, 66),    # naranja
    (168, 120, 255),   # violeta
    (92, 206, 120),    # verde
    (255, 112, 176),   # rosa
    (64, 208, 224),    # turquesa
    (232, 196, 64),    # dorado
    (150, 170, 190),   # gris azulado
]

MIN_CELL_PX_FOR_LINES = 6

_BAND_ALIVE = np.array(BAND_COLORS, dtype=np.uint8)
_BAND_DEAD = (_BAND_ALIVE * 0.16 + 12).astype(np.uint8)      # versión muy oscura del color
_BAND_GHOST = (_BAND_ALIVE * 0.45).astype(np.uint8)          # "acaba de morir" en modo franjas
_C_DEAD = np.array(COLOR_DEAD, dtype=np.uint8)
_C_ALIVE = np.array(COLOR_ALIVE, dtype=np.uint8)
_C_NEWBORN = np.array(COLOR_NEWBORN, dtype=np.uint8)
_C_DIED = np.array(COLOR_DIED, dtype=np.uint8)
_C_WHITE = np.array((255, 255, 255), dtype=np.uint8)


def band_color(i):
    """Color (RGB) del hilo i."""
    return BAND_COLORS[i % len(BAND_COLORS)]


def legend_colors(bands_on):
    """Colores (viva, nace, muere) tal como se ven en el tablero con o sin franjas."""
    if bands_on:
        return None, (255, 255, 255), (120, 130, 150)
    return COLOR_ALIVE, COLOR_NEWBORN, COLOR_DIED


def to_array(grid):
    """Entrada: matriz del core (lista de bytearray). Salida: ndarray uint8 (filas, columnas)."""
    return np.asarray(grid, dtype=np.uint8)


def build_rgb(arr, prev=None, ranges=None, show_changes=False):
    """Convierte la matriz 0/1 en una imagen RGB (filas, columnas, 3)."""
    rows = arr.shape[0]
    alive = arr > 0
    if ranges:
        heights = [e - s for s, e in ranges]
        idx = np.repeat(np.arange(len(ranges)) % len(BAND_COLORS), heights)
        alive_c = _BAND_ALIVE[idx][:, None, :]
        dead_c = _BAND_DEAD[idx][:, None, :]
        ghost_c = _BAND_GHOST[idx][:, None, :]
        born_c = _C_WHITE
    else:
        alive_c, dead_c, ghost_c, born_c = _C_ALIVE, _C_DEAD, _C_DIED, _C_NEWBORN

    rgb = np.where(alive[..., None], alive_c, dead_c)
    if show_changes and prev is not None and prev.shape == arr.shape:
        was = prev > 0
        born = alive & ~was
        died = ~alive & was
        rgb = np.where(born[..., None], born_c, rgb)
        rgb = np.where(died[..., None], ghost_c, rgb)
    return rgb.astype(np.uint8)


def layout(area, rows, cols):
    """Calcula dónde cae el tablero dentro de `area` (pygame.Rect), centrado."""
    cell = min(area.w / cols, area.h / rows)
    if cell >= MIN_CELL_PX_FOR_LINES:      # celdas grandes: tamaño entero para que la cuadrícula cuadre
        cell = int(cell)
        size = (cols * cell, rows * cell)
    else:                                  # matrices grandes: aprovechar todo el espacio (sin cuadrícula)
        size = (max(1, int(cols * cell)), max(1, int(rows * cell)))
    rect = pygame.Rect(0, 0, *size)
    rect.center = area.center
    return rect, cell


def draw_board(screen, arr, area, show_lines=True, prev=None, show_changes=False,
               ranges=None, labels=None, font=None):
    """Dibuja el tablero escalado y centrado en `area`."""
    rows, cols = arr.shape
    rect, cell = layout(area, rows, cols)
    if ranges and ranges[-1][1] != rows:
        ranges = None                      # el reparto no corresponde a esta matriz
    rgb = build_rgb(arr, prev, ranges, show_changes)
    surface = pygame.surfarray.make_surface(rgb.swapaxes(0, 1))
    surface = pygame.transform.scale(surface, rect.size)
    screen.blit(surface, rect.topleft)

    if show_lines and cell >= MIN_CELL_PX_FOR_LINES:
        for c in range(cols + 1):
            x = rect.x + c * cell
            pygame.draw.line(screen, COLOR_LINES, (x, rect.y), (x, rect.bottom))
        for r in range(rows + 1):
            y = rect.y + r * cell
            pygame.draw.line(screen, COLOR_LINES, (rect.x, y), (rect.right, y))

    if ranges:
        _draw_bands(screen, rect, rows, ranges, labels, font)
    pygame.draw.rect(screen, COLOR_EDGE, rect.inflate(2, 2), 1)
    return rect


def _draw_bands(screen, rect, rows, ranges, labels, font):
    """Separadores entre bandas y una etiqueta por banda (si cabe)."""
    px_per_row = rect.h / rows
    for i, (s, e) in enumerate(ranges):
        y0 = rect.y + round(s * px_per_row)
        if i > 0:
            pygame.draw.line(screen, (240, 244, 250), (rect.x, y0), (rect.right - 1, y0), 2)
        if font is not None and labels and (e - s) * px_per_row >= 22:
            text = f"{labels[i]}  ·  filas {s}-{e - 1}"
            surf = font.render(text, True, (255, 255, 255))
            chip = pygame.Surface((surf.get_width() + 12, surf.get_height() + 4), pygame.SRCALPHA)
            chip.fill((10, 12, 18, 190))
            screen.blit(chip, (rect.x + 6, y0 + 4))
            screen.blit(surf, (rect.x + 12, y0 + 6))


def cell_from_pos(pos, rect, rows, cols):
    """Convierte una posición de ratón (px) en (fila, columna). None si está fuera del tablero."""
    if not rect.collidepoint(pos):
        return None
    c = min(cols - 1, int((pos[0] - rect.x) * cols / rect.w))
    r = min(rows - 1, int((pos[1] - rect.y) * rows / rect.h))
    return r, c