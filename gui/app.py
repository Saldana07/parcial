"""
GUI del Juego de la Vida con pygame. Ejecutar: python -m gui.app
Modos: individual (un tablero por versión), carrera (las cuatro a la vez) y análisis de rendimiento.
"""

import os
import random
import time
import traceback
from dataclasses import dataclass

import pygame

import config
import graficas
from core import grid as grid_mod
from core import partition
from core.registry import EngineUnavailable, load_engine_class, version_de_modo
from gui import controls, renderer
from gui.race import Race

WINDOW_SIZE = (1280, 800)


@dataclass
class Board:
    """Tablero PROPIO de una versión: su matriz y su generación."""
    grid: list
    arr: object
    prev_arr: object
    generation: int


class App:
    def __init__(self):
        pygame.init()
        pygame.display.set_caption("Juego de la Vida — secuencial vs. paralelo")
        self.screen = pygame.display.set_mode(WINDOW_SIZE, pygame.RESIZABLE)
        self.fonts = controls.make_fonts()
        self.clock = pygame.time.Clock()

        version = version_de_modo(config.MODO_PARALELO)
        if version not in config.GUI_VERSIONES:
            version = config.GUI_VERSIONES[-1]
        sizes = config.GUI_TAMANOS
        size_idx = sizes.index(config.GUI_TAMANO) if config.GUI_TAMANO in sizes else 0
        self.ui = controls.UIState(version=version, size_idx=size_idx,
                                   workers_idx=config.TRABAJADORES.index(config.GUI_TRABAJADORES))

        self.grid = None            # matriz de la versión ACTIVA (la que se dibuja / se edita)
        self.arr = None             # esa misma matriz como ndarray
        self.prev_arr = None        # generación anterior (para resaltar nace/muere)
        self.origin = None          # tablero en la generación 0: de aquí parte SIEMPRE cada carrera
        self.analisis = None        # graficas.Analisis en marcha (None si no hay análisis corriendo)
        self.boards = {}            # versión -> Board: el tablero propio de cada versión
        self.engines = {}           # versión -> motor (solo la activa; la carrera usa sus propios procesos)
        self.race = None            # Race en marcha (None si no hay carrera corriendo)
        self.board_rect = pygame.Rect(0, 0, 1, 1)
        self.running_app = True
        self.rev = 0                # sube cada vez que cambia la matriz (invalida la caché del tablero)
        self._board_key = None      # con 1000x1000 dibujar cuesta ~45 ms: solo se redibuja si algo cambió
        self._board_surf = None
        self._board_local = None

        self._safe(self._new_grid, randomize=True, seed=self.ui.seed)

    # --- utilidades
    def _safe(self, fn, *args, **kwargs):
        """Ejecuta fn; si algo falla, pausa y lo muestra en pantalla en vez de caerse."""
        try:
            return fn(*args, **kwargs)
        except NotImplementedError as exc:
            origin = traceback.extract_tb(exc.__traceback__)[-1]
            self._fail(f"Pendiente de implementar: {origin.name}() en {os.path.basename(origin.filename)}")
        except EngineUnavailable as exc:
            self._fail(str(exc))
        except Exception as exc:                      # noqa: BLE001 - la GUI no debe caerse
            self._fail(f"Error: {exc}")
            self._close_engines()
        return None

    def _fail(self, message):
        self.ui.running = False
        self.ui.status = message

    def _cell_at(self, pos):
        if self.arr is None:
            return None
        return renderer.cell_from_pos(pos, self.board_rect, *self.arr.shape)

    def _set_grid(self, grid):
        self.rev += 1
        self.grid = grid
        self.arr = renderer.to_array(grid)
        self.ui.alive = int(self.arr.sum())
        self.ui.cells = self.arr.size

    def _close_engines(self):
        for eng in self.engines.values():
            eng.close()
        self.engines.clear()

    # --- tableros por versión
    def _new_board(self, grid, generation=0):
        """Board nuevo con una COPIA de `grid` (así ningún tablero comparte celdas con otro)."""
        g = grid_mod.copy(grid)
        return Board(g, renderer.to_array(g), None, generation)

    def _stash(self):
        """Guarda lo que se ve ahora en el tablero de la versión activa."""
        self.boards[self.ui.version] = Board(self.grid, self.arr, self.prev_arr, self.ui.generation)

    def _load(self, version):
        """Muestra el tablero propio de `version` (con su generación)."""
        b = self.boards[version]
        self.grid, self.prev_arr = b.grid, b.prev_arr
        self.ui.generation = b.generation
        self._set_grid(b.grid)                       # recalcula arr, vivas y celdas, y redibuja

    def _reset_boards(self):
        """Todas las versiones vuelven al tablero inicial (generación 0)."""
        self.boards = {v: self._new_board(self.origin) for v in config.GUI_VERSIONES}
        self._load(self.ui.version)

    def _reset_metrics(self):
        self.ui.ms.clear()
        self.ui.match.clear()

    def _bands(self):
        """Reparto de filas por trabajador (el mismo que usan V2 y V3) y sus etiquetas."""
        rows = self.arr.shape[0]
        if self.ui.version == 1:
            return [(0, rows)], ["Secuencial"]
        ranges = partition.row_ranges(rows, self.ui.workers)
        word = "Proceso" if self.ui.version == 3 else "Hilo"
        return ranges, [f"{word} {i}" for i in range(len(ranges))]

    # --- acciones
    def _new_grid(self, randomize, seed=None):
        n = self.ui.size
        g = grid_mod.new_grid(n, n)
        if randomize:
            self.ui.seed = seed
            self.ui.seed_text = str(seed)
            grid_mod.randomize(g, seed, config.DENSIDAD)
        self._close_engines()
        self.origin = grid_mod.copy(g)
        self._reset_boards()          # un tablero NUEVO por versión, todos con la misma matriz inicial
        self.ui.status = ""
        self._reset_metrics()

    def _make_engine(self, version):
        """Crea el motor de `version` a partir de la matriz actual."""
        return load_engine_class(version)(self.grid, 1 if version == 1 else self.ui.workers)

    def _ensure_engines(self):
        """Garantiza que exista el motor de la versión activa, creado desde SU tablero."""
        if set(self.engines) == {self.ui.version}:
            return
        self._close_engines()
        self.engines[self.ui.version] = self._make_engine(self.ui.version)

    def _switch_version(self, version):
        """Cambia de versión; si no se puede cargar, se queda con la anterior."""
        previous = self.ui.version
        self._stash()                    # el tablero de la versión que se deja queda como está
        self.ui.version = version
        self._load(version)              # se muestra el tablero PROPIO de la nueva versión
        self.ui.status = ""
        self._close_engines()
        self._reset_metrics()
        try:
            if not self.ui.compare_active:   # en la carrera cada versión corre en su propio proceso
                self._ensure_engines()       # falla pronto si la versión no existe
        except EngineUnavailable:
            self.ui.version = previous
            self._load(previous)
            raise

    def _step_once(self):
        """Avanza UNA generación de la versión activa (el modo individual; la carrera va aparte)."""
        ui = self.ui
        self._ensure_engines()
        prev = self.arr
        engine = self.engines[ui.version]

        t0 = time.perf_counter()
        engine.step()
        dt = (time.perf_counter() - t0) * 1000

        self.prev_arr = prev
        self._set_grid(engine.snapshot())
        ui.generation += 1
        # promedio exponencial: estable y sin guardar historial largo
        old_ms = ui.ms.get(ui.version, 0.0)
        ui.ms[ui.version] = dt if old_ms == 0 else 0.9 * old_ms + 0.1 * dt

    # --- carrera
    def _race_view(self, race):
        """Resumen de la carrera para dibujar (datos simples: controls.py no conoce a Race)."""
        ranking = race.ranking
        return {"phase": race.phase, "n": race.generations, "order": ranking,
                "lanes": [{"v": v, "done": race.done(v), "elapsed": race.elapsed(v),
                           "rank": ranking.index(v) + 1 if v in ranking else 0,
                           "error": race.errors.get(v)} for v in race.versions]}

    def _race_tick(self):
        """Un cuadro de la carrera: la crea si no existe, la sigue y la cierra cuando todos llegan."""
        ui = self.ui
        if self.race is None:
            self._reset_boards()                      # SIEMPRE desde la generación 0, no desde donde terminó la anterior
            self._close_engines()
            ui.match.clear()
            ui.ms.clear()
            self.race = Race(config.GUI_VERSIONES, self.grid, ui.workers, ui.race_n)
        race = self.race
        race.poll()
        ui.race_view = self._race_view(race)
        ui.status = ("Preparando la carrera… (V3 crea sus procesos antes de la salida)"
                     if race.phase == "preparando" else "")
        if race.finished:
            self._finish_race()

    def _finish_race(self):
        """Todos llegaron: cada tablero guarda la matriz final de su versión y se muestran los resultados."""
        ui, race = self.ui, self.race
        ui.race_view = self._race_view(race)
        self.race = None
        race.cancel()                                 # los procesos ya terminaron: solo los recoge
        ui.running = False
        n = race.generations
        for v, (seconds, final) in race.results.items():
            self.boards[v] = self._new_board(final, self.boards[v].generation + n)
            ui.ms[v] = seconds * 1000 / n             # ms por generación promedio (para el speedup)
        base = race.results.get(1)
        if base is not None:
            for v, (_, final) in race.results.items():
                if v != 1:
                    ui.match[v] = grid_mod.equals(base[1], final)
        self._load(ui.version)
        if race.ranking:
            w = race.ranking[0]
            ui.status = f"Ganó V{w}: {n} generaciones en {race.results[w][0]:.2f} s"
        else:
            ui.status = "Ninguna versión terminó la carrera"

    # --- análisis de rendimiento
    def _toggle_analysis(self):
        """Lanza el análisis en un proceso aparte, o lo cancela si ya está corriendo."""
        ui = self.ui
        if self.analisis is not None:
            self.analisis.cancel()
            self.analisis = None
            ui.analysis_running = False
            ui.status = "Análisis de rendimiento cancelado"
            return
        ui.running = False
        self._cancel_race()
        self._close_engines()                         # liberar hilos/procesos de la GUI antes de medir
        self.analisis = graficas.Analisis(**graficas.parametros(ui.seed, ui.workers))
        ui.analysis_running = True
        ui.status = "Análisis de rendimiento: preparando…"

    def _analysis_tick(self):
        """Un cuadro del análisis: muestra el progreso y, al terminar, abre la gráfica."""
        a, ui = self.analisis, self.ui
        a.poll()
        if not a.terminado:
            ui.status = f"Análisis de rendimiento {a.hechas}/{a.total or '?'}: {a.texto}"
            return
        self.analisis = None
        ui.analysis_running = False
        if a.error:
            ui.status = f"El análisis falló: {a.error}"
        elif a.ruta:
            ui.status = f"Análisis listo: graficas/{os.path.basename(a.ruta)} (y su .csv con los datos)"
            if hasattr(os, "startfile"):              # Windows: abrir la gráfica con el visor de imágenes
                os.startfile(a.ruta)
        else:
            ui.status = "Análisis de rendimiento cancelado"

    def _cancel_race(self, message=""):
        """Detiene la carrera en marcha (si la hay) y limpia sus procesos."""
        if self.race is not None:
            self.race.cancel()
            self.race = None
            self.ui.race_view = None
            self.ui.status = message

    def _edited(self):
        """La matriz se editó a mano: se recrean los motores con ella al avanzar."""
        self.rev += 1
        self._close_engines()
        self.prev_arr = None
        self.ui.match.clear()
        self.ui.alive = int(self.arr.sum())
        if self.ui.generation == 0:
            self.origin = grid_mod.copy(self.grid)    # lo pintado en la generación 0 es parte del tablero inicial

    def _paint(self, r, c, value):
        if self.grid is None:
            return
        self._cancel_race("Carrera cancelada: se editó el tablero")
        self.grid[r][c] = value       # el snapshot es una copia (contrato de Engine)
        self.arr[r, c] = value
        self._edited()

    def _apply(self, action):
        name, data = action
        ui = self.ui
        if name == "quit":
            self.running_app = False
        elif name == "step":
            if self.analisis is not None:
                ui.status = "Espera a que termine el análisis de rendimiento (o cancélalo)"
            elif ui.compare_active:
                ui.status = "En la carrera todas corren solas: usa Iniciar"
            else:
                self._safe(self._step_once)
        elif name == "generate":                      # tablero aleatorio con la semilla escrita
            text = ui.seed_text.strip()
            if not text.isdigit():
                ui.status = "Escribe una semilla (solo números)"
            else:
                ui.running = False
                self._cancel_race()
                self._safe(self._new_grid, randomize=True, seed=int(text))
        elif name == "random_seed":                   # semilla al azar (queda escrita en el cuadro)
            ui.running = False
            self._cancel_race()
            self._safe(self._new_grid, randomize=True, seed=random.randrange(10**6))
        elif name == "clear":
            ui.running = False
            self._cancel_race()
            self._safe(self._new_grid, randomize=False)
        elif name == "version":
            if data != ui.version:
                self._safe(self._switch_version, data)
        elif name == "workers":
            idx = max(0, min(len(config.TRABAJADORES) - 1, ui.workers_idx + data))
            if idx != ui.workers_idx:
                ui.workers_idx = idx
                ui.running = False
                self._cancel_race()
                self._close_engines()
                self._reset_metrics()
        elif name == "size":
            idx = max(0, min(len(config.GUI_TAMANOS) - 1, ui.size_idx + data))
            if idx != ui.size_idx:
                ui.size_idx = idx
                ui.running = False
                self._cancel_race()
                self._safe(self._new_grid, randomize=True, seed=ui.seed)
        elif name == "analysis":
            self._toggle_analysis()
        elif name == "race_n":
            idx = max(0, min(len(config.GUI_CARRERA_GENERACIONES) - 1, ui.race_idx + data))
            if idx != ui.race_idx:
                ui.race_idx = idx
                ui.running = False
                self._cancel_race()
                ui.race_view = None
        elif name == "compare":
            ui.running = False
            self._cancel_race()
            ui.compare = not ui.compare               # CARRERA: V1..V4 corren a la vez desde cualquier versión
            ui.race_view = None
            ui.status = (f"Carrera: pulsa Iniciar. Todas parten del tablero de V{ui.version}"
                         if ui.compare else "")
            self._close_engines()
            self._reset_metrics()
        elif name == "paint":
            self._paint(*data)

    # --- bucle
    def _draw(self):
        self.screen.fill(renderer.COLOR_BG)
        self.ui.buttons = []                          # cada cuadro registra sus botones desde cero
        w, h = self.screen.get_size()
        left_w = w - controls.SIDEBAR_W
        legend = pygame.Rect(16, 8, left_w - 32, 30)
        status = pygame.Rect(16, h - controls.STATUS_H - 10, left_w - 32, controls.STATUS_H)
        area = pygame.Rect(16, 44, left_w - 32, status.y - 44 - 8)

        if self.arr is not None:
            ranges, labels = self._bands()
            ui = self.ui
            key = (self.rev, ui.show_lines, ui.show_bands, ui.show_changes, ui.version, ui.workers, area.size)
            if key != self._board_key:               # solo se redibuja si cambió algo
                surf = pygame.Surface(area.size)
                surf.fill(renderer.COLOR_BG)
                self._board_local = renderer.draw_board(
                    surf, self.arr, surf.get_rect(), ui.show_lines, self.prev_arr, ui.show_changes,
                    ranges if ui.show_bands else None, labels, self.fonts.small)
                self._board_surf, self._board_key = surf, key
            self.screen.blit(self._board_surf, area.topleft)
            self.board_rect = self._board_local.move(area.topleft)
        else:
            msg = "Matriz no disponible: revisar core/grid.py"
            surf = self.fonts.body.render(msg, True, renderer.COLOR_WARN)
            self.screen.blit(surf, surf.get_rect(center=area.center))
            self.board_rect = pygame.Rect(0, 0, 1, 1)

        controls.draw_legend(self.screen, legend, self.ui, self.fonts)
        controls.draw_status(self.screen, status, self.ui, self.fonts)
        controls.draw_sidebar(self.screen, self.ui, self.fonts)
        pygame.display.flip()

    def run(self):
        last_step = time.perf_counter()
        try:
            while self.running_app:
                for event in pygame.event.get():
                    action = controls.handle_event(event, self.ui, self._cell_at)
                    if action:
                        self._apply(action)
                if self.analisis is not None:
                    self.ui.running = False               # mientras se mide, la GUI no compite por la CPU
                    self._analysis_tick()
                if self.ui.running and self.ui.compare_active:
                    self._safe(self._race_tick)           # la carrera avanza sola, en sus propios procesos
                elif self.ui.running:
                    now = time.perf_counter()
                    fps = self.ui.fps
                    if fps == 0 or now - last_step >= 1.0 / fps:
                        self._safe(self._step_once)
                        last_step = now
                elif self.race is not None:               # Cancelar durante la carrera
                    self._cancel_race("Carrera cancelada")
                self._draw()
                self.clock.tick(60)
        finally:
            if self.analisis is not None:
                self.analisis.cancel()
            self._cancel_race()
            self._close_engines()
            pygame.quit()


def main():
    """Inicializa pygame y ejecuta el bucle principal."""
    App().run()


if __name__ == "__main__":
    main()