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
    overtaken: int = 0  # veces que otro lo rebasó
    catchups: int = 0  # veces que tuvo que ir por debajo de v0 (alcanzó a alguien)
    slowed: bool = False  # va ahora por debajo de v0 (con histéresis)
    full_trip: bool = True  # False si empezó a mitad de la carretera (modo lleno)
    v_des: float = -1.0  # velocidad que busca ahora: v0, o menos en curva
    kind: str = "auto"  # "auto" o "camion"
    lane_prev: int = -1  # carril que está dejando (durante un cambio de carril)
    lc: float = 1.0  # avance del cambio de carril: 1 = terminado
    limit_factor: float = 1.0  # cuánto se pasa del límite (1 = lo respeta)
    respects_no_pass: bool = True
    driver: str = "normal"  # "prudente", "normal" o "agresivo"
    t_stuck: float = 0.0  # tiempo seguido atrapado detrás de otro, s
    a_buf: object = None  # aceleraciones pendientes (tiempo de reacción)
    a_prev: float = 0.0  # última aceleración aplicada
    vlim: object = None  # tabla de velocidad permitida (caché)
    mult: object = None  # tabla del factor de bajada (caché)
    convoy_start: bool = False  # el último intento de rebase seguía a otro que ya rebasaba
    convoy_overtakes: int = 0  # rebases empezados siguiendo a otro (en cadena)
    idm: object = None  # IDMParams propios (None: los de la carretera)
    grades: object = None  # GradeResponse propia (None: la de un auto)
    targets: list = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.lane < 0:
            self.lane = self.home_lane
        if self.v_des < 0:
            self.v_des = self.v0

    def occupies(self, lane: int) -> bool:
        """¿Ocupa este carril? Durante un cambio de carril ocupa los dos."""
        return lane == self.lane or (self.lc < 1.0 and lane == self.lane_prev)

    def change_lane(self, lane: int, duration: float) -> None:
        """Empieza un cambio de carril (instantáneo si `duration` es 0)."""
        if self.a_buf:
            self.a_buf.clear()  # situación nueva: las decisiones pendientes ya no valen
        if duration <= 0:
            self.lane = lane
            return
        if self.lc < 1.0 and lane == self.lane_prev:
            self.lc = 1.0 - self.lc  # vuelve atrás a mitad del cambio
        else:
            self.lc = 0.0
        self.lane_prev, self.lane = self.lane, lane

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
