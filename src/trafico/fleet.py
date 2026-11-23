"""Tipos de vehículo: autos y camiones."""

import math
from dataclasses import dataclass, field

from .idm import IDMParams

AUTO = "auto"
CAMION = "camion"
LARGO_AUTO = 4.5


@dataclass(frozen=True)
class TruckParams:
    """Camiones: proporción, tamaño, dinámica y distribución de la velocidad deseada.

    La velocidad deseada sigue una normal asimétrica (sesgada hacia abajo) con
    parámetros `loc`, `scale` y `skew` (km/h): con los valores por defecto la moda
    es ~105, el 96 % queda entre 90 y 110, el 0.5 % bajo 90 y el 3.5 % sobre 110.
    Además, una fracción `anomaly` son casos raros: la mayoría (`anomaly_slow`)
    muy lentos (cargados o con falla) y el resto con exceso de velocidad.
    """

    share: float = 0.0  # fracción de camiones en el tráfico de fondo (0 = ninguno)
    loc_kmh: float = 108.5
    scale_kmh: float = 6.5
    skew: float = -3.0
    anomaly: float = 0.02
    anomaly_slow: float = 0.75  # de las anomalías, qué fracción son lentas
    slow_min_kmh: float = 60.0
    slow_max_kmh: float = 90.0
    fast_min_kmh: float = 110.0
    fast_max_kmh: float = 125.0
    v_max_kmh: float = 125.0  # tope físico
    v_min_kmh: float = 50.0
    length: float = 16.5
    idm: IDMParams = field(default_factory=lambda: IDMParams(a_max=0.5, b=1.5, T=1.5))
    power_w_kg: float = 7.5  # potencia específica (para pendientes)

    def sample_kmh(self, rng) -> float:
        """Velocidad deseada de un camión (km/h)."""
        u = rng.random()
        if u < self.anomaly:
            if u < self.anomaly * self.anomaly_slow:
                return float(rng.uniform(self.slow_min_kmh, self.slow_max_kmh))
            return float(rng.uniform(self.fast_min_kmh, self.fast_max_kmh))
        d = self.skew / math.sqrt(1 + self.skew ** 2)
        while True:
            z0, z1 = rng.standard_normal(2)
            v = self.loc_kmh + self.scale_kmh * (d * abs(z0) + math.sqrt(1 - d * d) * z1)
            if self.v_min_kmh <= v <= self.v_max_kmh:
                return float(v)


# Potencia específica de un auto (W/kg): casi no lo frenan las pendientes
POTENCIA_AUTO = 60.0
