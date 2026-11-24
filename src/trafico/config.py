"""Leer, guardar y modificar configuraciones (`SimConfig`) por nombre de parámetro.

Los parámetros se nombran con puntos para los anidados: `flow_per_hour`,
`idm.T`, `overtaking.t_guard`. `overtaking=none` desactiva los rebases.
"""

import dataclasses
import json
from pathlib import Path

from .drivers import DriverModel
from .fleet import TruckParams
from .idm import IDMParams
from .overtaking import OvertakeParams
from .simulation import SimConfig

_ANIDADOS = {"idm": IDMParams, "overtaking": OvertakeParams, "trucks": TruckParams, "drivers": DriverModel}

# Nombres cortos en español para la línea de comandos y el menú
ALIAS = {
    "flujo": "flow_per_hour",
    "longitud": "length",
    "modo": "mode",
    "vehiculos": "n_vehicles",
    "duracion": "duration",
    "calentamiento": "warmup",
    "sondas": "n_probes",
    "espaciado_sondas": "probe_spacing",
    "v_media": "v0_mean_kmh",
    "sigma": "v0_std_kmh",
    "rebases": "overtaking",
    "semilla_trazado": "geometry_seed",
    "a_lateral": "curve_a_lat",
    "despeje": "sight_clearance",
    "camiones": "trucks.share",
    "pendientes": "grades",
    "limite": "speed_limit_kmh",
    "limites": "speed_limits",
    "zonas_no_rebase": "no_pass_zones",
    "no_rebase_sin_visibilidad": "no_pass_from_sight",
    "respetan_limite": "drivers.limit_compliance",
    "respetan_no_rebase": "drivers.no_pass_compliance",
    "prudentes": "drivers.share_cautious",
    "agresivos": "drivers.share_aggressive",
    "impaciencia": "drivers.impatience_after",
    "reaccion": "reaction_time",
    "rebase_logit": "overtaking.gap_logit",
    "piso_seguro": "overtaking.gap_floor",
    "asomarse": "overtaking.peek",
    "carriles_rebase": "passing_lanes",
}


def nombre_real(name: str) -> str:
    return ALIAS.get(name, name)


def to_dict(cfg: SimConfig) -> dict:
    return dataclasses.asdict(cfg)


def from_dict(d: dict) -> SimConfig:
    kw = dict(d)
    for key, cls in _ANIDADOS.items():
        if key in kw and isinstance(kw[key], dict):
            sub = dict(kw[key])
            if isinstance(sub.get("idm"), dict):  # p. ej. trucks.idm
                sub["idm"] = IDMParams(**sub["idm"])
            sub.pop("grades", None)  # campañas viejas guardaban la respuesta fija del camión
            kw[key] = cls(**sub)
    for clave in ("curves", "grades", "speed_limits", "no_pass_zones", "passing_lanes"):
        if clave in kw:
            kw[clave] = tuple(tuple(c) for c in kw[clave])
    return SimConfig(**kw)


def save(cfg: SimConfig, path: str | Path, **extra) -> None:
    with open(path, "w") as f:
        json.dump({"config": to_dict(cfg), **extra}, f, indent=2, ensure_ascii=False)


def load(path: str | Path) -> tuple[SimConfig, dict]:
    with open(path) as f:
        d = json.load(f)
    return from_dict(d["config"]), d


def _convertir(valor, actual, tipo):
    """Convierte `valor` (texto o número) al tipo del campo."""
    if not isinstance(valor, str):
        return valor
    t = type(actual) if actual is not None else tipo
    if t is bool:
        return valor.lower() in ("1", "true", "si", "sí", "yes")
    if t in (int, float):
        return t(float(valor)) if t is int else float(valor)
    return valor


def set_param(cfg: SimConfig, name: str, value) -> SimConfig:
    """Copia de `cfg` con el parámetro `name` (p. ej. `idm.T`) cambiado a `value`."""
    name = nombre_real(name)
    if name == "overtaking" and str(value).lower() in ("none", "no", "0", "false"):
        return dataclasses.replace(cfg, overtaking=None)
    if name == "overtaking" and str(value).lower() in ("si", "sí", "yes", "1", "true"):
        return dataclasses.replace(cfg, overtaking=cfg.overtaking or OvertakeParams())
    if name == "curves" and isinstance(value, str):
        return dataclasses.replace(cfg, curves=parse_curves(value))
    if name == "passing_lanes" and isinstance(value, str):  # "inicio:fin:sentido;..."
        tramos = tuple((a, b, int(d)) for a, b, d in parse_curves(value))
        return dataclasses.replace(cfg, passing_lanes=tramos)
    if name == "speed_limits" and isinstance(value, str):
        return dataclasses.replace(cfg, speed_limits=parse_curves(value))
    if name == "no_pass_zones" and isinstance(value, str):
        zonas = tuple((float(a), float(b)) for a, b in (p.split(":") for p in value.replace(" ", "").split(";") if p))
        return dataclasses.replace(cfg, no_pass_zones=zonas)
    if name == "grades" and isinstance(value, str):  # porcentaje -> fracción
        return dataclasses.replace(cfg, grades=tuple((a, b, g / 100.0) for a, b, g in parse_curves(value)))
    partes = name.split(".")
    if len(partes) == 1:
        campos = {f.name: f for f in dataclasses.fields(SimConfig)}
        if name not in campos:
            raise KeyError(f"parámetro desconocido: {name}")
        actual = getattr(cfg, name)
        return dataclasses.replace(cfg, **{name: _convertir(value, actual, campos[name].type)})
    if len(partes) == 2 and partes[0] in _ANIDADOS:
        sub = getattr(cfg, partes[0])
        if sub is None:
            sub = _ANIDADOS[partes[0]]()
        if partes[1] not in {f.name for f in dataclasses.fields(sub)}:
            raise KeyError(f"parámetro desconocido: {name}")
        nuevo = dataclasses.replace(sub, **{partes[1]: _convertir(value, getattr(sub, partes[1]), float)})
        return dataclasses.replace(cfg, **{partes[0]: nuevo})
    raise KeyError(f"parámetro desconocido: {name}")


def parse_curves(texto: str) -> tuple:
    """`"1500:2500:200;6000:6400:350"` -> ((1500, 2500, 200), (6000, 6400, 350)) (metros)."""
    out = []
    for parte in texto.replace(" ", "").split(";"):
        if parte:
            a, b, r = (float(x) for x in parte.split(":"))
            out.append((a, b, r))
    return tuple(out)


def get_param(cfg: SimConfig, name: str):
    name = nombre_real(name)
    obj = cfg
    for parte in name.split("."):
        if obj is None:
            return None
        obj = getattr(obj, parte)
    return obj


# Preset "realista": enciende todo el comportamiento de la fase 3 con valores razonables.
PRESET_REALISTA = {
    "trucks.share": 0.10,
    "overtaking.t_lane_change": 3.0,
    "overtaking.convoy": True,
    "overtaking.blocked_view": True,
    "overtaking.no_start_braking": True,
    "drivers.share_cautious": 0.20,
    "drivers.share_aggressive": 0.15,
    "drivers.impatience_after": 60.0,
    "drivers.limit_compliance": 0.80,
    "drivers.no_pass_compliance": 0.90,
    "no_pass_from_sight": True,
    "reaction_time": 1.0,
    "b_physical": 9.0,
    "overtaking.return_closing": True,
    "overtaking.peek": True,  # F033: se asoma para ver (línea de visión) en lugar de la regla fija
    "overtaking.gap_logit": True,  # F032: aceptación de hueco con logit, sin piso de seguridad
}


def realista(cfg: SimConfig) -> SimConfig:
    """Aplica el preset realista (camiones, cambio de carril lento, cadena, conductores, reacción)."""
    for k, v in PRESET_REALISTA.items():
        if k == "overtaking.convoy" and cfg.overtaking is None:
            continue  # sin rebases no hay nada que ajustar
        if k.startswith("overtaking.") and cfg.overtaking is None:
            continue
        cfg = set_param(cfg, k, v)
    return cfg
