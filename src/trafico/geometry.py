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

from .slopes import AUTO_GRADES as _AUTO_GRADES
from .slopes import downhill_factor as _downhill_factor

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
    grades: tuple[tuple[float, float, float], ...] = ()  # (inicio, fin, pendiente) con pendiente
    #   en fracción (0.05 = 5 %) y positiva si sube en el sentido +1
    limits: tuple[tuple[float, float, float], ...] = ()  # (inicio, fin, km/h): límites de velocidad
    no_pass_zones: tuple[tuple[float, float], ...] = ()  # (inicio, fin): no rebasar (señalizado)
    no_pass_from_sight: bool = False  # señalizar "no rebasar" donde falta visibilidad
    limit_lookahead: float = 100.0  # se frena para un límite menor desde esta distancia, m
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
        pend = tuple(sorted((float(a), float(b), float(g)) for a, b, g in self.grades))
        for a, b, g in pend:
            if not (0 <= a < b <= self.length) or abs(g) > 0.2:
                raise ValueError(f"pendiente inválida: ({a}, {b}, {g})")
        for (_, b1, _), (a2, _, _) in zip(pend, pend[1:]):
            if a2 < b1:
                raise ValueError("los tramos de pendiente no pueden solaparse")
        object.__setattr__(self, "grades", pend)
        object.__setattr__(self, "limits", tuple(sorted((float(a), float(b), float(v)) for a, b, v in self.limits)))
        object.__setattr__(self, "no_pass_zones", tuple(sorted((float(a), float(b)) for a, b in self.no_pass_zones)))

    # --- consultas ---------------------------------------------------------
    @property
    def straight(self) -> bool:
        """Recta y plana, sin señales: no cambia nada respecto a no tener geometría."""
        return not self.curves and not self.grades and not self.limits and not self.has_no_pass

    @property
    def has_no_pass(self) -> bool:
        return bool(self.no_pass_zones) or (self.no_pass_from_sight and bool(self.curves))

    def _tabla_lim(self, direction: int) -> np.ndarray:
        """Límite de velocidad (m/s) por celda, ya anticipado `limit_lookahead` metros."""
        t = self._tablas.get(("lim", direction))
        if t is not None:
            return t
        n = int(math.ceil(self.length / self.grid)) + 1
        xs = np.arange(n) * self.grid
        s = xs if direction == 1 else self.length - xs
        lim = np.full(n, np.inf)
        for a, b, v in self.limits:
            lim[(s >= a) & (s < b)] = v / 3.6
        k = max(1, int(round(self.limit_lookahead / self.grid)))
        ant = lim.copy()
        for i in range(n):  # mínimo en los próximos `k` puntos: frena antes de la señal
            ant[i] = lim[i:i + k + 1].min()
        self._tablas[("lim", direction)] = ant
        return ant

    def speed_limit(self, direction: int, x: float) -> float:
        """Límite de velocidad señalizado (m/s) en la posición propia `x`; inf si no hay."""
        if not self.limits:
            return math.inf
        t = self._tabla_lim(direction)
        return float(t[min(max(int(x / self.grid), 0), len(t) - 1)])

    def _tabla_nopass(self, direction: int) -> np.ndarray:
        t = self._tablas.get(("np", direction))
        if t is not None:
            return t
        n = int(math.ceil(self.length / self.grid)) + 1
        xs = np.arange(n) * self.grid
        s = xs if direction == 1 else self.length - xs
        prohibido = np.zeros(n, dtype=bool)
        for a, b in self.no_pass_zones:
            prohibido |= (s >= a) & (s < b)
        if self.no_pass_from_sight and self.curves:
            prohibido |= self._tabla_vis(direction) < self.no_pass_sight
        self._tablas[("np", direction)] = prohibido
        return prohibido

    def no_pass_between(self, direction: int, x0: float, x1: float) -> bool:
        """¿Hay zona de no rebase señalizada entre x0 y x1 (posición propia)?"""
        if not self.has_no_pass:
            return False
        t = self._tabla_nopass(direction)
        i0 = min(max(int(x0 / self.grid), 0), len(t) - 1)
        i1 = min(max(int(x1 / self.grid), i0), len(t) - 1)
        return bool(t[i0:i1 + 1].any())

    def marked_no_pass(self, s: float, direction: int = 1) -> bool:
        """Para dibujar: ¿hay línea continua (no rebasar) en el punto `s` de la carretera?"""
        x = s if direction == 1 else self.length - s
        if self.has_no_pass:
            return self.no_pass_between(direction, x, x)
        return not self.can_pass_at(s, direction) if self.curves else False

    @property
    def has_grades(self) -> bool:
        return bool(self.grades)

    def _tabla_pend(self, direction: int) -> np.ndarray:
        t = self._tablas.get(("g", direction))
        if t is not None:
            return t
        n = int(math.ceil(self.length / self.grid)) + 1
        xs = np.arange(n) * self.grid + self.grid / 2  # centro de cada celda
        s = xs if direction == 1 else self.length - xs
        g = np.zeros(n)
        for a, b, pend in self.grades:
            g[(s >= a) & (s < b)] = pend * direction  # subir en un sentido es bajar en el otro
        self._tablas[("g", direction)] = g
        return g

    def grade(self, direction: int, x: float) -> float:
        """Pendiente que encuentra el sentido `direction` en su posición `x` (+ = sube)."""
        if not self.grades:
            return 0.0
        t = self._tabla_pend(direction)
        return float(t[min(max(int(x / self.grid), 0), len(t) - 1)])

    def elevation(self, s: float) -> float:
        """Altura (m) en el punto `s` de la carretera, partiendo de 0 en s = 0."""
        h = 0.0
        for a, b, g in self.grades:
            if s <= a:
                break
            h += g * (min(s, b) - a)
        return h

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

    def vlim_list(self, direction: int, resp=None, limit_factor: float = 1.0) -> list:
        """Velocidad permitida (m/s) por celda combinando curva, pendiente y límite señalizado.

        Se consulta con `int(x / grid)`. Es una lista de Python (acceso más rápido que numpy)
        y se guarda en caché por (sentido, tipo de vehículo, factor de exceso).
        """
        resp = resp or _AUTO_GRADES
        clave = ("vl", direction, resp, limit_factor)
        t = self._tablas.get(clave)
        if t is not None:
            return t
        curva = self._tabla(direction)
        n = len(curva)
        comb = np.empty(n)
        comb[:-1] = curva[1:]  # misma convención que `limit`: punto de rejilla siguiente
        comb[-1] = curva[-1]
        if self.grades and resp.engine_brake:
            # freno de motor en bajadas fuertes y largas (solo camiones pesados)
            from .slopes import engine_brake_speed

            pend = self._tabla_pend(direction)
            larga = self._tabla_bajada_larga(direction, resp)
            tope = np.array([engine_brake_speed(resp, g) if lg else np.inf for g, lg in zip(pend, larga)])
            for i in range(n - 2, -1, -1):  # se prepara antes de empezar a bajar
                tope[i] = min(tope[i], math.sqrt(tope[i + 1] ** 2 + 2 * self.b_curve * self.grid))
            comb = np.minimum(comb, tope)
        if self.limits:
            comb = np.minimum(comb, self._tabla_lim(direction) * limit_factor)
        t = comb.tolist()
        self._tablas[clave] = t
        return t

    def _tabla_bajada_larga(self, direction: int, resp) -> np.ndarray:
        """Celdas dentro de una bajada fuerte (más de `steep`) más larga que `long_descent_m`."""
        pend = self._tabla_pend(direction)
        fuerte = pend < -resp.steep
        out = np.zeros(len(pend), dtype=bool)
        i = 0
        while i < len(pend):
            if fuerte[i]:
                j = i
                while j < len(pend) and fuerte[j]:
                    j += 1
                if (j - i) * self.grid >= resp.long_descent_m:
                    out[i:j] = True
                i = j
            else:
                i += 1
        return out

    def mult_list(self, direction: int, resp=None) -> list:
        """Factor sobre la velocidad deseada por celda: en bajada el conductor se deja llevar."""
        resp = resp or _AUTO_GRADES
        clave = ("mult", direction, resp)
        t = self._tablas.get(clave)
        if t is None:
            t = self._tablas[clave] = [_downhill_factor(resp, g) for g in self._tabla_pend(direction).tolist()]
        return t

    def grade_list(self, direction: int) -> list:
        t = self._tablas.get(("gl", direction))
        if t is None:
            t = self._tablas[("gl", direction)] = self._tabla_pend(direction).tolist()
        return t

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
    def free_time(self, v0: float, direction: int, idm, dt: float, grades_resp=None,
                  limit_factor: float = 1.0) -> float:
        """Tiempo que tarda un vehículo solo, con velocidad deseada `v0` (m/s).

        Integra las mismas ecuaciones que la carretera (IDM en vía libre más el
        seguimiento de la velocidad permitida), así que es el "ideal" con curvas.
        """
        clave = ("t", direction, round(v0, 3), idm, dt, grades_resp, round(limit_factor, 4))
        if clave in self._tablas:
            return self._tablas[clave]
        from .idm import idm_acceleration
        from .slopes import AUTO_GRADES, accel_limit

        r = grades_resp or AUTO_GRADES
        tabla = self.vlim_list(direction, r, limit_factor)
        n = len(tabla) - 1
        mult = self.mult_list(direction, r) if self.grades else None
        # la física del motor se aplica con relieve, y a los camiones siempre (potencia y aire)
        pend = self.grade_list(direction) if self.grades else ([0.0] * (n + 1) if grades_resp is not None else None)
        v_in = min(v0, self.limit(direction, 0.0))
        if self.limits:
            v_in = min(v_in, self.speed_limit(direction, 0.0) * limit_factor)
        x, v, t = 0.0, v_in, 0.0
        while x < self.length:
            k = min(int(x / self.grid), n)
            vd = v0 if mult is None else v0 * mult[k]
            vd = min(vd, tabla[k])
            a = curve_accel(idm_acceleration(v, vd, None, None, idm), v, vd)
            if pend is not None:
                a = min(a, accel_limit(r, v, pend[k]))
            v_new = max(0.0, v + a * dt)
            x += 0.5 * (v + v_new) * dt
            v = v_new
            t += dt
        # mismo redondeo que la carretera: el vehículo sale en el paso en que cruza L
        self._tablas[clave] = t
        return t


    def free_time_interp(self, v0: float, direction: int, idm, dt: float, grades_resp=None) -> float:
        """`free_time` interpolado en una tabla cada 2 km/h (para muchos vehículos)."""
        clave = ("ti", direction, idm, dt, grades_resp)
        tabla = self._tablas.get(clave)
        if tabla is None:
            vs = np.arange(40.0, 152.0, 2.0) / 3.6
            tabla = (vs, np.array([self.free_time(v, direction, idm, dt, grades_resp) for v in vs.tolist()]))
            self._tablas[clave] = tabla
        return float(np.interp(v0, *tabla))


def curve_accel(a: float, v: float, v_des: float) -> float:
    """Limita la aceleración para no ir por encima de la velocidad permitida."""
    if v > v_des:
        return min(a, max(-B_MAX_CURVA, K_CURVA * (v_des - v)))
    return a


@dataclass(frozen=True)
class Preset:
    """Tipo de carretera para generar trazados al azar."""

    descripcion: str
    curvas_por_km: float = 0.0
    r_min: float = 300.0  # radio, m
    r_max: float = 900.0
    l_min: float = 200.0  # longitud de cada curva, m
    l_max: float = 600.0
    recta_min: float = 150.0  # recta mínima entre curvas, m


PRESETS = {
    "recta": Preset("Recta (sin curvas)"),
    "pocas": Preset("Pocas curvas suaves (0.3 por km, radio 300-900 m)", 0.3, 300, 900, 200, 600),
    "muchas": Preset("Muchas curvas (1.2 por km, radio 150-450 m)", 1.2, 150, 450, 150, 450),
    "montana": Preset("Montaña (2.5 curvas por km, radio 60-200 m)", 2.5, 60, 200, 80, 250, 80),
}


def build_trazado(nombre: str, length: float, seed: int) -> tuple:
    """Curvas al azar de un tipo de carretera (reproducibles con `seed`).

    El número de curvas es fijo (curvas_por_km × km) para que trazados del mismo
    tipo sean comparables; cambian su posición, su radio y su longitud.
    """
    if nombre not in PRESETS:
        raise ValueError(f"trazado desconocido: {nombre!r}; opciones: {', '.join(PRESETS)}")
    p = PRESETS[nombre]
    n = int(round(p.curvas_por_km * length / 1000.0))
    if n == 0:
        return ()
    rng = np.random.default_rng([seed, list(PRESETS).index(nombre)])
    largos = rng.uniform(p.l_min, p.l_max, n)
    radios = np.exp(rng.uniform(np.log(p.r_min), np.log(p.r_max), n))
    libre = length - largos.sum() - (n + 1) * p.recta_min
    while libre < 0 and n > 0:  # no caben: menos curvas
        n -= 1
        largos, radios = largos[:n], radios[:n]
        libre = length - largos.sum() - (n + 1) * p.recta_min
    rectas = p.recta_min + rng.dirichlet(np.ones(n + 1)) * libre
    curvas, x = [], 0.0
    for i in range(n):
        x += rectas[i]
        curvas.append((round(x, 1), round(min(length, x + largos[i]), 1), round(float(radios[i]), 1)))
        x += largos[i]
    return tuple(curvas)


@dataclass(frozen=True)
class Relieve:
    """Tipo de relieve para generar perfiles de pendiente al azar."""

    descripcion: str
    pct_min: float = 0.0  # pendiente de cada tramo, %
    pct_max: float = 0.0
    l_min: float = 400.0  # longitud de cada tramo, m
    l_max: float = 1200.0
    plano: float = 0.3  # fracción de tramos planos
    h_max: float = 150.0  # altura máxima respecto al inicio, m (evita subir sin fin)


RELIEVES = {
    "plano": Relieve("Plano (sin pendientes)"),
    "lomerio": Relieve("Lomerío (pendientes de 1.5 a 4 %)", 1.5, 4.0, 400, 1200, 0.3, 120),
    # SCT: en terreno montañoso la pendiente gobernadora es 4-6 % y la máxima 6-8 % según el tipo
    "montanoso": Relieve("Montañoso (pendientes de 3 a 6 %, a veces 7 %)", 3.0, 6.0, 300, 800, 0.15, 400),
}


def build_relieve(nombre: str, length: float, seed: int) -> tuple:
    """Tramos de pendiente al azar: ((inicio, fin, pendiente en fracción), ...)."""
    if nombre not in RELIEVES:
        raise ValueError(f"relieve desconocido: {nombre!r}; opciones: {', '.join(RELIEVES)}")
    r = RELIEVES[nombre]
    if r.pct_max <= 0:
        return ()
    rng = np.random.default_rng([seed, 100 + list(RELIEVES).index(nombre)])
    tramos, x, h = [], 0.0, 0.0
    while x < length - 1.0:
        largo = min(float(rng.uniform(r.l_min, r.l_max)), length - x)
        if rng.random() >= r.plano:
            pct = float(rng.uniform(r.pct_min, r.pct_max))
            if nombre == "montanoso" and rng.random() < 0.1:
                pct = float(rng.uniform(6.0, 7.0))  # algún tramo corto de pendiente máxima
            # sube o baja; si ya se está muy alto o muy bajo, se tiende a volver
            signo = 1.0 if rng.random() < 0.5 - 0.45 * max(-1.0, min(1.0, h / r.h_max)) else -1.0
            g = signo * pct / 100.0
            tramos.append((round(x, 1), round(x + largo, 1), round(g, 4)))
            h += g * largo
        x += largo
    return tuple(tramos)


def describe(geo: "Geometry | None", length: float) -> dict:
    """Números del trazado: curvas, % en curva, % sin visibilidad para rebasar."""
    vacio = {"curvas": 0, "pct_en_curva": 0.0, "pct_no_rebase": 0.0, "radio_min_m": None,
             "pendiente_max_pct": 0.0, "pct_pendiente_fuerte": 0.0, "desnivel_subida_m": 0.0}
    if geo is None:
        return vacio
    en_curva = sum(b - a for a, b, _ in geo.curves)
    xs = np.arange(0, length, geo.grid)
    no_pasa = np.mean([not geo.can_pass_at(s) for s in xs]) if geo.curves else 0.0
    fuerte = sum(b - a for a, b, g in geo.grades if abs(g) > 0.03)
    return {
        **vacio,
        "curvas": len(geo.curves),
        "pct_en_curva": round(100 * en_curva / length, 1),
        "pct_no_rebase": round(100 * float(no_pasa), 1),
        "radio_min_m": min((r for _, _, r in geo.curves), default=None),
        "pendiente_max_pct": round(100 * max((abs(g) for _, _, g in geo.grades), default=0.0), 1),
        "pct_pendiente_fuerte": round(100 * fuerte / length, 1),
        "desnivel_subida_m": round(sum(g * (b - a) for a, b, g in geo.grades if g > 0), 0),
    }
