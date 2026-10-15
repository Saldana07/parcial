"""
Contrato común de las cuatro versiones: Engine(grid, workers), run(n), step(), snapshot() y close().
"""


class Engine:
    """Interfaz base. Cada versión hereda y rellena los métodos."""

    name = "base"   # Etiqueta para el CSV y las gráficas: "v1", "v2", "v3", "v4"

    def __init__(self, initial_grid, workers=1):
        """Prepara el motor a partir de una COPIA de initial_grid (no modifica el original)."""
        raise NotImplementedError

    def run(self, generations):
        """Avanza `generations` generaciones."""
        raise NotImplementedError

    def step(self):
        """Avanza una generación (equivale a run(1))."""
        raise NotImplementedError

    def snapshot(self):
        """Devuelve (una copia de) la matriz actual, para dibujar o comparar."""
        raise NotImplementedError

    def close(self):
        """Libera hilos/procesos. Debe poder llamarse más de una vez sin error."""
        raise NotImplementedError

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()          # se llama siempre, incluso si hubo una excepción
        return False          # no se traga la excepción
