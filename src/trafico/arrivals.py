"""Llegadas de vehículos: proceso de Poisson con velocidades deseadas aleatorias."""

import numpy as np

from .fleet import AUTO, CAMION, TruckParams
from .vehicle import kmh_a_ms


class PoissonArrivals:
    """Genera llegadas con tasa `rate_per_hour` y velocidad deseada Normal truncada.

    Cada fuente tiene su propio generador aleatorio, así que la misma semilla
    produce siempre la misma secuencia, sin importar lo que pase en la carretera.
    """

    def __init__(
        self,
        rate_per_hour: float,
        v0_mean_kmh: float = 100.0,
        v0_std_kmh: float = 10.0,
        v0_min_kmh: float = 60.0,
        v0_max_kmh: float = 140.0,
        seed: int | np.random.SeedSequence = 0,
        max_count: int | None = None,
        trucks: TruckParams | None = None,
    ) -> None:
        if rate_per_hour < 0:
            raise ValueError("rate_per_hour debe ser >= 0")
        if v0_min_kmh >= v0_max_kmh:
            raise ValueError("v0_min_kmh debe ser menor que v0_max_kmh")
        self.rate_per_hour = rate_per_hour
        self.v0_mean_kmh = v0_mean_kmh
        self.v0_std_kmh = v0_std_kmh
        self.v0_min_kmh = v0_min_kmh
        self.v0_max_kmh = v0_max_kmh
        self.trucks = trucks if trucks is not None and trucks.share > 0 else None
        self.max_count = max_count  # None: sin límite
        self.count = 0
        self._rng = np.random.default_rng(seed)
        self._next_t = self._gap()

    def _gap(self) -> float:
        if self.rate_per_hour == 0:
            return float("inf")
        return float(self._rng.exponential(3600.0 / self.rate_per_hour))

    def sample_v0(self) -> float:
        """Una velocidad deseada (m/s) de la distribución de esta fuente."""
        return self.sample()[0]

    def sample(self) -> tuple[float, str]:
        """Un vehículo nuevo: (velocidad deseada en m/s, tipo).

        Sin camiones no se consume ningún número aleatorio extra, así que las
        secuencias son las mismas que antes de existir los camiones.
        """
        if self.trucks is not None and self._rng.random() < self.trucks.share:
            return kmh_a_ms(self.trucks.sample_kmh(self._rng)), CAMION
        return kmh_a_ms(self._v0_kmh()), AUTO

    def _v0_kmh(self) -> float:
        while True:
            v = float(self._rng.normal(self.v0_mean_kmh, self.v0_std_kmh))
            if self.v0_min_kmh <= v <= self.v0_max_kmh:
                return v

    def due(self, t: float) -> list[float]:
        """Velocidades deseadas (m/s) de las llegadas hasta el instante `t`."""
        return [v for v, _ in self.due_vehicles(t)]

    def due_vehicles(self, t: float) -> list[tuple[float, str]]:
        """Llegadas hasta el instante `t`: [(velocidad deseada m/s, tipo), ...]."""
        out = []
        while self._next_t <= t and (self.max_count is None or self.count < self.max_count):
            out.append(self.sample())
            self.count += 1
            self._next_t += self._gap()
        return out

    @property
    def exhausted(self) -> bool:
        """True si ya generó todas sus llegadas (`max_count`)."""
        return self.max_count is not None and self.count >= self.max_count
