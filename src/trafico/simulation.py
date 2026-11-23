"""Una corrida completa: tráfico de fondo aleatorio y vehículos sonda."""

from dataclasses import dataclass, field

import numpy as np

from .arrivals import PoissonArrivals
from .drivers import DriverModel
from .fleet import CAMION, TruckParams
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
    # Cómo se genera el tráfico de fondo:
    #   "flujo": llegadas de Poisson con `flow_per_hour` por sentido (sin fin).
    #   "lleno": arranca con `n_vehicles` por sentido repartidos en la carretera; cada
    #            uno que sale se repone, así que la cantidad se mantiene.
    #   "total": entran exactamente `n_vehicles` por sentido (Poisson a `flow_per_hour`)
    #            y la corrida termina cuando han salido todos.
    mode: str = "flujo"
    n_vehicles: int = 0
    duration: float = 0.0  # la corrida dura al menos warmup + duration, s
    # Trazado: "recta", un trazado generado (ver geometry.PRESETS) o curvas explícitas.
    trazado: str = "recta"
    geometry_seed: int = 0  # semilla del trazado generado; 0 = la misma que el tráfico
    curves: tuple = ()  # ((inicio, fin, radio), ...) en m; se usa si trazado == "recta"
    curve_a_lat: float = 2.0  # aceleración lateral cómoda en curva, m/s²
    sight_clearance: float = 10.0  # despeje lateral para la visibilidad en curva, m
    trucks: TruckParams = field(default_factory=TruckParams)  # trucks.share = 0: sin camiones
    relieve: str = "plano"  # perfil de pendientes generado (ver geometry.RELIEVES)
    grades: tuple = ()  # ((inicio, fin, pendiente en fracción), ...); se usa si relieve == "plano"
    speed_limit_kmh: float = 0.0  # límite de velocidad en toda la carretera (0 = sin límite)
    speed_limits: tuple = ()  # ((inicio, fin, km/h), ...) límites por tramo (se suman al general)
    no_pass_zones: tuple = ()  # ((inicio, fin), ...) zonas de no rebase señalizadas
    no_pass_from_sight: bool = False  # señalizar no rebase donde no hay visibilidad (curvas)
    drivers: DriverModel = field(default_factory=DriverModel)
    reaction_time: float = 0.0  # tiempo de reacción de los conductores, s (0 = inmediato)
    b_physical: float = 0.0  # frenado máximo físico, m/s² (0 = sin tope)


MODOS = ("flujo", "lleno", "total")


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


_GEOMETRIAS: dict = {}


def geometry_from_config(cfg: SimConfig, seed: int = 1):
    """Trazado de `cfg` (None si es recto). Se guarda en caché por proceso.

    Con `geometry_seed = 0` el trazado generado depende de la semilla del tráfico
    `seed`: cada réplica ve una carretera distinta del mismo tipo.
    """
    from .geometry import Geometry, build_relieve, build_trazado

    gseed = cfg.geometry_seed or seed
    generado = cfg.trazado != "recta" or cfg.relieve != "plano"
    clave = (cfg.length, cfg.trazado, cfg.relieve, gseed if generado else 0, tuple(map(tuple, cfg.curves)),
             tuple(map(tuple, cfg.grades)), cfg.curve_a_lat, cfg.sight_clearance, cfg.speed_limit_kmh,
             tuple(map(tuple, cfg.speed_limits)), tuple(map(tuple, cfg.no_pass_zones)), cfg.no_pass_from_sight)
    if clave not in _GEOMETRIAS:
        if cfg.trazado == "recta":
            curvas = tuple(map(tuple, cfg.curves))
        else:
            curvas = build_trazado(cfg.trazado, cfg.length, gseed)
        if cfg.relieve == "plano":
            pend = tuple(map(tuple, cfg.grades))
        else:
            pend = build_relieve(cfg.relieve, cfg.length, gseed)
        limites = tuple(map(tuple, cfg.speed_limits))
        if cfg.speed_limit_kmh > 0:
            limites = _con_limite_general(limites, cfg.length, cfg.speed_limit_kmh)
        geo = Geometry(cfg.length, curvas, a_lat=cfg.curve_a_lat, clearance=cfg.sight_clearance, grades=pend,
                       limits=limites, no_pass_zones=tuple(map(tuple, cfg.no_pass_zones)),
                       no_pass_from_sight=cfg.no_pass_from_sight)
        _GEOMETRIAS[clave] = None if geo.straight else geo
    return _GEOMETRIAS[clave]


def _con_limite_general(tramos: tuple, length: float, general: float) -> tuple:
    """Rellena con el límite general los huecos entre límites por tramo."""
    out, x = [], 0.0
    for a, b, v in sorted(tramos):
        if a > x:
            out.append((x, a, general))
        out.append((a, b, v))
        x = max(x, b)
    if x < length:
        out.append((x, length, general))
    return tuple(out)


def _plana(length: float):
    from .geometry import Geometry

    clave = ("plana", length)
    if clave not in _GEOMETRIAS:
        _GEOMETRIAS[clave] = Geometry(length)
    return _GEOMETRIAS[clave]


def free_time(cfg: SimConfig, v0: float, direction: int = 1, exact: bool = True, seed: int = 1,
              kind: str = "auto", limit_factor: float = 1.0, grades=None) -> float:
    """Tiempo de viaje en vía libre (s) para velocidad deseada `v0` (m/s)."""
    geo = geometry_from_config(cfg, seed)
    if geo is None:
        if kind != CAMION:
            return cfg.length / v0
        geo = _plana(cfg.length)  # los camiones tienen física de motor también en llano
    idm = cfg.trucks.idm if kind == CAMION else cfg.idm
    resp = (grades or cfg.trucks.response()) if kind == CAMION else None
    if exact or limit_factor != 1.0 or kind == CAMION:  # cada camión tiene su potencia
        return geo.free_time(v0, direction, idm, cfg.dt, resp, limit_factor)
    return geo.free_time_interp(v0, direction, idm, cfg.dt, resp)


def probe_times(cfg: SimConfig) -> list[float]:
    """Instantes de entrada de las sondas."""
    return [cfg.warmup + i * cfg.probe_spacing for i in range(cfg.n_probes)]


def build_road(cfg: SimConfig, seed: int, recorder: Recorder | None = None) -> Road:
    """Carretera con el tráfico de fondo de `cfg` (sin sondas), lista para avanzar.

    Cada sentido tiene su propio generador (hijos de `seed`), así que el tráfico
    de fondo depende solo de la semilla.
    """
    if cfg.mode not in MODOS:
        raise ValueError(f"modo desconocido {cfg.mode!r}; opciones: {MODOS}")
    seq = np.random.SeedSequence(seed)
    ss = seq.spawn(2)  # llegadas de cada sentido (mismos hijos que antes)
    road = Road(length=cfg.length, dt=cfg.dt, idm=cfg.idm, overtaking=cfg.overtaking, recorder=recorder,
                geometry=geometry_from_config(cfg, seed), trucks=cfg.trucks, drivers=cfg.drivers,
                driver_seed=seq.spawn(1)[0], truck_seed=seq.spawn(1)[0] if cfg.trucks.share > 0 else None,
                reaction_time=cfg.reaction_time,
                b_physical=cfg.b_physical)
    for direction, s in zip((1, -1), ss):
        if cfg.mode == "lleno":
            sampler = PoissonArrivals(0.0, cfg.v0_mean_kmh, cfg.v0_std_kmh, seed=s, trucks=cfg.trucks)
            road.fill(direction, cfg.n_vehicles, sampler)
            road.keep_count(direction, sampler)
        else:
            limit = cfg.n_vehicles if cfg.mode == "total" else None
            road.add_source(
                direction,
                PoissonArrivals(cfg.flow_per_hour, cfg.v0_mean_kmh, cfg.v0_std_kmh, seed=s, max_count=limit,
                                trucks=cfg.trucks),
            )
    return road


def run_simulation(
    cfg: SimConfig, probe_v0_kmh: float, seed: int, recorder: Recorder | None = None
) -> RunResult:
    """Corre una simulación con sondas de velocidad deseada `probe_v0_kmh`.

    El tráfico de fondo depende solo de `seed` (números aleatorios comunes): dos
    corridas con la misma semilla y distinta velocidad de sonda ven el mismo
    tráfico de fondo, y las sondas entran en los mismos instantes.
    """
    road = build_road(cfg, seed, recorder)
    probes = []
    for t_inject in probe_times(cfg):
        road.run(t_inject - road.t)
        probes.append(road.inject(kmh_a_ms(probe_v0_kmh), direction=1, probe=True))
    max_time = cfg.length / kmh_a_ms(40) + 600.0
    deadline = max(road.t, cfg.warmup + cfg.duration) + max_time
    if cfg.mode == "total" and cfg.flow_per_hour > 0:
        deadline += 3 * 3600.0 * cfg.n_vehicles / cfg.flow_per_hour

    def falta():
        if any(p.t_exit is None for p in probes) or road.t < cfg.warmup + cfg.duration:
            return True
        return cfg.mode == "total" and not (road.sources_exhausted and not road.vehicles and not road.pending)

    while falta() and road.t < deadline:
        road.run(10.0)
    if any(p.t_exit is None for p in probes):
        raise RuntimeError("alguna sonda no terminó el recorrido")

    results = [
        ProbeResult(
            index=i,
            v0_kmh=probe_v0_kmh,
            t_entry=p.t_entry,
            travel_time=p.travel_time,
            free_time=free_time(cfg, p.v0, seed=seed),
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
        trips=[viaje(v, free_time(cfg, v.v0, v.direction, exact=False, seed=seed, kind=v.kind,
                                  limit_factor=v.limit_factor, grades=v.grades),
                     cfg.length if v.full_trip else 0.0) for v in road.finished],
        recorder=recorder,
    )
