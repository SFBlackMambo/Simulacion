"""Trazado de la carretera: rectas y curvas.

Una curva es un tramo `[inicio, fin)` (en metros, coordenadas de la carretera,
las del sentido +1) con radio `R`. Tiene dos efectos:

1. **Velocidad**: nadie pasa por una curva a más de √(a_lat · R) (aceleración
   lateral cómoda `a_lat`). Los conductores frenan antes de entrar, con una
   deceleración `b_curve`, así que la velocidad permitida en cada punto es la
   envolvente min(v_curva, √(v_siguiente² + 2·b·d)).
2. **Visibilidad** (F016): en una curva se ve menos del carril contrario. Con un
   despeje lateral `m`, la distancia de visibilidad en curva es d ≈ √(8·R·m).

Las tablas se precalculan en una rejilla de `grid` metros por sentido, así que
consultar el límite en cada paso es O(1).
"""

import math
from dataclasses import dataclass, field

import numpy as np

K_CURVA = 4.0  # 1/s: ganancia con la que se sigue la velocidad permitida al frenar
B_MAX_CURVA = 3.0  # m/s²: deceleración máxima por curva


@dataclass(frozen=True)
class Geometry:
    length: float
    curves: tuple[tuple[float, float, float], ...] = ()  # (inicio, fin, radio), m
    a_lat: float = 2.0  # aceleración lateral cómoda, m/s²
    b_curve: float = 1.0  # deceleración para llegar a la curva a su velocidad, m/s²
    clearance: float = 10.0  # despeje lateral para la visibilidad en curva, m
    no_pass_sight: float = 450.0  # para dibujar: con menos visibilidad se marca "no rebasar", m
    grid: float = 10.0
    _tablas: dict = field(default_factory=dict, compare=False, repr=False, hash=False)

    def __post_init__(self):
        curvas = tuple(sorted((float(a), float(b), float(r)) for a, b, r in self.curves))
        for a, b, r in curvas:
            if not (0 <= a < b <= self.length) or r <= 0:
                raise ValueError(f"curva inválida: ({a}, {b}, {r})")
        for (_, b1, _), (a2, _, _) in zip(curvas, curvas[1:]):
            if a2 < b1:
                raise ValueError("las curvas no pueden solaparse")
        object.__setattr__(self, "curves", curvas)

    # --- consultas ---------------------------------------------------------
    @property
    def straight(self) -> bool:
        return not self.curves

    def curve_spans(self) -> list[tuple[float, float]]:
        return [(a, b) for a, b, _ in self.curves]

    def radius_at(self, s: float) -> float:
        """Radio en el punto `s` (coordenadas de la carretera); inf en recta."""
        for a, b, r in self.curves:
            if a <= s < b:
                return r
        return math.inf

    def curve_speed(self, radius: float) -> float:
        return math.sqrt(self.a_lat * radius) if math.isfinite(radius) else math.inf

    def _tabla(self, direction: int) -> np.ndarray:
        """Velocidad permitida (m/s) en la rejilla del sentido `direction` (x propio)."""
        t = self._tablas.get(("v", direction))
        if t is not None:
            return t
        n = int(math.ceil(self.length / self.grid)) + 1
        xs = np.arange(n) * self.grid
        s = xs if direction == 1 else self.length - xs
        vc = np.full(n, np.inf)
        for a, b, r in self.curves:
            vc[(s >= a) & (s < b) if direction == 1 else (s > a) & (s <= b)] = self.curve_speed(r)
        # una curva más corta que la rejilla también cuenta
        for a, b, r in self.curves:
            for p in (a, b):
                x = p if direction == 1 else self.length - p
                i = min(n - 1, int(x / self.grid))
                vc[i] = min(vc[i], self.curve_speed(r))
        v = vc.copy()
        for i in range(n - 2, -1, -1):  # envolvente de frenado hacia atrás
            v[i] = min(v[i], math.sqrt(v[i + 1] ** 2 + 2 * self.b_curve * self.grid))
        self._tablas[("v", direction)] = v
        return v

    def limit(self, direction: int, x: float) -> float:
        """Velocidad permitida (m/s) en la posición propia `x` del sentido `direction`."""
        t = self._tabla(direction)
        i = int(x / self.grid) + 1  # punto de rejilla siguiente: nunca llega tarde a la curva
        return float(t[min(max(i, 0), len(t) - 1)])

    def max_limit_between(self, direction: int, x0: float, x1: float) -> float:
        """Mínimo de la velocidad permitida entre x0 y x1 (posición propia)."""
        t = self._tabla(direction)
        i0 = min(max(int(x0 / self.grid), 0), len(t) - 1)
        i1 = min(max(int(x1 / self.grid), i0), len(t) - 1)
        return float(t[i0:i1 + 1].min())

    # --- visibilidad -----------------------------------------------------------
    def sight_in_curve(self, radius: float) -> float:
        """Distancia de visibilidad dentro de una curva de radio `radius` (m)."""
        return math.sqrt(8.0 * radius * self.clearance)

    def _tabla_vis(self, direction: int) -> np.ndarray:
        t = self._tablas.get(("vis", direction))
        if t is not None:
            return t
        n = int(math.ceil(self.length / self.grid)) + 1
        xs = np.arange(n) * self.grid
        vis = np.full(n, np.inf)
        for a, b, r in self.curves:
            # inicio y fin de la curva en el sistema propio del sentido
            xa, xb = (a, b) if direction == 1 else (self.length - b, self.length - a)
            sc = self.sight_in_curve(r)
            # antes de la curva se ve la recta hasta ella más un trozo de curva; dentro, solo el trozo
            d = np.where(xs < xa, xa - xs, np.where(xs < xb, 0.0, np.inf))
            vis = np.minimum(vis, d + sc)
        self._tablas[("vis", direction)] = vis
        return vis

    def sight(self, direction: int, x: float) -> float:
        """Cuánto se ve hacia delante (m) desde la posición propia `x`."""
        t = self._tabla_vis(direction)
        i = int(x / self.grid)
        return float(t[min(max(i, 0), len(t) - 1)])

    def can_pass_at(self, s: float, direction: int = 1) -> bool:
        """Para dibujar: ¿hay visibilidad típica de rebase en el punto `s` de la carretera?"""
        x = s if direction == 1 else self.length - s
        return self.sight(direction, x) >= self.no_pass_sight

    # --- tiempo libre --------------------------------------------------------
    def free_time(self, v0: float, direction: int, idm, dt: float) -> float:
        """Tiempo que tarda un vehículo solo, con velocidad deseada `v0` (m/s).

        Integra las mismas ecuaciones que la carretera (IDM en vía libre más el
        seguimiento de la velocidad permitida), así que es el "ideal" con curvas.
        """
        clave = ("t", direction, round(v0, 3), idm, dt)
        if clave in self._tablas:
            return self._tablas[clave]
        from .idm import idm_acceleration

        x, v, t = 0.0, min(v0, self.limit(direction, 0.0)), 0.0
        while x < self.length:
            vd = min(v0, self.limit(direction, x))
            a = curve_accel(idm_acceleration(v, vd, None, None, idm), v, vd)
            v_new = max(0.0, v + a * dt)
            x += 0.5 * (v + v_new) * dt
            v = v_new
            t += dt
        # mismo redondeo que la carretera: el vehículo sale en el paso en que cruza L
        self._tablas[clave] = t
        return t


    def free_time_interp(self, v0: float, direction: int, idm, dt: float) -> float:
        """`free_time` interpolado en una tabla cada 1 km/h (para muchos vehículos)."""
        clave = ("ti", direction, idm, dt)
        tabla = self._tablas.get(clave)
        if tabla is None:
            vs = np.arange(30.0, 161.0, 1.0) / 3.6
            tabla = (vs, np.array([self.free_time(v, direction, idm, dt) for v in vs]))
            self._tablas[clave] = tabla
        return float(np.interp(v0, *tabla))


def curve_accel(a: float, v: float, v_des: float) -> float:
    """Limita la aceleración para no ir por encima de la velocidad permitida."""
    if v > v_des:
        return min(a, max(-B_MAX_CURVA, K_CURVA * (v_des - v)))
    return a


def build_trazado(nombre: str, length: float, seed: int) -> tuple:
    """Curvas de un trazado con nombre (los trazados generados llegan en F017)."""
    if nombre == "recta":
        return ()
    raise ValueError(f"trazado desconocido: {nombre!r}")
