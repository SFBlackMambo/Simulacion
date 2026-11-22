"""Vehículo con velocidad deseada fija."""

from dataclasses import dataclass


def kmh_a_ms(v_kmh: float) -> float:
    """Convierte km/h a m/s."""
    return v_kmh / 3.6


def ms_a_kmh(v_ms: float) -> float:
    """Convierte m/s a km/h."""
    return v_ms * 3.6


@dataclass
class Vehicle:
    """Un vehículo. Unidades SI: metros y segundos.

    `x` es la posición del frente del vehículo medida desde el punto de entrada
    del carril. `v0` es la velocidad deseada, que no cambia durante el viaje.
    """

    id: int
    v0: float
    x: float = 0.0
    v: float = 0.0
    length: float = 4.5

    @property
    def rear(self) -> float:
        """Posición de la parte trasera."""
        return self.x - self.length

    def gap_to(self, leader: "Vehicle") -> float:
        """Distancia libre (parachoques a parachoques) hasta el líder."""
        return leader.rear - self.x
