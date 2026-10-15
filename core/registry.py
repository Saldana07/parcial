"""
Lista de versiones V1..V4 y carga de cada una bajo demanda.
"""

import importlib

# versión -> (módulo, clase)
ENGINES = {
    1: ("core.v1_sequential", "SequentialEngine"),
    2: ("core.v2_threads", "ThreadedEngine"),
    3: ("core.v3_processes", "ProcessEngine"),
    4: ("core.v4_hybrid", "HybridEngine"),
}

# Valor de config.MODO_PARALELO -> versión con la que arranca la GUI.
MODOS = {
    "hilos": 2,       # Threads (threading + Barrier)
    "procesos": 3,    # multiprocessing (ProcessPoolExecutor + filas fantasma)
}


class EngineUnavailable(Exception):
    """La versión pedida no se pudo cargar o iniciar."""


def load_engine_class(version):
    """Importa y devuelve la clase del motor de `version`. Lanza EngineUnavailable si no se puede."""
    module_name, class_name = ENGINES[version]
    try:
        module = importlib.import_module(module_name)
        return getattr(module, class_name)
    except (ImportError, AttributeError) as exc:
        raise EngineUnavailable(f"V{version} no disponible: {exc}") from exc


def version_de_modo(modo):
    """Traduce 'hilos' | 'procesos' a su número de versión."""
    if modo not in MODOS:
        raise ValueError(f"Modo desconocido: {modo!r}. Opciones: {', '.join(MODOS)}")
    return MODOS[modo]
