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
    v_nueva = max(0.0, vehicle.v + a * dt)
    vehicle.x += 0.5 * (vehicle.v + v_nueva) * dt
    vehicle.v = v_nueva
