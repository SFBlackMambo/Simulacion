"""Puente entre el simulador y la página web (site/): corre en el navegador con Pyodide.

La página (JavaScript) crea un `SimWeb` con las opciones de los controles, lo avanza cada cuadro y dibuja lo que
devuelve `estado()`. Aquí no hay nada de dibujo: es la misma simulación que usa `trafico animar`.
"""

import math

from . import config as cfgmod
from .animation import color_de, texto_modelo, C_ATRAPADO, C_LIBRE, C_REBASE, C_SONDA
from .recorder import REBASE_ABORTO, REBASE_FIN
from .simulation import SimConfig, build_road, free_time, probe_times, tramos_2mas1
from .vehicle import kmh_a_ms, ms_a_kmh

COLORES = {C_LIBRE: 0, C_ATRAPADO: 1, C_REBASE: 2, C_SONDA: 3}
CAMPOS = 11  # números por vehículo en `estado()`

DEFECTO = {
    "longitud_km": 8.0,
    "modo": "lleno",  # "lleno" (N vehículos por sentido) o "flujo" (veh/h por sentido)
    "vehiculos": 70,
    "flujo": 300.0,
    "trazado": "recta",
    "relieve": "plano",
    "realista": False,
    "camiones": None,  # fracción; None = la del preset (10 % con realista, 0 sin él)
    "cada_2mas1_km": 0.0,  # un tramo 2+1 cada tantos km (0 = ninguno)
    "vel_sonda": 130.0,
    "semilla": 1,
}


def configurar(opciones: dict | None = None) -> SimConfig:
    """`SimConfig` de la animación a partir de las opciones de la página."""
    o = {**DEFECTO, **(opciones or {})}
    cfg = SimConfig(mode=o["modo"], n_vehicles=int(o["vehiculos"]), flow_per_hour=float(o["flujo"]),
                    length=float(o["longitud_km"]) * 1000.0, warmup=30.0, n_probes=5, probe_spacing=150.0)
    if o["trazado"] != "recta":
        cfg = cfgmod.set_param(cfg, "trazado", o["trazado"])
    if o["relieve"] != "plano":
        cfg = cfgmod.set_param(cfg, "relieve", o["relieve"])
    if o["realista"]:
        cfg = cfgmod.realista(cfg)
    if o["camiones"] is not None:
        cfg = cfgmod.set_param(cfg, "camiones", float(o["camiones"]))
    if float(o["cada_2mas1_km"]) > 0:
        cfg = cfgmod.set_param(cfg, "cada_2mas1", float(o["cada_2mas1_km"]) * 1000.0)
    return cfg


class _Contador:
    def __init__(self):
        self.fin = self.aborto = 0

    def event(self, road, kind, veh, n=0, cadena=False):
        if kind == REBASE_FIN:
            self.fin += 1
        elif kind == REBASE_ABORTO:
            self.aborto += 1

    def on_step(self, road):
        pass


class SimWeb:
    """Una corrida que avanza en tiempo real, con sondas, como la de `trafico animar`."""

    def __init__(self, opciones: dict | None = None):
        o = {**DEFECTO, **(opciones or {})}
        self.cfg = configurar(o)
        self.seed = int(o["semilla"])
        self.v_sonda = float(o["vel_sonda"])
        self.road = build_road(self.cfg, self.seed)
        self.road.recorder = _Contador()
        self.pendientes = list(probe_times(self.cfg))
        self.sondas = []
        self._libres: dict = {}

    def avanzar(self, segundos: float, max_pasos: int = 2000) -> int:
        """Avanza `segundos` simulados (como máximo `max_pasos` pasos). Devuelve los pasos dados."""
        road = self.road
        n = min(max_pasos, int(segundos / road.dt + 1e-9))
        for _ in range(n):
            while self.pendientes and road.t >= self.pendientes[0]:
                self.pendientes.pop(0)
                self.sondas.append(road.inject(kmh_a_ms(self.v_sonda), direction=1, probe=True))
            road.step()
        return n

    def estado(self) -> list:
        """Vehículos en la carretera, `CAMPOS` números cada uno:
        posición (m, coordenadas del sentido +1), carril, carril anterior, avance del cambio de carril, km/h,
        color (0 libre, 1 atrapado, 2 rebasando, 3 sonda), camión (0/1), sentido, largo (m), sonda (0/1),
        velocidad deseada (km/h)."""
        out = []
        road = self.road
        for v in road.vehicles:
            out += [road.position(v), v.lane, v.lane_prev, v.lc, ms_a_kmh(v.v), COLORES[color_de(v)],
                    1 if v.kind == "camion" else 0, v.direction, v.length, 1 if v.probe else 0, ms_a_kmh(v.v0)]
        return out

    def _libre(self, veh) -> float:
        k = veh.v0
        if k not in self._libres:
            self._libres[k] = free_time(self.cfg, veh.v0, veh.direction, seed=self.seed)
        return self._libres[k]

    def info(self) -> dict:
        """Contadores, la sonda en camino y las que ya llegaron."""
        road = self.road
        en_via = [s for s in self.sondas if s.t_exit is None and s in road.vehicles]
        activa = None
        if en_via:
            s = en_via[0]
            t = road.t - s.t_entry
            libre = self._libre(s) * s.x / self.cfg.length
            activa = {"pos": road.position(s), "v": ms_a_kmh(s.v), "v0": ms_a_kmh(s.v0), "recorrido_km": s.x / 1000,
                      "t": t, "perdido": t - libre, "rebases": s.overtakes, "alcances": s.catchups}
        hechas = []
        for i, s in enumerate(self.sondas):
            if s.t_exit is not None:
                libre = self._libre(s)
                hechas.append({"n": i + 1, "tardo": s.travel_time, "libre": libre, "perdio": s.travel_time - libre,
                               "rebases": s.overtakes, "alcances": s.catchups})
        return {
            "t": road.t, "en_carretera": len(road.vehicles), "rebases": road.recorder.fin,
            "abortos": road.recorder.aborto, "colisiones": road.collisions, "activa": activa, "hechas": hechas,
            "proxima": (self.pendientes[0] - road.t) if self.pendientes else None,
        }

    def geometria(self) -> dict:
        """Lo fijo de la carretera, para dibujarla una vez: curvas, no rebase, pendientes, límites, 2+1."""
        road, L = self.road, self.cfg.length
        geo = road.geometry
        d = {"longitud": L, "curvas": [], "no_rebase": [], "pendientes": [], "limites": [], "perfil": [],
             "carriles_rebase": [list(t) for t in tramos_2mas1(self.cfg)], "modelo": texto_modelo(self.cfg),
             "camiones": self.cfg.trucks.share > 0, "v_sonda": self.v_sonda}
        if geo is not None:
            d["curvas"] = [[a, b, r, ms_a_kmh(geo.curve_speed(r))] for a, b, r in geo.curves]
            d["pendientes"] = [[a, b, g] for a, b, g in geo.grades]
            d["limites"] = [[a, b, v] for a, b, v in geo.limits]
            paso = 20.0
            tramo = None
            for i in range(int(math.ceil(L / paso))):  # dónde la línea central es continua
                s = i * paso
                if geo.marked_no_pass(s):
                    if tramo is None:
                        tramo = [s, s + paso]
                    else:
                        tramo[1] = s + paso
                elif tramo is not None:
                    d["no_rebase"].append(tramo)
                    tramo = None
            if tramo is not None:
                d["no_rebase"].append(tramo)
            if geo.grades:
                d["perfil"] = [geo.elevation(L * i / 300) for i in range(301)]
        return d
