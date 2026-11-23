"""Pendientes: física de subida y bajada para cada vehículo.

Calibrado con datos (ver README, sección de pendientes):
- NCHRP Report 505 (TRB, 2003): relación peso/potencia de camiones en carreteras de dos
  carriles (mediana ~107-186 lb/hp, P85 180-280) y velocidades medidas en subidas.
- FHWA-RD-99-171 (TWOPAS): ecuaciones de desempeño de camiones y autos en pendiente.
- SCT, Manual de Proyecto Geométrico de Carreteras (2018): vehículo de proyecto T3-S2-R4 de
  75.5 t y 430 hp (~4.3 W/kg); "en bajadas los camiones aumentan su velocidad hasta un 5 %";
  hasta 5 % de pendiente los autos no pierden velocidad apreciable.
- St John (NCHRP 185) vía Bester y Oncke (2013): en bajadas largas de más de 4 % los camiones
  pesados bajan a V ≈ 0.9 / G m/s.

Modelo:
- Subida y llano (solo en carreteras con relieve): la aceleración no puede superar lo que da el
  motor: P/v − g·(i + c_r) − k·v², con P la potencia específica en la rueda (W/kg) y k el
  arrastre aerodinámico por kg (½·ρ·CdA/m). El vehículo pierde velocidad poco a poco; no frena.
- Bajada: la gravedad empuja (g·|i|); el conductor se deja llevar hasta `tolerance` por encima
  de su velocidad deseada (proporcional a la pendiente, completa a partir de 5 %).
- Freno de motor: los camiones pesados (poca potencia por kg) en bajadas fuertes y largas no
  pasan de 0.9 / G m/s (mínimo 40 km/h) y se preparan antes de empezar a bajar.
"""

import math
from dataclasses import dataclass

G = 9.81
C_RODADURA = 0.01
RHO = 1.2  # densidad del aire, kg/m³


@dataclass(frozen=True)
class GradeResponse:
    """Cómo responde un vehículo a las pendientes."""

    power_w_kg: float = 22.0  # potencia específica en la rueda
    k_aero: float = 0.5 * RHO * 0.7 / 1400.0  # ½·ρ·CdA/m, 1/m (auto de 1400 kg, CdA 0.7 m²)
    tolerance: float = 0.10  # en bajada se deja llevar hasta este % por encima de su velocidad deseada
    engine_brake: bool = False  # camión pesado: freno de motor en bajadas fuertes y largas
    steep: float = 0.04  # bajada "fuerte" (fracción)
    long_descent_m: float = 2000.0  # bajada "larga"
    st_john: float = 0.9  # V = st_john / G (m/s) en bajadas fuertes y largas
    v_min_descent_kmh: float = 40.0


AUTO_GRADES = GradeResponse()
K_AERO_CAMION = 0.5 * RHO * 6.0 / 30000.0  # camión cargado de 30 t con CdA de 6 m²


def uphill_speed(r: GradeResponse, grade: float) -> float:
    """Velocidad que el motor puede sostener en una pendiente (m/s), resolviendo P/v = g(i+c_r) + k v²."""
    resist = G * (grade + C_RODADURA)
    if resist <= 0 and r.k_aero <= 0:
        return math.inf
    lo, hi = 0.1, 100.0
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if r.power_w_kg / mid - max(resist, 0.0) - r.k_aero * mid * mid > 0:
            lo = mid
        else:
            hi = mid
    return lo


def accel_limit(r: GradeResponse, v: float, grade: float) -> float:
    """Aceleración máxima que da el motor (m/s²) en una pendiente `grade` a velocidad `v`."""
    return r.power_w_kg / max(v, 1.0) - G * (grade + C_RODADURA) - r.k_aero * v * v


def downhill_factor(r: GradeResponse, grade: float) -> float:
    """En bajada, cuánto por encima de su velocidad deseada se deja llevar el conductor (×)."""
    if grade >= 0:
        return 1.0
    return 1.0 + r.tolerance * min(1.0, -grade / 0.05)


def engine_brake_speed(r: GradeResponse, grade: float) -> float:
    """Velocidad máxima con freno de motor en una bajada fuerte y larga (m/s)."""
    return max(r.v_min_descent_kmh / 3.6, r.st_john / max(-grade, 1e-6))


def truck_response(lb_hp: float, eficiencia: float = 0.87) -> GradeResponse:
    """Respuesta de un camión con relación peso/potencia `lb_hp` (potencia neta del motor)."""
    w_kg = 1644.0 / lb_hp * eficiencia  # 1 hp/lb = 1644 W/kg; a la rueda llega el 87 %
    w_kg = round(w_kg * 2) / 2  # al 0.5 W/kg: pocas tablas distintas
    return GradeResponse(power_w_kg=w_kg, k_aero=K_AERO_CAMION, tolerance=0.05, engine_brake=w_kg < 6.0)
