"""Llegadas de vehículos: proceso de Poisson con velocidades deseadas aleatorias."""

import numpy as np

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
        self._rng = np.random.default_rng(seed)
        self._next_t = self._gap()

    def _gap(self) -> float:
        if self.rate_per_hour == 0:
            return float("inf")
        return float(self._rng.exponential(3600.0 / self.rate_per_hour))

    def _v0_kmh(self) -> float:
        while True:
            v = float(self._rng.normal(self.v0_mean_kmh, self.v0_std_kmh))
            if self.v0_min_kmh <= v <= self.v0_max_kmh:
                return v

    def due(self, t: float) -> list[float]:
        """Velocidades deseadas (m/s) de las llegadas hasta el instante `t`."""
        out = []
        while self._next_t <= t:
            out.append(kmh_a_ms(self._v0_kmh()))
            self._next_t += self._gap()
        return out
