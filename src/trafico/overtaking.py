"""Rebase: criterio de hueco seguro y máquina de estados.

Estados de un vehículo: SIGUIENDO -> REBASANDO (en el carril contrario) ->
REGRESANDO (ya adelantó, espera un hueco) -> SIGUIENDO. También puede abortar
y regresar detrás de lo que iba a rebasar si aparece un vehículo de frente.
El cambio de carril es instantáneo.
"""

from dataclasses import dataclass
from math import inf

from .recorder import REBASE_ABORTO, REBASE_FIN, REBASE_INICIO
from .slopes import AUTO_GRADES, accel_limit, uphill_speed
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
    v_unseen: float = 30.0  # velocidad supuesta de un vehículo que no se ve (tras una curva), m/s
    t_guard_unseen: float = 2.0  # margen frente a ese vehículo supuesto, s
    t_lane_change: float = 0.0  # duración de cada cambio de carril, s (0 = instantáneo)
    convoy: bool = False  # se puede seguir a otro que ya rebasa (varios a la vez)
    blocked_view: bool = False  # el vehículo de delante tapa la vista del carril contrario
    truck_block_headway: float = 3.0  # detrás de un camión a menos de esto (s) no se ve nada
    car_block_headway: float = 2.0  # detrás de un auto a menos de esto (s) se ve poco
    sight_behind_car: float = 500.0  # cuánto se ve detrás de un auto cercano, m
    no_start_braking: bool = False  # no empezar si uno mismo o alguno a rebasar frena fuerte
    return_closing: bool = False  # al volver, el hueco debe cubrir también la diferencia de velocidad
    b_return: float = 3.0  # frenado firme supuesto al volver, m/s²
    braking_threshold: float = -1.0  # m/s²: "frenar fuerte"
    window_back: float = 300.0  # no rebasar si otro del mismo sentido rebasa en esta zona, m
    window_front: float = 600.0


def _free_speed(v: float, v0: float, idm, step: float) -> float:
    """Velocidad tras `step` s de aceleración en vía libre (misma curva que el IDM)."""
    return v + idm.a_max * (1.0 - (v / v0) ** idm.delta) * step


def _tabla(road, veh: Vehicle):
    """Velocidad permitida por celda para este vehículo (curvas, pendientes, límites); None si es recta."""
    geo = road.geometry
    if geo is None:
        return None
    t = veh.vlim
    if t is None:  # los rasgos del vehículo no cambian: se busca una sola vez
        t = veh.vlim = geo.vlim_list(veh.direction, veh.grades, veh.limit_factor)
    return t


def _limite(road, veh: Vehicle, x: float) -> float:
    """Velocidad permitida por el trazado (curvas y pendientes) en la posición propia `x`."""
    tabla = _tabla(road, veh)
    if tabla is None:
        return inf
    k = int(x / road.geometry.grid)
    return tabla[0 if k < 0 else (len(tabla) - 1 if k >= len(tabla) else k)]


def _time_to_clear(road, veh: Vehicle, other: Vehicle, p: OvertakeParams, idm, v_cap: float = inf) -> float:
    """Tiempo para que `veh` deje a `other` atrás con holgura (inf si no lo logra).

    El que rebasa no puede ir más rápido de lo que permite el trazado; para el
    rebasado se toma la cota pesimista de que acelera (y no frena en las curvas).
    """
    dist = other.x + p.m_back + veh.length - veh.x
    v, rel, t, step, x = veh.v, 0.0, 0.0, 0.5, veh.x
    tabla = _tabla(road, veh)
    grid = road.geometry.grid if tabla is not None else 1.0
    n = len(tabla) - 1 if tabla is not None else 0
    a_max, delta, v0 = idm.a_max, idm.delta, veh.v0
    a_other = (other.idm or road.idm).a_max
    pend = road.geometry.grade_list(veh.direction) if tabla is not None and road.geometry.grades else None
    resp = veh.grades or AUTO_GRADES
    fisica = pend is not None or veh.grades is not None  # camiones: el motor limita también en llano
    while rel < dist:
        if tabla is None:
            lim = v_cap
        else:
            k = int(x / grid)
            k = 0 if k < 0 else (n if k > n else k)
            lim = min(tabla[k], v_cap)
        if tabla is None:
            k = 0
        v_new = min(v + a_max * (1.0 - (v / v0) ** delta) * step, max(lim, v - 3.0 * step))
        if fisica:  # el motor (pendiente y aire) limita la aceleración
            g = pend[k] if pend is not None else 0.0
            v_new = min(v_new, max(0.0, v + accel_limit(resp, v, g) * step))
        x += 0.5 * (v + v_new) * step
        v = v_new
        t += step
        v_other = min(other.v0, other.v + a_other * t)  # cota: `other` podría acelerar
        rel += (v - v_other) * step
        if t > p.t_max:
            return inf
    return t


def _distance(v: float, v_max: float, T: float, a_max: float, idm=None, road=None, veh=None,
              v_cap: float = inf) -> float:
    """Distancia recorrida en `T` s partiendo de `v` y acelerando hacia `v_max`.

    Con `idm` sigue la curva de aceleración en vía libre (y, con `road`, los
    límites del trazado); sin él acelera a `a_max` constante (cota superior, para
    vehículos contrarios).
    """
    x, t = 0.0, 0.0
    while t < T:
        step = min(0.5, T - t)
        if idm is None:
            v_new = min(v_max, v + a_max * step)
        else:
            v_new = _free_speed(v, v_max, idm, step)
            if road is not None and (road.geometry is not None or v_cap < inf):
                v_new = min(v_new, max(min(_limite(road, veh, veh.x + x), v_cap), v - 3.0 * step))
        x += 0.5 * (v + v_new) * step
        v, t = v_new, t + step
    return x


def _visible(road, p: OvertakeParams, veh: Vehicle, leader: Vehicle, delante: list) -> float:
    """Cuánto ve `veh` del carril contrario (m), según el trazado y quién le tapa la vista."""
    vis = inf if road.geometry is None else road.geometry.sight(veh.direction, veh.x)
    if not p.blocked_view:
        return vis
    v = max(veh.v, 1.0)
    for b in [leader, *delante]:
        hw = (b.rear - veh.x) / v
        if b.kind == "camion" and hw < p.truck_block_headway:
            return 0.0
        if hw < p.car_block_headway:
            vis = min(vis, p.sight_behind_car)
    return vis


def _is_safe(road, p: OvertakeParams, veh: Vehicle, chain: list[Vehicle]) -> bool:
    idm = veh.idm or road.idm  # dinámica del que rebasa (un camión acelera menos)
    a_max = road.idm.a_max  # cota de aceleración de los contrarios
    target = 1 - veh.lane
    # ¿hay otros del mismo sentido en el carril contrario cerca?
    delante = []
    for u in road.vehicles:
        if u is veh or u.direction != veh.direction or not u.occupies(target):
            continue
        if veh.x - p.window_back < u.x < veh.x + p.window_front:
            if not p.convoy or u.x <= veh.x or u.state == SIGUIENDO:
                return False  # uno detrás, o uno que vuelve: no se arriesga
            # va rebasando delante: se le puede seguir, pero a distancia segura
            p_idm = veh.idm or road.idm
            hueco = u.rear - veh.x
            frenar = max(0.0, veh.v - u.v) ** 2 / (2.0 * p_idm.b)
            if hueco < p_idm.s0 + 0.5 * p_idm.T * veh.v + frenar:
                return False
            delante.append(u)
    veh.convoy_start = bool(delante)
    # Descarte rápido (mismo resultado, sin las cuentas caras): si no ve lo suficiente ni para
    # el rebase más corto posible, no hay nada que calcular.
    vis = _visible(road, p, veh, chain[0], delante)
    f_guard = road.drivers.guard_factor(veh) if road.drivers is not None else 1.0
    if vis < inf:
        t_min = p.t_margin + p.t_lane_change + road.reaction_steps * road.dt
        if vis - p.v_unseen * (t_min + p.t_guard_unseen * f_guard) <= p.d_margin:
            return False
    v_cap = min((u.v_des for u in delante), default=inf)  # no irá más rápido que el de delante
    t_pass = 0.0
    for other in chain:
        t = _time_to_clear(road, veh, other, p, idm, v_cap)
        if t == inf:
            return False
        t_pass = max(t_pass, t)
    # hasta volver del todo al carril propio (con tiempo de reacción, todo empieza un poco tarde)
    T = t_pass + p.t_margin + p.t_lane_change + road.reaction_steps * road.dt
    x_end = veh.x + _distance(veh.v, veh.v0, T, a_max, idm, road, veh, v_cap) + p.d_margin
    T_guard = T + p.t_guard * f_guard
    for u in road.vehicles:
        if u is veh or u.direction == veh.direction:
            continue
        front = road.front_in_opposite_frame(u)
        if front + u.length < veh.rear:
            continue  # ya se cruzó con `veh`
        # el contrario podría acelerar hasta su v0: se toma la cota más pesimista
        if front - _distance(u.v, u.v0, T_guard, a_max) <= x_end:
            return False
    if road.length - p.v_entry * T_guard <= x_end:
        return False  # podría entrar uno por el otro extremo
    geo = road.geometry
    if geo is not None and veh.respects_no_pass and geo.no_pass_between(veh.direction, veh.x, x_end):
        return False  # la maniobra invadiría una zona de no rebase señalizada
    if vis < inf:
        # Lo que no se ve puede traer un vehículo de frente: se supone uno a `v_unseen`
        # justo donde acaba la visibilidad. Así solo se rebasa si la maniobra cabe en lo visible.
        if veh.x + vis - p.v_unseen * (T + p.t_guard_unseen * f_guard) <= x_end:
            return False
    return True


def _start(road, p: OvertakeParams, veh: Vehicle, lst: list[Vehicle], i: int) -> bool:
    if veh.lc < 1.0:
        return False  # aún termina un cambio de carril
    leader = lst[i - 1]
    dv_min = p.dv_min * (road.drivers.dv_factor(veh) if road.drivers is not None else 1.0)
    v_puede = veh.v_des
    if veh.grades is not None:  # un camión compara con lo que su motor puede sostener aquí
        geo = road.geometry
        g = geo.grade(veh.direction, veh.x) if geo is not None and geo.grades else 0.0
        v_puede = min(v_puede, uphill_speed(veh.grades, g))
    if leader.rear - veh.x > p.trigger_gap or leader.v + dv_min > v_puede:
        return False
    need = veh.length + p.m_back + p.m_front
    chain = [leader]
    j = i - 1
    while j > 0 and lst[j - 1].rear - lst[j].x < need:
        chain.append(lst[j - 1])
        j -= 1
        if len(chain) > p.max_chain:
            return False
    if p.t_lane_change > 0:
        # Hay que poder salir sin alcanzar al de delante mientras dura el cambio de carril.
        tl = p.t_lane_change
        acerca = max(0.0, veh.v - leader.v) * tl + 0.5 * (veh.idm or road.idm).a_max * tl * tl
        if leader.rear - veh.x < (veh.idm or road.idm).s0 + acerca:
            return False
    if p.no_start_braking and (veh.a_prev < p.braking_threshold
                               or any(u.a_prev < p.braking_threshold for u in chain)):
        return False  # el pelotón está frenando: no es momento de salir
    if not _is_safe(road, p, veh, chain):
        return False
    veh.change_lane(1 - veh.lane, p.t_lane_change)
    veh.state = REBASANDO
    veh.targets = chain
    road.event(REBASE_INICIO, veh, len(chain), cadena=veh.convoy_start)
    if veh.convoy_start:
        veh.convoy_overtakes += 1
    return True


def _threat(road, p: OvertakeParams, veh: Vehicle) -> bool:
    # con cambio de carril lento hay que reaccionar antes: volver también lleva tiempo
    t = p.t_threat + p.t_lane_change
    for u in road.vehicles:
        if u.direction != veh.direction and u.occupies(veh.lane):
            gap = road.front_in_opposite_frame(u) - veh.x
            if gap > 0 and gap < (veh.v + u.v) * t + p.d_threat:
                return True
    return False


def _try_return(road, p: OvertakeParams, veh: Vehicle, groups) -> bool:
    amenaza = None  # se calcula solo si hace falta
    if veh.state == REBASANDO:
        if all(veh.rear >= t.x + p.m_back for t in veh.targets):
            veh.state = REGRESANDO
        else:
            amenaza = _threat(road, p, veh)
            if not amenaza:
                return False
    home = veh.home_lane
    ahead = behind = inf
    for u in groups.get((home, veh.direction), ()):
        if u is veh:
            continue
        if u.x > veh.x:
            d = u.rear - veh.x
            if p.return_closing and veh.v > u.v:  # lo que necesita para frenar hasta su velocidad
                d -= (veh.v - u.v) ** 2 / (2.0 * p.b_return)
            ahead = min(ahead, d)
        else:
            d = veh.rear - u.x
            if p.return_closing and u.v > veh.v:  # el de atrás también tiene que poder frenar
                d -= (u.v - veh.v) ** 2 / (2.0 * p.b_return)
            behind = min(behind, d)
    m_front, m_back = p.m_front, p.m_back
    if p.t_lane_change > 0 and (ahead < m_front or behind < m_back):
        if amenaza is None:
            amenaza = _threat(road, p, veh)
        if amenaza:  # viene alguien de frente: se mete en un hueco más justo
            m_front, m_back = 0.5 * m_front, 0.5 * m_back
    if ahead < m_front or behind < m_back:
        return False
    if veh.state == REGRESANDO:
        veh.overtakes += len(veh.targets)
        for t in veh.targets:
            t.overtaken += 1
        road.event(REBASE_FIN, veh, len(veh.targets))
    else:
        veh.aborts += 1
        road.event(REBASE_ABORTO, veh, len(veh.targets))
    veh.change_lane(home, p.t_lane_change)
    veh.state = SIGUIENDO
    veh.targets = []
    return True


def update(road, groups) -> bool:
    """Decide inicios y regresos de rebase. Devuelve True si algún vehículo cambió de carril."""
    p = road.overtaking
    interval = max(1, round(p.decision_interval / road.dt))
    changed = False
    for (lane, _d), lst in list(groups.items()):
        for i, veh in enumerate(lst):
            if veh.lane != lane:
                continue  # está en este grupo solo porque cambia de carril
            if veh.state == SIGUIENDO:
                if i > 0 and (road.n_steps + veh.id) % interval == 0:
                    changed |= _start(road, p, veh, lst, i)
            else:
                changed |= _try_return(road, p, veh, groups)
    return changed
