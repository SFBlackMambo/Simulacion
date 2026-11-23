"""Pendientes: cómo afectan la subida y la bajada a cada tipo de vehículo.

Subida (modelo de potencia): un vehículo con potencia específica P (W/kg) no
puede sostener más de v = P / (g·(i + c_r)) en una pendiente i (fracción, 0.06 =
6 %), con resistencia a la rodadura c_r. Tampoco puede acelerar más de
P/v − g·(i + c_r). Para un camión (7.5 W/kg): 3 % → ~69 km/h, 6 % → ~39 km/h,
8 % → ~31 km/h. Un auto (60 W/kg) casi no lo nota.

Bajada: los camiones bajan con freno de motor. Hasta `down_start_pct` no cambia
nada; a partir de ahí su velocidad máxima baja `down_kmh_per_pct` por cada punto
de pendiente desde `down_base_kmh` (sin bajar de `down_min_kmh`). Los autos no
cambian.

Solo se aplica donde hay pendiente: en terreno plano no cambia nada.
"""

import math
from dataclasses import dataclass

G = 9.81
C_RODADURA = 0.01


@dataclass(frozen=True)
class GradeResponse:
    """Cómo responde un tipo de vehículo a las pendientes."""

    power_w_kg: float = 60.0
    engine_brake: bool = False  # baja despacio en pendientes fuertes (camiones)
    down_start_pct: float = 3.0
    down_base_kmh: float = 90.0
    down_kmh_per_pct: float = 6.0
    down_min_kmh: float = 40.0


AUTO_GRADES = GradeResponse()


def uphill_speed(power: float, grade: float) -> float:
    """Velocidad máxima sostenible en subida (m/s); inf si no limita."""
    resist = G * (grade + C_RODADURA)
    if grade <= 0 or resist <= 0:
        return math.inf
    return power / resist


def downhill_speed(r: GradeResponse, grade: float) -> float:
    """Velocidad máxima en bajada por freno de motor (m/s); inf si no limita."""
    pct = -100.0 * grade
    if not r.engine_brake or pct <= r.down_start_pct:
        return math.inf
    return max(r.down_min_kmh, r.down_base_kmh - r.down_kmh_per_pct * (pct - r.down_start_pct)) / 3.6


def speed_limit(r: GradeResponse, grade: float) -> float:
    """Velocidad máxima por la pendiente (m/s)."""
    if grade > 0:
        return uphill_speed(r.power_w_kg, grade)
    if grade < 0:
        return downhill_speed(r, grade)
    return math.inf


def accel_limit(r: GradeResponse, v: float, grade: float) -> float:
    """Aceleración máxima que da el motor en subida (m/s²); inf si no limita."""
    if grade <= 0:
        return math.inf
    return r.power_w_kg / max(v, 1.0) - G * (grade + C_RODADURA)
