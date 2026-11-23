"""Carretera: simulación por pasos de tiempo."""

import math
from collections import deque
from operator import attrgetter

from .arrivals import PoissonArrivals
from . import overtaking
from .fleet import AUTO, CAMION, LARGO_AUTO, TruckParams
from .geometry import curve_accel
from .idm import IDMParams, advance, idm_acceleration
from .overtaking import OvertakeParams
from .vehicle import Vehicle

_POR_X = attrgetter("x")


class Road:
    """Carretera recta con un carril por sentido.

    Los vehículos entran por `x = 0` de su sentido y salen en `x = length`.
    Todos se actualizan a la vez en cada paso de tiempo `dt`.
    """

    def __init__(
        self,
        length: float = 20_000.0,
        dt: float = 0.1,
        idm: IDMParams = IDMParams(),
        t_emergency: float = 3.0,
        b_emergency: float = 6.0,
        d_emergency: float = 30.0,
        overtaking: OvertakeParams | None = None,
        recorder=None,
        geometry=None,
        trucks=None,
    ) -> None:
        self.length = length
        self.dt = dt
        self.idm = idm
        self.t_emergency = t_emergency  # tiempo a colisión frontal que dispara el frenado
        self.b_emergency = b_emergency  # deceleración de emergencia, m/s²
        self.d_emergency = d_emergency  # distancia mínima frente a frente, m
        self.overtaking = overtaking  # None: nadie rebasa
        self.recorder = recorder  # Recorder opcional (solo lee el estado)
        self.geometry = geometry if geometry is not None and not geometry.straight else None
        self.trucks = trucks  # TruckParams: tamaño y dinámica de los camiones
        self.t = 0.0
        self.n_steps = 0
        self.vehicles: list[Vehicle] = []
        self.finished: list[Vehicle] = []
        self.collisions = 0
        self._pending: dict[int, deque[Vehicle]] = {1: deque(), -1: deque()}
        self._sources: dict[int, PoissonArrivals] = {}
        self._replacers: dict[int, PoissonArrivals] = {}
        self._next_id = 0

    # ------------------------------------------------------------------
    # Creación de vehículos
    # ------------------------------------------------------------------
    def _nuevo(self, v0: float, direction: int, probe: bool, kind: str = AUTO, **kw) -> Vehicle:
        if kind == CAMION:
            t = self.trucks or TruckParams()
            kw.setdefault("length", t.length)
            kw["idm"] = t.idm
        veh = Vehicle(self._next_id, v0, direction=direction, probe=probe, kind=kind, **kw)
        self._next_id += 1
        return veh

    def inject(self, v0: float, direction: int = 1, probe: bool = False, kind: str = AUTO) -> Vehicle:
        """Pone un vehículo en la cola de entrada de su sentido."""
        veh = self._nuevo(v0, direction, probe, kind)
        self._pending[direction].append(veh)
        return veh

    def add_source(self, direction: int, source: PoissonArrivals) -> None:
        """Conecta una fuente de llegadas a la entrada de un sentido."""
        self._sources[direction] = source

    def keep_count(self, direction: int, sampler: PoissonArrivals) -> None:
        """Cada vehículo de fondo que sale por este sentido se repone con uno nuevo.

        Así el número de vehículos por sentido se mantiene (modo "carretera llena").
        La velocidad deseada del nuevo se toma de `sampler`.
        """
        self._replacers[direction] = sampler

    def fill(self, direction: int, n: int, sampler: PoissonArrivals) -> list[Vehicle]:
        """Llena la carretera con `n` vehículos equiespaciados en un sentido.

        La velocidad inicial es la deseada, limitada a la que permite el hueco
        con el de delante (IDM en equilibrio), para que no haya frenazos al inicio.
        Se marcan con `full_trip=False` porque no recorren la carretera completa.
        """
        if n <= 0:
            return []
        spacing = self.length / n
        largo = LARGO_AUTO if sampler.trucks is None else max(LARGO_AUTO, sampler.trucks.length)
        if spacing < largo + self.idm.s0 + 0.5:
            raise ValueError(f"{n} vehículos no caben en {self.length:g} m")
        gap = spacing - largo
        v_max = max(0.0, (gap - self.idm.s0) / self.idm.T)
        out = []
        for i in range(n):
            v0, kind = sampler.sample()
            x = self.length - 1.0 - i * spacing  # el primero casi en la salida
            veh = self.place(v0, x, v=min(v0, v_max), direction=direction, kind=kind)
            veh.full_trip = False
            out.append(veh)
        return out

    def place(
        self,
        v0: float,
        x: float,
        v: float | None = None,
        direction: int = 1,
        lane: int | None = None,
        probe: bool = False,
        length: float | None = None,
        kind: str = AUTO,
    ) -> Vehicle:
        """Coloca un vehículo directamente en la carretera (escenarios y tests)."""
        kw = {} if length is None else {"length": length}
        veh = self._nuevo(v0, direction, probe, kind, x=x, v=v0 if v is None else v, **kw)
        if lane is not None:
            veh.lane = lane
        veh.t_entry = self.t
        self.vehicles.append(veh)
        return veh

    # ------------------------------------------------------------------
    # Entrada de vehículos
    # ------------------------------------------------------------------
    def _try_enter(self) -> None:
        for queue in self._pending.values():
            if not queue:
                continue
            veh = queue[0]
            v_in = self._entry_speed(veh)
            if v_in is None:
                for w in queue:
                    w.t_wait_entry += self.dt
                continue
            queue.popleft()
            veh.x, veh.v, veh.t_entry = 0.0, v_in, self.t
            self.vehicles.append(veh)
            for w in queue:
                w.t_wait_entry += self.dt

    def _entry_speed(self, veh: Vehicle) -> float | None:
        """Velocidad de entrada, o None si no hay hueco suficiente."""
        last = None
        for u in self.vehicles:
            if not u.occupies(veh.lane):
                continue
            if u.direction == veh.direction:
                if last is None or u.x < last.x:
                    last = u
            elif self.front_in_opposite_frame(u) < 200.0 and self.front_in_opposite_frame(u) + u.length > 0:
                return None  # un rebasante contrario viene de frente por este carril
        v_max = veh.v0 if self.geometry is None else min(veh.v0, self.geometry.limit(veh.direction, 0.0))
        if last is None:
            return v_max
        gap = last.rear  # el frente del que entra está en x = 0
        v_in = min(v_max, last.v) if gap < 200.0 else v_max
        if gap >= self.idm.s0 + v_in * self.idm.T:
            return v_in
        return None

    def position(self, veh: Vehicle) -> float:
        """Posición del frente en coordenadas de la carretera (las del sentido +1)."""
        return veh.x if veh.direction == 1 else self.length - veh.x

    def event(self, kind: str, veh: Vehicle, n: int = 0) -> None:
        """Avisa de un evento al registro, si hay."""
        if self.recorder is not None:
            self.recorder.event(self, kind, veh, n)

    def front_in_opposite_frame(self, other: Vehicle) -> float:
        """Posición del frente de `other` medida en el sistema del sentido contrario."""
        return self.length - other.x

    # ------------------------------------------------------------------
    # Paso de simulación
    # ------------------------------------------------------------------
    def _groups(self) -> dict[tuple[int, int], list[Vehicle]]:
        """Vehículos por (carril, sentido), ordenados de delante hacia atrás."""
        groups: dict[tuple[int, int], list[Vehicle]] = {}
        for veh in self.vehicles:
            groups.setdefault((veh.lane, veh.direction), []).append(veh)
            if veh.lc < 1.0:  # cambiando de carril: ocupa también el que deja
                groups.setdefault((veh.lane_prev, veh.direction), []).append(veh)
        for lst in groups.values():
            lst.sort(key=_POR_X, reverse=True)
        return groups

    def step(self) -> None:
        """Avanza la simulación un paso `dt`."""
        for direction, source in self._sources.items():
            for v0, kind in source.due_vehicles(self.t):
                self.inject(v0, direction, kind=kind)
        self._try_enter()
        groups = self._groups()
        if self.overtaking is not None and overtaking.update(self, groups):
            groups = self._groups()
        idm, dt, geo = self.idm, self.dt, self.geometry
        accels: list[tuple[Vehicle, float, bool]] = []
        for (lane, direction), lst in groups.items():
            opposite = groups.get((lane, -direction))
            leader = None
            for veh in lst:
                v0 = veh.v0
                if geo is not None:
                    v0 = min(v0, geo.limit(direction, veh.x))
                    veh.v_des = v0
                p_idm = veh.idm or idm
                if leader is None:
                    a = idm_acceleration(veh.v, v0, None, None, p_idm)
                else:
                    a = idm_acceleration(veh.v, v0, leader.rear - veh.x, leader.v, p_idm)
                if geo is not None:
                    a = curve_accel(a, veh.v, v0)
                if opposite:
                    a = self._head_on_brake(veh, opposite, a)
                # ¿lo frena alguien? (líder a menos de 4 s o de 50 m)
                cerca = leader is not None and leader.rear - veh.x < max(50.0, 4.0 * veh.v)
                accels.append((veh, a, cerca))
                leader = veh
        if any(v.lc < 1.0 for v in self.vehicles):
            accels = _fusionar(accels)
        t_lc = self.overtaking.t_lane_change if self.overtaking is not None else 0.0
        for veh, a, cerca in accels:
            advance(veh, a, dt)
            if veh.lc < 1.0:
                veh.lc = min(1.0, veh.lc + dt / t_lc) if t_lc > 0 else 1.0
            if veh.v < veh.v_des - 1.0:
                veh.t_slow += dt
                if not veh.slowed and cerca:
                    veh.slowed = True
                    veh.catchups += 1
            elif veh.slowed and veh.v > veh.v_des - 0.3:
                veh.slowed = False
        self.t += dt
        self.n_steps += 1
        self._count_collisions(groups)
        self._remove_finished()
        if self.recorder is not None:
            self.recorder.on_step(self)

    def _head_on_brake(self, veh: Vehicle, opposite: list[Vehicle], a: float) -> float:
        """Frenado de emergencia si hay un choque frontal inminente en este carril."""
        for other in opposite:
            gap = self.front_in_opposite_frame(other) - veh.x  # frente contra frente
            if gap <= 0:
                continue  # ya se cruzaron
            closing = veh.v + other.v
            if gap < closing * self.t_emergency + self.d_emergency:
                veh.emergency_steps += 1
                return min(a, -self.b_emergency)
        return a

    def _count_collisions(self, groups: dict[tuple[int, int], list[Vehicle]]) -> None:
        for (lane, direction), lst in groups.items():
            for lead, veh in zip(lst, lst[1:]):
                if veh.x > lead.rear:
                    self.collisions += 1
            if direction != 1:
                continue
            for veh in lst:  # choque frontal con vehículos contrarios del mismo carril
                for other in groups.get((lane, -1), ()):
                    o_front = self.front_in_opposite_frame(other)
                    if veh.x > o_front and veh.rear < o_front + other.length:
                        self.collisions += 1

    def _remove_finished(self) -> None:
        if not any(v.x >= self.length for v in self.vehicles):
            return
        keep = []
        for veh in self.vehicles:
            if veh.x >= self.length:
                veh.t_exit = self.t
                self.finished.append(veh)
                sampler = self._replacers.get(veh.direction)
                if sampler is not None and not veh.probe:
                    v0, kind = sampler.sample()
                    self.inject(v0, veh.direction, kind=kind)
            else:
                keep.append(veh)
        self.vehicles = keep

    @property
    def pending(self) -> int:
        """Vehículos esperando para entrar."""
        return sum(len(q) for q in self._pending.values())

    @property
    def sources_exhausted(self) -> bool:
        """True si ninguna fuente generará más llegadas."""
        return all(s.exhausted for s in self._sources.values())

    def run(self, seconds: float) -> None:
        """Corre `seconds` segundos simulados."""
        for _ in range(math.ceil(seconds / self.dt - 1e-9)):
            self.step()


def _fusionar(accels):
    """Un vehículo que cambia de carril aparece en dos grupos: se queda con la aceleración
    más restrictiva (frena por lo que tenga delante en cualquiera de los dos carriles)."""
    vistos: dict[int, int] = {}
    out = []
    for veh, a, cerca in accels:
        k = id(veh)
        if k in vistos:
            i = vistos[k]
            v0, a0, c0 = out[i]
            out[i] = (v0, min(a0, a), c0 or cerca)
        else:
            vistos[k] = len(out)
            out.append((veh, a, cerca))
    return out
