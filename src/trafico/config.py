"""Leer, guardar y modificar configuraciones (`SimConfig`) por nombre de parámetro.

Los parámetros se nombran con puntos para los anidados: `flow_per_hour`,
`idm.T`, `overtaking.t_guard`. `overtaking=none` desactiva los rebases.
"""

import dataclasses
import json
from pathlib import Path

from .idm import IDMParams
from .overtaking import OvertakeParams
from .simulation import SimConfig

_ANIDADOS = {"idm": IDMParams, "overtaking": OvertakeParams}

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
}


def nombre_real(name: str) -> str:
    return ALIAS.get(name, name)


def to_dict(cfg: SimConfig) -> dict:
    return dataclasses.asdict(cfg)


def from_dict(d: dict) -> SimConfig:
    kw = dict(d)
    for key, cls in _ANIDADOS.items():
        if key in kw and isinstance(kw[key], dict):
            kw[key] = cls(**kw[key])
    if "curves" in kw:
        kw["curves"] = tuple(tuple(c) for c in kw["curves"])
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


def get_param(cfg: SimConfig, name: str):
    name = nombre_real(name)
    obj = cfg
    for parte in name.split("."):
        if obj is None:
            return None
        obj = getattr(obj, parte)
    return obj
