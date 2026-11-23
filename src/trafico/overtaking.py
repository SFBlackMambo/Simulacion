"""Rebase: criterio de hueco seguro y máquina de estados.

Estados de un vehículo: SIGUIENDO -> REBASANDO (en el carril contrario) ->
REGRESANDO (ya adelantó, espera un hueco) -> SIGUIENDO. También puede abortar
y regresar detrás de lo que iba a rebasar si aparece un vehículo de frente.
El cambio de carril es instantáneo.
"""

from dataclasses import dataclass
from math import inf

from .recorder import REBASE_ABORTO, REBASE_FIN, REBASE_INICIO
from .vehicle import REBASANDO, REGRESANDO, SIGUIENDO, Vehicle


@dataclass(frozen=True)
class OvertakeParams:
    """Parámetros del rebase (SI)."""

    dv_min: float = 2.0  # el líder debe ir al menos esto por debajo de v0, m/s
    trigger_gap: float = 100.0  # distancia al líder a partir de la cual se considera rebasar, m
    decision_interval: float = 1.0  # cada cuánto decide un conductor, s
    t_guard: float = 6.0  # el contrario debe llegar al menos esto después de terminar el rebase, s
    d_margin: float = 30.0  # distancia libre frente a frente adicional, m
    t_margin: float = 2.0  # tiempo extra de seguridad para el rebase, s
    m_back: float = 20.0  # distancia libre detrás del vehículo al regresar, m
    m_front: float = 20.0  # distancia libre delante del vehículo al regresar, m
    max_chain: int = 4  # máximo de vehículos que se rebasan de una vez
    t_max: float = 60.0  # un rebase que tarde más que esto no se intenta, s
    v_entry: float = 40.0  # velocidad supuesta de un vehículo que aún no entra, m/s
    t_threat: float = 4.0  # tiempo a choque frontal que hace abortar el rebase, s
    d_threat: float = 30.0  # distancia frente a frente que hace abortar el rebase, m
    window_back: float = 300.0  # no rebasar si otro del mismo sentido rebasa en esta zona, m
    window_front: float = 600.0


def _free_speed(v: float, v0: float, idm, step: float) -> float:
    """Velocidad tras `step` s de aceleración en vía libre (misma curva que el IDM)."""
    return v + idm.a_max * (1.0 - (v / v0) ** idm.delta) * step


def _time_to_clear(veh: Vehicle, other: Vehicle, p: OvertakeParams, idm) -> float:
    """Tiempo para que `veh` deje a `other` atrás con holgura (inf si no lo logra)."""
    dist = other.x + p.m_back + veh.length - veh.x
    v, rel, t, step = veh.v, 0.0, 0.0, 0.5
    while rel < dist:
        v = _free_speed(v, veh.v0, idm, step)
        t += step
        v_other = min(other.v0, other.v + idm.a_max * t)  # cota: `other` podría acelerar
        rel += (v - v_other) * step
        if t > p.t_max:
            return inf
    return t


def _distance(v: float, v_max: float, T: float, a_max: float, idm=None) -> float:
    """Distancia recorrida en `T` s partiendo de `v` y acelerando hacia `v_max`.

    Con `idm` sigue la curva de aceleración en vía libre; sin él acelera a `a_max`
    constante (cota superior, para vehículos contrarios).
    """
    x, t = 0.0, 0.0
    while t < T:
        step = min(0.5, T - t)
        v_new = min(v_max, v + a_max * step) if idm is None else _free_speed(v, v_max, idm, step)
        x += 0.5 * (v + v_new) * step
        v, t = v_new, t + step
    return x


def _is_safe(road, p: OvertakeParams, veh: Vehicle, chain: list[Vehicle]) -> bool:
    idm = road.idm
    a_max = idm.a_max
    t_pass = 0.0
    for other in chain:
        t = _time_to_clear(veh, other, p, idm)
        if t == inf:
            return False
        t_pass = max(t_pass, t)
    T = t_pass + p.t_margin
    x_end = veh.x + _distance(veh.v, veh.v0, T, a_max, idm) + p.d_margin
    T_guard = T + p.t_guard
    target = 1 - veh.lane
    for u in road.vehicles:
        if u is veh:
            continue
        if u.direction == veh.direction:
            if u.lane == target and veh.x - p.window_back < u.x < veh.x + p.window_front:
                return False
        else:
            front = road.front_in_opposite_frame(u)
            if front + u.length < veh.rear:
                continue  # ya se cruzó con `veh`
            # el contrario podría acelerar hasta su v0: se toma la cota más pesimista
            if front - _distance(u.v, u.v0, T_guard, a_max) <= x_end:
                return False
    return road.length - p.v_entry * T_guard > x_end  # podría entrar uno por el otro extremo


def _start(road, p: OvertakeParams, veh: Vehicle, lst: list[Vehicle], i: int) -> bool:
    leader = lst[i - 1]
    if leader.rear - veh.x > p.trigger_gap or leader.v + p.dv_min > veh.v_des:
        return False
    need = veh.length + p.m_back + p.m_front
    chain = [leader]
    j = i - 1
    while j > 0 and lst[j - 1].rear - lst[j].x < need:
        chain.append(lst[j - 1])
        j -= 1
        if len(chain) > p.max_chain:
            return False
    if not _is_safe(road, p, veh, chain):
        return False
    veh.lane = 1 - veh.lane
    veh.state = REBASANDO
    veh.targets = chain
    road.event(REBASE_INICIO, veh, len(chain))
    return True


def _threat(road, p: OvertakeParams, veh: Vehicle) -> bool:
    for u in road.vehicles:
        if u.direction != veh.direction and u.lane == veh.lane:
            gap = road.front_in_opposite_frame(u) - veh.x
            if gap > 0 and gap < (veh.v + u.v) * p.t_threat + p.d_threat:
                return True
    return False


def _try_return(road, p: OvertakeParams, veh: Vehicle, groups) -> bool:
    if veh.state == REBASANDO:
        if all(veh.rear >= t.x + p.m_back for t in veh.targets):
            veh.state = REGRESANDO
        elif not _threat(road, p, veh):
            return False
    home = veh.home_lane
    ahead = behind = inf
    for u in groups.get((home, veh.direction), ()):
        if u.x > veh.x:
            ahead = min(ahead, u.rear - veh.x)
        else:
            behind = min(behind, veh.rear - u.x)
    if ahead < p.m_front or behind < p.m_back:
        return False
    if veh.state == REGRESANDO:
        veh.overtakes += len(veh.targets)
        for t in veh.targets:
            t.overtaken += 1
        road.event(REBASE_FIN, veh, len(veh.targets))
    else:
        veh.aborts += 1
        road.event(REBASE_ABORTO, veh, len(veh.targets))
    veh.lane = home
    veh.state = SIGUIENDO
    veh.targets = []
    return True


def update(road, groups) -> bool:
    """Decide inicios y regresos de rebase. Devuelve True si algún vehículo cambió de carril."""
    p = road.overtaking
    interval = max(1, round(p.decision_interval / road.dt))
    changed = False
    for lst in list(groups.values()):
        for i, veh in enumerate(lst):
            if veh.state == SIGUIENDO:
                if i > 0 and (road.n_steps + veh.id) % interval == 0:
                    changed |= _start(road, p, veh, lst, i)
            else:
                changed |= _try_return(road, p, veh, groups)
    return changed
