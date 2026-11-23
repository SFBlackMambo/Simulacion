"""Una corrida completa: tráfico de fondo aleatorio y vehículos sonda."""

from dataclasses import dataclass, field

import numpy as np

from .arrivals import PoissonArrivals
from .idm import IDMParams
from .overtaking import OvertakeParams
from .recorder import Recorder, viaje
from .road import Road
from .vehicle import kmh_a_ms


@dataclass(frozen=True)
class SimConfig:
    """Configuración de una corrida (distancias en m, tiempos en s, velocidades en km/h)."""

    length: float = 20_000.0
    dt: float = 0.2
    flow_per_hour: float = 300.0  # tasa de llegadas por sentido
    v0_mean_kmh: float = 100.0
    v0_std_kmh: float = 10.0
    warmup: float = 1_500.0  # tiempo antes de la primera sonda, para llenar la carretera
    n_probes: int = 30
    probe_spacing: float = 90.0  # entre sondas, s
    idm: IDMParams = field(default_factory=IDMParams)
    overtaking: OvertakeParams | None = field(default_factory=OvertakeParams)


@dataclass
class ProbeResult:
    """Resultado de una sonda."""

    index: int
    v0_kmh: float
    t_entry: float
    travel_time: float
    free_time: float  # L / v0
    overtakes: int
    t_slow: float
    t_wait_entry: float

    @property
    def delay(self) -> float:
        return self.travel_time - self.free_time


@dataclass
class RunResult:
    probes: list[ProbeResult]
    collisions: int
    emergency_vehicles: int
    background_finished: int
    trips: list[dict] = field(default_factory=list)  # viaje de cada vehículo que salió
    recorder: Recorder | None = None


def run_simulation(
    cfg: SimConfig, probe_v0_kmh: float, seed: int, recorder: Recorder | None = None
) -> RunResult:
    """Corre una simulación con sondas de velocidad deseada `probe_v0_kmh`.

    El tráfico de fondo depende solo de `seed` (números aleatorios comunes): dos
    corridas con la misma semilla y distinta velocidad de sonda ven el mismo
    tráfico de fondo, y las sondas entran en los mismos instantes.
    """
    road = Road(length=cfg.length, dt=cfg.dt, idm=cfg.idm, overtaking=cfg.overtaking, recorder=recorder)
    seeds = np.random.SeedSequence(seed).spawn(2)
    for direction, ss in zip((1, -1), seeds):
        road.add_source(
            direction,
            PoissonArrivals(cfg.flow_per_hour, cfg.v0_mean_kmh, cfg.v0_std_kmh, seed=ss),
        )

    probes = []
    entry_times = [cfg.warmup + i * cfg.probe_spacing for i in range(cfg.n_probes)]
    for t_inject in entry_times:
        road.run(t_inject - road.t)
        probes.append(road.inject(kmh_a_ms(probe_v0_kmh), direction=1, probe=True))
    max_time = cfg.length / kmh_a_ms(40) + 600.0
    deadline = road.t + max_time
    while any(p.t_exit is None for p in probes) and road.t < deadline:
        road.run(10.0)
    if any(p.t_exit is None for p in probes):
        raise RuntimeError("alguna sonda no terminó el recorrido")

    results = [
        ProbeResult(
            index=i,
            v0_kmh=probe_v0_kmh,
            t_entry=p.t_entry,
            travel_time=p.travel_time,
            free_time=cfg.length / p.v0,
            overtakes=p.overtakes,
            t_slow=p.t_slow,
            t_wait_entry=p.t_wait_entry,
        )
        for i, p in enumerate(probes)
    ]
    background = [v for v in road.finished if not v.probe]
    return RunResult(
        probes=results,
        collisions=road.collisions,
        emergency_vehicles=sum(v.emergency_steps > 0 for v in road.finished),
        background_finished=len(background),
        trips=[viaje(v, cfg.length / v.v0) for v in road.finished],
        recorder=recorder,
    )
