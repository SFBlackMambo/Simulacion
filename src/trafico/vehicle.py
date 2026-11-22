"""Vehículo con velocidad deseada fija."""

from dataclasses import dataclass, field

SIGUIENDO = "SIGUIENDO"
REBASANDO = "REBASANDO"
REGRESANDO = "REGRESANDO"


def kmh_a_ms(v_kmh: float) -> float:
    """Convierte km/h a m/s."""
    return v_kmh / 3.6


def ms_a_kmh(v_ms: float) -> float:
    """Convierte m/s a km/h."""
    return v_ms * 3.6


@dataclass(eq=False)
class Vehicle:
    """Un vehículo. Unidades SI: metros y segundos.

    `x` es la posición del frente medida en el sentido de marcha del propio
    vehículo (0 al entrar, `Road.length` al salir). `v0` es la velocidad
    deseada y no cambia durante el viaje.

    Carriles físicos: el carril 0 es el normal del sentido +1 y el carril 1 el
    del sentido -1. Al rebasar, un vehículo usa el carril del otro sentido.
    """

    id: int
    v0: float
    x: float = 0.0
    v: float = 0.0
    length: float = 4.5
    direction: int = 1
    lane: int = -1
    probe: bool = False
    state: str = SIGUIENDO
    t_entry: float = 0.0
    t_exit: float | None = None
    t_wait_entry: float = 0.0  # tiempo esperando para poder entrar
    t_slow: float = 0.0  # tiempo yendo claramente por debajo de v0
    overtakes: int = 0  # vehículos rebasados
    aborts: int = 0  # rebases abortados
    emergency_steps: int = 0  # pasos con frenado de emergencia
    targets: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.lane < 0:
            self.lane = self.home_lane

    @property
    def home_lane(self) -> int:
        """Carril normal de su sentido."""
        return 0 if self.direction == 1 else 1

    @property
    def rear(self) -> float:
        """Posición de la parte trasera."""
        return self.x - self.length

    @property
    def travel_time(self) -> float | None:
        """Tiempo de viaje (de entrar a salir), o None si aún no sale."""
        if self.t_exit is None:
            return None
        return self.t_exit - self.t_entry

    def gap_to(self, leader: "Vehicle") -> float:
        """Distancia libre (parachoques a parachoques) hasta el líder."""
        return leader.rear - self.x
