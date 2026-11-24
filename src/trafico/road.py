"""Carretera: simulación por pasos de tiempo."""

import dataclasses
import math
from collections import deque

import numpy as np
from operator import attrgetter

from .arrivals import PoissonArrivals
from . import overtaking
from .fleet import AUTO, CAMION, LARGO_AUTO, TruckParams
from .fuel import AUTO_FUEL, litros_por_s, truck_fuel
from .geometry import curve_accel
from .slopes import AUTO_GRADES, accel_limit
from .idm import IDMParams, advance, hdm_acceleration, idm_acceleration
from .overtaking import OvertakeParams
from .vehicle import REBASANDO, Vehicle

_POR_X = attrgetter("x")
N_ANTICIPA = 3  # con tiempo de reacción, cuántos vehículos de delante se miran


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
        truck_seed=None,
        drivers=None,
        driver_seed=None,
        reaction_time: float = 0.0,
        b_physical: float = 0.0,
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
        self._truck_rng = np.random.default_rng(truck_seed) if truck_seed is not None else None
        self.drivers = drivers if drivers is not None and drivers.active else None
        self._driver_rng = np.random.default_rng(driver_seed) if self.drivers is not None else None
        self._idm_cache: dict = {}
        # tiempo de reacción: la aceleración se aplica con `n` pasos de retraso
        self.reaction_steps = int(round(reaction_time / dt)) if reaction_time > 0 else 0
        self.b_physical = b_physical  # tope de frenado, m/s² (0 = sin tope, como en las fases 1 y 2)
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
            kw["grades"] = t.response(self._truck_rng)
            kw["fuel"] = _fuel_camion(kw["grades"].power_w_kg)
        veh = Vehicle(self._next_id, v0, direction=direction, probe=probe, kind=kind, **kw)
        self._next_id += 1
        if self.drivers is not None and not probe:  # las sondas son conductores normales
            self.drivers.assign(veh, self._driver_rng)
            f = self.drivers.T_factor(veh)
            if f != 1.0:
                base = veh.idm or self.idm
                clave = (base, f)
                if clave not in self._idm_cache:
                    self._idm_cache[clave] = dataclasses.replace(base, T=base.T * f)
                veh.idm = self._idm_cache[clave]
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
        v_max = veh.v0
        if self.geometry is not None:
            v_max = min(v_max, self.geometry.limit(veh.direction, 0.0))
            if self.geometry.limits:
                v_max = min(v_max, self.geometry.speed_limit(veh.direction, 0.0) * veh.limit_factor)
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

    def event(self, kind: str, veh: Vehicle, n: int = 0, cadena: bool = False) -> None:
        """Avisa de un evento al registro, si hay."""
        if self.recorder is not None:
            self.recorder.event(self, kind, veh, n, cadena)

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
        accels: list[tuple] = []
        for (lane, direction), lst in groups.items():
            opposite = groups.get((lane, -direction))
            pend_dir = geo.grade_list(direction) if geo is not None and geo.grades else None
            leader = None
            for i_veh, veh in enumerate(lst):
                if (leader is not None and veh.lc < 1.0 and lane == veh.lane_prev and veh.state == REBASANDO
                        and leader.rear - veh.x > (veh.idm or idm).s0 + veh.v):
                    leader = None  # saliendo a rebasar: el de delante ya no le estorba (salvo muy cerca)
                v0 = veh.v0
                g = 0.0
                g_activo = False
                if geo is not None:
                    tabla = veh.vlim
                    if tabla is None:
                        tabla = veh.vlim = geo.vlim_list(direction, veh.grades, veh.limit_factor)
                    k = int(veh.x / geo.grid)
                    k = 0 if k < 0 else (len(tabla) - 1 if k >= len(tabla) else k)
                    if pend_dir is not None:
                        g = veh.g_now = pend_dir[k]
                        mult = veh.mult
                        if mult is None:
                            mult = veh.mult = geo.mult_list(direction, veh.grades)
                        v0 = v0 * mult[k]  # en bajada se deja llevar
                        g_activo = True
                    else:
                        g_activo = False
                    v0 = min(v0, tabla[k])
                    veh.v_des = v0
                p_idm = veh.idm or idm
                if leader is None:
                    a = idm_acceleration(veh.v, v0, None, None, p_idm)
                elif self.reaction_steps:
                    # Con tiempo de reacción el conductor se anticipa (Human Driver Model, Treiber 2006):
                    # estima huecos y su velocidad para cuando su acción haga efecto, y mira a varios
                    # de delante (multi-anticipación), lo que evita que los pelotones oscilen.
                    tau = self.reaction_steps * dt
                    v_est = max(0.0, veh.v + tau * veh.a_prev)
                    lideres = []
                    for j in range(1, N_ANTICIPA + 1):
                        if i_veh - j < 0:
                            break
                        u = lst[i_veh - j]
                        gap = u.rear - veh.x
                        lideres.append((max(0.1, gap - tau * (veh.v - u.v)), u.v))
                    a = hdm_acceleration(v_est, v0, lideres, p_idm)
                else:
                    a = idm_acceleration(veh.v, v0, leader.rear - veh.x, leader.v, p_idm)
                if geo is not None:
                    a = curve_accel(a, veh.v, v0)
                if g_activo or veh.grades is not None:  # el motor no da para más (pendiente, aire)
                    a = min(a, accel_limit(veh.grades or AUTO_GRADES, veh.v, g))
                a_seguir = a
                a_frontal = self._head_on_brake(veh, opposite, math.inf) if opposite else math.inf
                # medidas (solo se registran): headway, TTC con el de delante y frente a frente
                if leader is not None:
                    if veh.v > 0.1:
                        hw = (leader.x - veh.x) / veh.v
                        if hw < veh.m_hw:
                            veh.m_hw = hw
                    dv = veh.v - leader.v
                    if dv > 0:
                        ttc = (leader.rear - veh.x) / dv
                        if ttc < veh.m_ttcl:
                            veh.m_ttcl = ttc
                if opposite:
                    for other in opposite:  # ordenados: el primero que no se cruzó es el más cercano
                        gap = self.length - other.x - veh.x
                        if gap > 0:
                            ttc = gap / max(veh.v + other.v, 0.1)
                            if ttc < veh.m_ttco:
                                veh.m_ttco = ttc
                            break
                a = min(a_seguir, a_frontal)
                # ¿lo frena alguien? (líder a menos de 4 s o de 50 m)
                cerca = leader is not None and leader.rear - veh.x < max(50.0, 4.0 * veh.v)
                critico = False
                if self.reaction_steps and leader is not None:  # susto: reacciona sin demora
                    gap = leader.rear - veh.x
                    dv = veh.v - leader.v
                    critico = gap < p_idm.s0 + 0.5 * veh.v or (dv > 0 and gap / dv < 2.0)
                accels.append((veh, a, cerca, a_seguir, a_frontal, critico))
                leader = veh
        if any(v.lc < 1.0 for v in self.vehicles):
            accels = _fusionar(accels)
        t_lc = self.overtaking.t_lane_change if self.overtaking is not None else 0.0
        n_r = self.reaction_steps
        for veh, a, cerca, a_seguir, a_frontal, critico in accels:
            if n_r:
                buf = veh.a_buf
                if buf is None:
                    buf = veh.a_buf = deque()
                buf.append(a_seguir)
                a_dem = buf.popleft() if len(buf) > n_r else a_seguir
                a = min(a_seguir if critico else a_dem, a_frontal)  # el frenado frontal es inmediato
            veh.a_prev = a
            if self.b_physical and a < -self.b_physical:
                a = -self.b_physical  # un vehículo real no frena más que esto
            advance(veh, a, dt)
            veh.fuel_l += litros_por_s(veh.fuel or AUTO_FUEL, veh.v, a, veh.g_now) * dt  # solo se registra
            if veh.lc < 1.0:
                veh.lc = min(1.0, veh.lc + dt / t_lc) if t_lc > 0 else 1.0
            if veh.v < veh.v_des - 1.0:
                veh.t_slow += dt
                if not veh.slowed and cerca:
                    veh.slowed = True
                    veh.catchups += 1
            elif veh.slowed and veh.v > veh.v_des - 0.3:
                veh.slowed = False
            veh.t_stuck = veh.t_stuck + dt if veh.slowed else 0.0
            _medir(veh, dt)
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


_FUEL_CAMION: dict = {}


def _fuel_camion(w_kg: float):
    """Consumo de un camión según su potencia en la rueda (caché: hay pocas distintas)."""
    f = _FUEL_CAMION.get(w_kg)
    if f is None:
        f = _FUEL_CAMION[w_kg] = truck_fuel(1644.0 * 0.87 / w_kg)
    return f


TTC_CONFLICTO = 1.5  # s, umbral de conflicto (SSAM, Gettman y Head 2003)


def _medir(veh: Vehicle, dt: float) -> None:
    """Acumula las medidas del paso (no cambian la dinámica) y las reinicia."""
    hw = veh.m_hw
    if hw <= 2.5:
        veh.t_hw25 += dt
    if hw < 3.0:
        veh.t_hw3 += dt
    if veh.lane != veh.home_lane:
        veh.t_opposite += dt
    t = veh.m_ttcl
    if t < TTC_CONFLICTO <= veh.ttcl_prev:  # empieza un episodio
        veh.conflicts_leader += 1
    veh.ttcl_prev = t
    if t < veh.ttc_leader_min:
        veh.ttc_leader_min = t
    t = veh.m_ttco
    if t < TTC_CONFLICTO <= veh.ttco_prev:
        veh.conflicts_opp += 1
    veh.ttco_prev = t
    if t < veh.ttc_opp_min:
        veh.ttc_opp_min = t
    veh.m_hw = veh.m_ttcl = veh.m_ttco = math.inf


def _fusionar(accels):
    """Un vehículo que cambia de carril aparece en dos grupos: se queda con la aceleración
    más restrictiva (frena por lo que tenga delante en cualquiera de los dos carriles)."""
    vistos: dict[int, int] = {}
    out = []
    for veh, a, cerca, a_s, a_f, crit in accels:
        k = id(veh)
        if k in vistos:
            i = vistos[k]
            v0, a0, c0, s0, f0, k0 = out[i]
            out[i] = (v0, min(a0, a), c0 or cerca, min(s0, a_s), min(f0, a_f), k0 or crit)
        else:
            vistos[k] = len(out)
            out.append((veh, a, cerca, a_s, a_f, crit))
    return out
