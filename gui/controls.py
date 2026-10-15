"""
Estado de la interfaz, botones, teclado y panel lateral. Traduce eventos en acciones para app.py.
"""

from collections import namedtuple
from dataclasses import dataclass, field

import pygame

import config
from gui import renderer as R

SIDEBAR_W = 380
STATUS_H = 24
SEED_MAX_DIGITS = 9

# Gen/s objetivo. 0 = sin límite (lo más rápido que permita el motor).
SPEEDS = [1, 2, 5, 10, 20, 30, 60, 0]

# Etiqueta corta para botones y filas de la carrera (con 4 versiones el espacio es justo).
VERSION_LABEL = {1: "V1 Secuencial", 2: "V2 Hilos", 3: "V3 Procesos", 4: "V4 NumPy"}
# Color de cada versión en las barras de la carrera.
VERSION_COLORS = {1: (150, 170, 190), 2: R.band_color(0), 3: R.band_color(1), 4: R.band_color(3)}
_TOGGLES = {"show_bands", "show_changes", "show_lines"}

Fonts = namedtuple("Fonts", "title head body small big")


def make_fonts():
    names = "segoeui,helveticaneue,dejavusans,arial"
    f = pygame.font.SysFont
    return Fonts(f(names, 22, bold=True), f(names, 17, bold=True), f(names, 15),
                 f(names, 13), f(names, 26, bold=True))


@dataclass
class Button:
    rect: pygame.Rect
    label: str
    action: tuple
    kind: str = "normal"      # "primary" | "normal"
    active: bool = False
    enabled: bool = True


@dataclass
class UIState:
    """Estado mutable de la interfaz."""
    running: bool = False
    version: int = 1
    workers_idx: int = 0
    speed_idx: int = 3
    size_idx: int = 0
    show_lines: bool = True
    show_bands: bool = True
    show_changes: bool = True
    compare: bool = False        # CARRERA: True => corren TODAS las versiones de config.GUI_VERSIONES a la vez
    generation: int = 0
    alive: int = 0
    cells: int = 0
    ms: dict = field(default_factory=dict)       # versión -> ms/generación (promedio exponencial)
    match: dict = field(default_factory=dict)    # versión -> True/False: ¿misma matriz que V1?
    seed: int = config.SEMILLA                   # semilla del tablero actual
    seed_text: str = str(config.SEMILLA)         # lo que hay escrito en el cuadro de la semilla
    seed_focus: bool = False                     # True mientras se escribe en el cuadro
    seed_rect: pygame.Rect = None                # dónde está el cuadro (lo fija el dibujo en cada cuadro)
    status: str = ""
    painting: int = None         # None = no pinta; 1 = pintando vivas; 0 = borrando
    buttons: list = field(default_factory=list)
    race_idx: int = config.GUI_CARRERA_GENERACIONES.index(config.GUI_CARRERA_DEFAULT)
    race_view: dict = None       # estado de la carrera para dibujar (lo escribe app.py en cada cuadro)
    analysis_running: bool = False   # True mientras corre el análisis de rendimiento (en otro proceso)

    @property
    def workers(self):
        return config.TRABAJADORES[self.workers_idx]

    @property
    def fps(self):
        return SPEEDS[self.speed_idx]

    @property
    def size(self):
        return config.GUI_TAMANOS[self.size_idx]

    @property
    def compare_active(self):
        return self.compare

    @property
    def race_n(self):
        """Generaciones que corre cada versión en la carrera."""
        return config.GUI_CARRERA_GENERACIONES[self.race_idx]

    @property
    def ms_main(self):
        """ms/generación de la versión que se está viendo en el tablero."""
        return self.ms.get(self.version, 0.0)

    @property
    def worker_word(self):
        """'hilo' o 'proceso', según la versión que se ve (V3 usa procesos)."""
        return "proceso" if self.version == 3 else "hilo"

    def speedup(self, version):
        """Speedup de `version` contra V1 (solo en la carrera, con ambos tiempos ya medidos)."""
        base, ms = self.ms.get(1, 0.0), self.ms.get(version, 0.0)
        if self.compare_active and base > 0 and ms > 0:
            return base / ms
        return None


# --- eventos
def _do(state, name, data):
    """Aplica una acción de la UI. Devuelve una acción para app.py o None si ya se resolvió."""
    if name == "toggle_run":
        state.running = not state.running
        state.status = ""
        return None
    if name == "step":
        state.running = False
        return ("step", None)
    if name == "speed":
        state.speed_idx = max(0, min(len(SPEEDS) - 1, state.speed_idx + data))
        return None
    if name == "toggle" and data in _TOGGLES:
        setattr(state, data, not getattr(state, data))
        return None
    return (name, data)     # el resto lo ejecuta app.py


def handle_event(event, state, cell_at):
    """Procesa un evento de pygame y devuelve una acción (nombre, datos) o None."""
    if event.type == pygame.QUIT:
        return ("quit", None)

    if event.type == pygame.KEYDOWN:
        k = event.key
        if state.seed_focus:                          # escribiendo la semilla: el teclado es del cuadro
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                state.seed_focus = False
                return ("generate", None)
            if k == pygame.K_ESCAPE:
                state.seed_focus = False
            elif k == pygame.K_BACKSPACE:
                state.seed_text = state.seed_text[:-1]
            elif event.unicode and event.unicode in "0123456789" and len(state.seed_text) < SEED_MAX_DIGITS:
                state.seed_text += event.unicode
            return None
        if k in (pygame.K_ESCAPE, pygame.K_q):
            return ("quit", None)
        simples = {
            pygame.K_SPACE: ("toggle_run", None), pygame.K_n: ("step", None),
            pygame.K_r: ("generate", None), pygame.K_s: ("random_seed", None),
            pygame.K_c: ("clear", None), pygame.K_UP: ("workers", +1),
            pygame.K_DOWN: ("workers", -1), pygame.K_RIGHT: ("speed", +1),
            pygame.K_LEFT: ("speed", -1), pygame.K_g: ("toggle", "show_lines"),
            pygame.K_f: ("toggle", "show_bands"), pygame.K_d: ("toggle", "show_changes"),
            pygame.K_m: ("compare", None), pygame.K_a: ("analysis", None), pygame.K_RIGHTBRACKET: ("size", +1),
            pygame.K_LEFTBRACKET: ("size", -1),
        }
        if k in simples:
            return _do(state, *simples[k])
        if pygame.K_1 <= k <= pygame.K_9 and (k - pygame.K_0) in config.GUI_VERSIONES:
            return ("version", k - pygame.K_0)

    elif event.type == pygame.MOUSEBUTTONDOWN and event.button in (1, 3):
        if event.button == 1:
            state.seed_focus = bool(state.seed_rect and state.seed_rect.collidepoint(event.pos))
            if state.seed_focus:
                return None
            for b in state.buttons:
                if b.enabled and b.rect.collidepoint(event.pos):
                    return _do(state, *b.action)
        cell = cell_at(event.pos)
        if cell is not None:
            state.painting = 1 if event.button == 1 else 0
            return ("paint", (*cell, state.painting))

    elif event.type == pygame.MOUSEBUTTONUP and event.button in (1, 3):
        state.painting = None

    elif event.type == pygame.MOUSEMOTION and state.painting is not None:
        cell = cell_at(event.pos)
        if cell is not None:
            return ("paint", (*cell, state.painting))

    return None


# --- dibujo básico
def _text(screen, font, text, x, y, color, right=False):
    surf = font.render(text, True, color)
    screen.blit(surf, (x - surf.get_width() if right else x, y))
    return surf.get_width()


def _draw_button(screen, font, b):
    hover = b.enabled and b.rect.collidepoint(pygame.mouse.get_pos())
    if not b.enabled:
        bg, fg, edge = R.COLOR_BTN_OFF, (88, 96, 114), None
    elif b.kind == "primary":
        bg = (255, 205, 120) if hover else R.COLOR_ACCENT
        fg, edge = (30, 22, 8), None
    elif b.active:
        bg, fg, edge = R.COLOR_ON_BG, R.COLOR_TEXT, R.COLOR_ON_EDGE
    else:
        bg = R.COLOR_BTN_HI if hover else R.COLOR_BTN
        fg, edge = R.COLOR_TEXT, None
    pygame.draw.rect(screen, bg, b.rect, border_radius=7)
    if edge:
        pygame.draw.rect(screen, edge, b.rect, 1, border_radius=7)
    surf = font.render(b.label, True, fg)
    screen.blit(surf, surf.get_rect(center=b.rect.center))


def _row(screen, state, font, x, y, width, height, specs, gap=8):
    """Fila de botones. specs: (etiqueta, acción, kind, active, enabled, peso)."""
    total = sum(s[5] for s in specs)
    avail = width - gap * (len(specs) - 1)
    cx = x
    for i, (label, action, kind, active, enabled, weight) in enumerate(specs):
        w = round(avail * weight / total) if i < len(specs) - 1 else x + width - cx
        b = Button(pygame.Rect(cx, y, w, height), label, action, kind, active, enabled)
        state.buttons.append(b)
        _draw_button(screen, font, b)
        cx += w + gap


def _spec(label, action, kind="normal", active=False, enabled=True, weight=1):
    return (label, action, kind, active, enabled, weight)


def _stepper(screen, state, fonts, x, y, width, label, value, minus, plus, enabled=True):
    """Fila 'etiqueta  [-]  valor  [+]'."""
    _text(screen, fonts.body, label, x, y + 4, R.COLOR_BODY if enabled else R.COLOR_DIM)
    bm = Button(pygame.Rect(x + 96, y, 32, 28), "-", minus, enabled=enabled)
    bp = Button(pygame.Rect(x + width - 32, y, 32, 28), "+", plus, enabled=enabled)
    for b in (bm, bp):
        state.buttons.append(b)
        _draw_button(screen, fonts.head, b)
    surf = fonts.body.render(value, True, R.COLOR_TEXT if enabled else R.COLOR_DIM)
    mid = (bm.rect.right + bp.rect.left) // 2
    screen.blit(surf, surf.get_rect(center=(mid, y + 14)))


def _seed_box(screen, state, fonts, rect):
    """Cuadro de texto de la semilla (solo números). Guarda su rect para que el ratón lo encuentre."""
    state.seed_rect = rect
    pygame.draw.rect(screen, R.COLOR_BTN_OFF, rect, border_radius=7)
    pygame.draw.rect(screen, R.COLOR_ON_EDGE if state.seed_focus else R.COLOR_EDGE, rect, 1, border_radius=7)
    if state.seed_text or state.seed_focus:
        caret = "|" if state.seed_focus and (pygame.time.get_ticks() // 500) % 2 == 0 else ""
        surf = fonts.body.render(state.seed_text + caret, True, R.COLOR_TEXT)
    else:
        surf = fonts.body.render("escribe una semilla", True, R.COLOR_DIM)
    screen.blit(surf, surf.get_rect(midleft=(rect.x + 10, rect.centery)))


# --- paneles
def draw_legend(screen, rect, state, fonts):
    """Barra sobre el tablero: leyenda de colores."""
    alive_c, born_c, died_c = R.legend_colors(state.show_bands)
    x, y = rect.x, rect.y + 6
    items = []
    if state.show_bands:
        items.append((None, f"Color = {state.worker_word} que calcula esa fila"))
    else:
        items.append((alive_c, "Viva"))
    if state.show_changes:
        items += [(born_c, "Nace"), (died_c, "Muere")]
    for color, label in items:
        if color is not None:
            pygame.draw.rect(screen, color, (x, y + 2, 14, 14), border_radius=3)
            x += 20
        x += _text(screen, fonts.body, label, x, y, R.COLOR_BODY) + 22


def draw_status(screen, rect, state, fonts):
    """Una línea bajo el tablero: avisos y resultados (quién ganó la carrera, errores...)."""
    if state.status:
        _text(screen, fonts.body, state.status, rect.x, rect.y + 2, R.COLOR_WARN)
    else:
        _text(screen, fonts.small, "Clic izq.: pintar · Clic der.: borrar", rect.x, rect.y + 5, R.COLOR_DIM)


def _race_card(screen, state, fonts, card, versions):
    """Tarjeta de la CARRERA: un carril por versión con su progreso, su tiempo, su speedup y su puesto."""
    view = state.race_view
    cx, cy = card.x + 12, card.y + 10
    n = state.race_n
    _text(screen, fonts.body, f"Carrera: {n} generaciones", cx, cy, R.COLOR_TEXT)
    fase = {"preparando": "Preparando…", "corriendo": "¡En marcha!", "terminada": "Terminada",
            "cancelada": "Cancelada"}.get(view["phase"] if view else "", "Pulsa Iniciar")
    _text(screen, fonts.small, fase, card.right - 12, cy + 3, R.COLOR_ACCENT, right=True)
    cy += 28
    lanes = {lane["v"]: lane for lane in view["lanes"]} if view else {}
    bar_x, bar_w = cx + 92, 92
    for v in versions:
        lane = lanes.get(v)
        _text(screen, fonts.small, VERSION_LABEL[v], cx, cy + 2, R.COLOR_BODY)
        pygame.draw.rect(screen, R.COLOR_EDGE, (bar_x, cy + 3, bar_w, 12), border_radius=3)    # la pista
        if lane:
            done = lane["done"]
            if done:
                pygame.draw.rect(screen, VERSION_COLORS[v], (bar_x, cy + 3, max(3, int(bar_w * done / n)), 12),
                                 border_radius=3)
            if lane["error"]:
                _text(screen, fonts.small, "falló", card.right - 12, cy + 2, R.COLOR_BAD, right=True)
            else:
                secs = f"{lane['elapsed']:.2f} s" if lane["elapsed"] else "—"
                _text(screen, fonts.small, secs, card.right - 92, cy + 2, R.COLOR_TEXT, right=True)
                s = 1.0 if v == 1 and lane["rank"] else state.speedup(v)
                if s is not None:
                    color = R.COLOR_DIM if v == 1 else (R.COLOR_OK if s > 1.05 else (R.COLOR_WARN if s >= 0.95 else R.COLOR_BAD))
                    _text(screen, fonts.small, f"{s:.2f}×", card.right - 42, cy + 2, color, right=True)
                if lane["rank"]:
                    _text(screen, fonts.small, f"{lane['rank']}º", card.right - 12, cy + 2,
                          R.COLOR_ACCENT if lane["rank"] == 1 else R.COLOR_DIM, right=True)
        cy += 22
    if state.match:
        mx = cx + _text(screen, fonts.small, "Correctitud:", cx, cy + 2, R.COLOR_DIM) + 8
        for v in versions:
            ok = state.match.get(v)
            if v == 1 or ok is None:
                continue
            txt, col = (f"V{v} igual a V1", R.COLOR_OK) if ok else (f"V{v} difiere de V1", R.COLOR_BAD)
            mx += _text(screen, fonts.small, txt, mx, cy + 2, col) + 10


def draw_sidebar(screen, state, fonts):
    """Panel derecho: botones y métricas."""
    w, h = screen.get_size()
    x0 = w - SIDEBAR_W
    pygame.draw.rect(screen, R.COLOR_PANEL, (x0, 0, SIDEBAR_W, h))
    pygame.draw.line(screen, R.COLOR_EDGE, (x0, 0), (x0, h))
    pad = 18
    x, inner = x0 + pad, SIDEBAR_W - 2 * pad
    y = 14

    _text(screen, fonts.title, "Juego de la Vida", x, y, R.COLOR_TEXT)
    _text(screen, fonts.small, "Secuencial vs. paralelo", x + inner, y + 8, R.COLOR_DIM, right=True)
    y += 34

    cmp_on = state.compare_active
    if cmp_on:
        inicio = "Cancelar carrera" if state.running else "¡Iniciar carrera!"
    else:
        inicio = "Pausar" if state.running else "Iniciar"
    _row(screen, state, fonts.body, x, y, inner, 38, [
        _spec(inicio, ("toggle_run", None), "primary", weight=2),
        _spec("Paso", ("step", None), enabled=not cmp_on)])
    y += 46

    _text(screen, fonts.small, "Semilla (la misma semilla = el mismo tablero)", x, y, R.COLOR_DIM)
    y += 18
    gen_w = 96
    _seed_box(screen, state, fonts, pygame.Rect(x, y, inner - gen_w - 8, 30))
    b = Button(pygame.Rect(x + inner - gen_w, y, gen_w, 30), "Generar", ("generate", None))
    state.buttons.append(b)
    _draw_button(screen, fonts.small, b)
    y += 38
    _row(screen, state, fonts.small, x, y, inner, 30, [
        _spec("Al azar", ("random_seed", None)), _spec("Limpiar", ("clear", None))])
    y += 38

    _text(screen, fonts.small, "Versión (carrera: mismo tablero)" if cmp_on
          else "Versión (cada una tiene su propio tablero)", x, y, R.COLOR_DIM)
    y += 18
    _row(screen, state, fonts.small, x, y, inner, 34, [
        _spec(VERSION_LABEL[v], ("version", v), active=(state.version == v))
        for v in config.GUI_VERSIONES], gap=6)
    y += 42

    par = state.version != 1 or cmp_on
    if cmp_on:
        workers_label = "Hilos/proc."
    else:
        workers_label = "Procesos" if state.version == 3 else "Hilos"
    _stepper(screen, state, fonts, x, y, inner, workers_label, str(state.workers) if par else "—",
             ("workers", -1), ("workers", +1), enabled=par)
    y += 34
    if cmp_on:
        _stepper(screen, state, fonts, x, y, inner, "Generaciones", str(state.race_n),
                 ("race_n", -1), ("race_n", +1))
    else:
        fps = "máx" if state.fps == 0 else f"{state.fps} gen/s"
        _stepper(screen, state, fonts, x, y, inner, "Velocidad", fps, ("speed", -1), ("speed", +1))
    y += 34
    _stepper(screen, state, fonts, x, y, inner, "Matriz", f"{state.size} × {state.size}",
             ("size", -1), ("size", +1))
    y += 40

    _text(screen, fonts.small, "Vista", x, y, R.COLOR_DIM)
    y += 18
    _row(screen, state, fonts.small, x, y, inner, 30, [
        _spec("Franjas", ("toggle", "show_bands"), active=state.show_bands),
        _spec("Cambios", ("toggle", "show_changes"), active=state.show_changes),
        _spec("Cuadrícula", ("toggle", "show_lines"), active=state.show_lines),
        _spec("Carrera", ("compare", None), active=cmp_on)])
    y += 38

    # --- métricas
    versions = list(config.GUI_VERSIONES)
    card = pygame.Rect(x, y, inner, (70 + 22 * len(versions)) if cmp_on else 92)
    pygame.draw.rect(screen, R.COLOR_CARD, card, border_radius=8)
    cx, cy = card.x + 12, card.y + 10
    if cmp_on:
        _race_card(screen, state, fonts, card, versions)
    else:
        _text(screen, fonts.body, f"Generación {state.generation}", cx, cy, R.COLOR_TEXT)
        pct = 100 * state.alive / state.cells if state.cells else 0
        _text(screen, fonts.body, f"Vivas {state.alive} ({pct:.0f}%)", card.right - 12, cy, R.COLOR_BODY, right=True)
        cy += 28
        _text(screen, fonts.small, "Tiempo por generación", cx, cy, R.COLOR_DIM)
        ms = f"{state.ms_main:.2f} ms" if state.ms_main else "—"
        _text(screen, fonts.big, ms, cx, cy + 14, R.COLOR_TEXT)
        _text(screen, fonts.small, f"Tablero propio de V{state.version}", card.right - 12,
              cy + 26, R.COLOR_DIM, right=True)
    y = card.bottom + 10
    _row(screen, state, fonts.small, x, y, inner, 30, [
        _spec("Cancelar análisis" if state.analysis_running else "Análisis de rendimiento (A)",
              ("analysis", None), kind="primary" if state.analysis_running else "normal")])
    y += 38

    _text(screen, fonts.small, "Espacio inicia · N paso · F franjas · D cambios · M carrera",
          x, h - 24, R.COLOR_DIM)
