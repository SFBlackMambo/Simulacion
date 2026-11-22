"""Carretera: simulación por pasos de tiempo."""

import math
from collections import deque
from operator import attrgetter

from .arrivals import PoissonArrivals
from . import overtaking
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
    ) -> None:
        self.length = length
        self.dt = dt
        self.idm = idm
        self.t_emergency = t_emergency  # tiempo a colisión frontal que dispara el frenado
        self.b_emergency = b_emergency  # deceleración de emergencia, m/s²
        self.d_emergency = d_emergency  # distancia mínima frente a frente, m
        self.overtaking = overtaking  # None: nadie rebasa
        self.t = 0.0
        self.n_steps = 0
        self.vehicles: list[Vehicle] = []
        self.finished: list[Vehicle] = []
        self.collisions = 0
        self._pending: dict[int, deque[Vehicle]] = {1: deque(), -1: deque()}
        self._sources: dict[int, PoissonArrivals] = {}
        self._next_id = 0

    # ------------------------------------------------------------------
    # Creación de vehículos
    # ------------------------------------------------------------------
    def _nuevo(self, v0: float, direction: int, probe: bool, **kw) -> Vehicle:
        veh = Vehicle(self._next_id, v0, direction=direction, probe=probe, **kw)
        self._next_id += 1
        return veh

    def inject(self, v0: float, direction: int = 1, probe: bool = False) -> Vehicle:
        """Pone un vehículo en la cola de entrada de su sentido."""
        veh = self._nuevo(v0, direction, probe)
        self._pending[direction].append(veh)
        return veh

    def add_source(self, direction: int, source: PoissonArrivals) -> None:
        """Conecta una fuente de llegadas a la entrada de un sentido."""
        self._sources[direction] = source

    def place(
        self,
        v0: float,
        x: float,
        v: float | None = None,
        direction: int = 1,
        lane: int | None = None,
        probe: bool = False,
        length: float = 4.5,
    ) -> Vehicle:
        """Coloca un vehículo directamente en la carretera (escenarios y tests)."""
        veh = self._nuevo(v0, direction, probe, x=x, v=v0 if v is None else v, length=length)
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
            if u.lane != veh.lane:
                continue
            if u.direction == veh.direction:
                if last is None or u.x < last.x:
                    last = u
            elif self.front_in_opposite_frame(u) < 200.0 and self.front_in_opposite_frame(u) + u.length > 0:
                return None  # un rebasante contrario viene de frente por este carril
        if last is None:
            return veh.v0
        gap = last.rear  # el frente del que entra está en x = 0
        v_in = min(veh.v0, last.v) if gap < 200.0 else veh.v0
        if gap >= self.idm.s0 + v_in * self.idm.T:
            return v_in
        return None

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
        for lst in groups.values():
            lst.sort(key=_POR_X, reverse=True)
        return groups

    def step(self) -> None:
        """Avanza la simulación un paso `dt`."""
        for direction, source in self._sources.items():
            for v0 in source.due(self.t):
                self.inject(v0, direction)
        self._try_enter()
        groups = self._groups()
        if self.overtaking is not None and overtaking.update(self, groups):
            groups = self._groups()
        idm, dt = self.idm, self.dt
        accels: list[tuple[Vehicle, float]] = []
        for (lane, direction), lst in groups.items():
            opposite = groups.get((lane, -direction))
            leader = None
            for veh in lst:
                if leader is None:
                    a = idm_acceleration(veh.v, veh.v0, None, None, idm)
                else:
                    a = idm_acceleration(veh.v, veh.v0, leader.rear - veh.x, leader.v, idm)
                if opposite:
                    a = self._head_on_brake(veh, opposite, a)
                accels.append((veh, a))
                leader = veh
        for veh, a in accels:
            advance(veh, a, dt)
            if veh.v < veh.v0 - 1.0:
                veh.t_slow += dt
        self.t += dt
        self.n_steps += 1
        self._count_collisions(groups)
        self._remove_finished()

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
            else:
                keep.append(veh)
        self.vehicles = keep

    def run(self, seconds: float) -> None:
        """Corre `seconds` segundos simulados."""
        for _ in range(math.ceil(seconds / self.dt - 1e-9)):
            self.step()
