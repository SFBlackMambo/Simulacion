"""Ejecución de réplicas en paralelo."""

from concurrent.futures import ProcessPoolExecutor
from dataclasses import replace

from .simulation import RunResult, SimConfig, run_simulation


def _tarea(args: tuple[SimConfig, float, int]) -> RunResult:
    cfg, v0_kmh, seed = args
    return run_simulation(cfg, v0_kmh, seed)


def run_replicas(
    cfg: SimConfig,
    probe_speeds_kmh: list[float],
    seeds: list[int],
    workers: int = 1,
) -> dict[tuple[float, int], RunResult]:
    """Corre una simulación por cada (velocidad de sonda, semilla).

    Devuelve un diccionario {(v0_kmh, semilla): RunResult}. Con `workers > 1`
    usa procesos; el resultado es el mismo que en serie.
    """
    claves = [(v, s) for v in probe_speeds_kmh for s in seeds]
    tareas = [(cfg, v, s) for v, s in claves]
    if workers <= 1:
        resultados = [_tarea(t) for t in tareas]
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            resultados = list(pool.map(_tarea, tareas))
    return dict(zip(claves, resultados))


def con_flujo(cfg: SimConfig, flow_per_hour: float) -> SimConfig:
    """Copia de `cfg` con otro flujo de llegadas por sentido."""
    return replace(cfg, flow_per_hour=flow_per_hour)
