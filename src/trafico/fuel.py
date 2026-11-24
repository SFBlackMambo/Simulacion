"""Combustible y CO2 por vehículo, a partir de la potencia que pide en cada paso.

Modelo (solo se registra; no cambia la dinámica):

- Potencia específica en la rueda (VSP, Jiménez-Palacios 1999, en kW/t = W/kg):
      autos:    VSP = v·(1.1·a + g·i + 0.132) + 0.000302·v³
      camiones: igual, con masa rotatoria 1.05, rodadura g·0.0065 y aire ½·ρ·CdA·v³/m
  con `v` en m/s, `a` la aceleración aplicada (m/s²) e `i` la pendiente (fracción).
- Consumo: línea de Willans, la forma de los modelos de potencia (Akçelik; VT-CPFM de Rakha et al.
  2011; las tasas de MOVES por intervalo de VSP crecen casi lineal con la potencia):
      potencia de combustible = P0 + max(VSP, 0)·m / η
  `P0` es lo que gasta el motor sin entregar potencia (ralentí y fricción) y `η` la eficiencia
  marginal del tanque a la rueda. Con VSP < 0 (frenando o bajando) gasta solo `P0`.
- Litros = energía / poder calorífico; CO2 por litro según la EPA (gasolina 8,887 g/galón,
  diésel 10,180 g/galón).

Masa del camión: sale de su relación peso/potencia con un motor de 430 hp (el vehículo de
proyecto T3-S2-R4 de la SCT: 75.5 t y 430 hp ≈ 390 lb/hp). Así un camión de 150 lb/hp pesa ~29 t
y un full de 390 lb/hp ~76 t.

Revisión contra referencias (tests/test_fuel.py): un auto en llano a velocidad constante gasta
≈5.7, 6.8 y 7.5 L/100 km a 100, 120 y 130 km/h, y un camión de 30 t a 90 km/h ≈31 L/100 km. Son
valores típicos de autos compactos de gasolina y de tractocamiones (pruebas de consumo publicadas y
el aumento de ~30 % de 100 a 130 km/h); los coeficientes son supuestos que se pueden cambiar.
"""

import math
from dataclasses import dataclass

G = 9.81
RHO = 1.2
GASOLINA_MJ_L = 32.0  # poder calorífico inferior
DIESEL_MJ_L = 35.8
CO2_GASOLINA = 8.887 / 3.785411784  # kg/L (EPA)
CO2_DIESEL = 10.180 / 3.785411784
HP_CAMION = 430.0
KG_POR_LB = 0.45359237


@dataclass(frozen=True)
class FuelParams:
    """Parámetros de consumo de un tipo de vehículo."""

    mass_kg: float = 1500.0
    rot: float = 1.1  # factor de masa rotatoria
    roll: float = 0.132  # rodadura, m/s² (g·Cr)
    aero: float = 0.000302  # ½·ρ·CdA/m, 1/m
    p0_kw: float = 8.0  # ralentí y fricción, kW de combustible (~0.9 L/h de gasolina)
    eta: float = 0.36  # eficiencia marginal del tanque a la rueda
    mj_l: float = GASOLINA_MJ_L
    co2_kg_l: float = CO2_GASOLINA


AUTO_FUEL = FuelParams()
CdA_CAMION = 6.0


def truck_fuel(lb_hp: float) -> FuelParams:
    """Consumo de un camión con relación peso/potencia `lb_hp`."""
    m = lb_hp * HP_CAMION * KG_POR_LB
    return FuelParams(mass_kg=m, rot=1.05, roll=G * 0.0065, aero=0.5 * RHO * CdA_CAMION / m, p0_kw=20.0,
                      eta=0.40, mj_l=DIESEL_MJ_L, co2_kg_l=CO2_DIESEL)


def vsp(p: FuelParams, v: float, a: float, grade: float) -> float:
    """Potencia específica en la rueda, W/kg (= kW/t)."""
    return v * (p.rot * a + G * grade + p.roll) + p.aero * v * v * v


def litros_por_s(p: FuelParams, v: float, a: float, grade: float) -> float:
    """Consumo instantáneo, L/s."""
    w = vsp(p, v, a, grade)
    kw = p.p0_kw + (w * p.mass_kg / 1000.0 / p.eta if w > 0 else 0.0)
    return kw / (p.mj_l * 1000.0)


def l_100km_constante(p: FuelParams, v_kmh: float, grade: float = 0.0) -> float:
    """Consumo a velocidad constante, L/100 km (para revisar contra referencias)."""
    v = v_kmh / 3.6
    return litros_por_s(p, v, 0.0, grade) * 100_000.0 / v if v > 0 else math.inf
