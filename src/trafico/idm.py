"""Modelo de seguimiento IDM (Intelligent Driver Model, Treiber et al. 2000)."""

import math
from dataclasses import dataclass

from .vehicle import Vehicle


@dataclass(frozen=True)
class IDMParams:
    """Parámetros del IDM (SI)."""

    a_max: float = 1.0  # aceleración máxima, m/s²
    b: float = 1.5  # deceleración cómoda, m/s²
    T: float = 1.5  # intervalo de tiempo deseado al líder, s
    s0: float = 2.0  # distancia mínima de parada, m
    delta: float = 4.0  # exponente de aceleración


def idm_acceleration(
    v: float,
    v0: float,
    gap: float | None,
    v_leader: float | None,
    p: IDMParams = IDMParams(),
) -> float:
    """Aceleración del IDM.

    `gap` y `v_leader` son None si no hay líder (vía libre).
    """
    libre = 1.0 - (v / v0) ** p.delta
    if gap is None or v_leader is None:
        return p.a_max * libre
    gap = max(gap, 1e-6)
    s_deseada = p.s0 + max(0.0, v * p.T + v * (v - v_leader) / (2.0 * math.sqrt(p.a_max * p.b)))
    return p.a_max * (libre - (s_deseada / gap) ** 2)


def step(
    vehicle: Vehicle,
    leader: Vehicle | None,
    dt: float,
    p: IDMParams = IDMParams(),
) -> None:
    """Avanza un vehículo un paso de tiempo `dt` (integración balística).

    El estado del líder debe ser el del inicio del paso.
    """
    if leader is None:
        a = idm_acceleration(vehicle.v, vehicle.v0, None, None, p)
    else:
        a = idm_acceleration(vehicle.v, vehicle.v0, vehicle.gap_to(leader), leader.v, p)
    advance(vehicle, a, dt)


B_FISICO = 9.0  # m/s²: lo máximo que frena un vehículo real


def advance(vehicle: Vehicle, a: float, dt: float) -> None:
    """Integra el movimiento con aceleración `a` durante `dt` (balística)."""
    v_nueva = max(0.0, vehicle.v + a * dt)
    vehicle.x += 0.5 * (vehicle.v + v_nueva) * dt
    vehicle.v = v_nueva


def hdm_acceleration(v: float, v0: float, leaders: list[tuple[float, float]], p: IDMParams = IDMParams()) -> float:
    """IDM con multi-anticipación (Human Driver Model, Treiber et al. 2006).

    `leaders` = [(hueco hasta el j-ésimo de delante, su velocidad), ...], del más
    cercano al más lejano. Cada interacción pesa 1/j² y se normaliza para que en
    equilibrio el hueco con el primero sea el mismo que con el IDM normal.
    """
    libre = 1.0 - (v / v0) ** p.delta
    if not leaders:
        return p.a_max * libre
    c = 1.0 / sum(1.0 / (j * j) for j in range(1, len(leaders) + 1))
    raiz = 2.0 * math.sqrt(p.a_max * p.b)
    inter = 0.0
    for j, (gap, v_l) in enumerate(leaders, start=1):
        s_des = p.s0 + max(0.0, v * p.T + v * (v - v_l) / raiz)
        # el j-ésimo está ~j huecos más allá: s* se escala con j
        inter += c * (j * s_des / max(gap, 1e-6)) ** 2 / (j * j)
    return p.a_max * (libre - inter)
