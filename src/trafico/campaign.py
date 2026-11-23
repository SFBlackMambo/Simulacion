"""Campañas: muchas simulaciones barriendo parámetros, con datos crudos reanudables.

Una campaña es el producto cartesiano de los valores barridos × velocidades de
sonda × semillas. Cada corrida se guarda en cuanto termina, así que si se corta
se puede reanudar con el mismo comando: las corridas hechas no se repiten.

Archivos en la carpeta de salida:
    campana.json  configuración base, barridos, velocidades y semillas
    corridas.csv  una fila por corrida (resumen del tráfico de fondo)
    sondas.csv    una fila por sonda
    viajes.csv    una fila por vehículo de cada corrida (se apaga con guardar_viajes=False);
                  columnas descritas en docs/datos.md
"""

import csv
import itertools
import json
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import numpy as np

from . import config as cfgmod
from .simulation import RunResult, SimConfig, run_simulation

CAMPOS_SONDA = ["indice", "t_entrada", "tiempo_viaje", "tiempo_libre", "retraso", "rebases", "t_lento",
                "t_espera_entrada"]
CAMPOS_CORRIDA = ["colisiones", "vehiculos_emergencia", "n_fondo", "retraso_fondo", "retraso_fondo_mediana",
                  "rebases_fondo", "alcances_fondo", "veces_rebasado_fondo", "t_lento_fondo",
                  "rebases_sondas", "alcances_sondas", "rebases_en_cadena_fondo", "camiones_fondo",
                  "retraso_camiones", "pct_siguiendo_fondo", "t_contrario_fondo", "conflictos_lider",
                  "conflictos_contrario", "con_viajes"]


def parse_sweep(texto: str) -> tuple[str, list]:
    """`flujo=100,200,300` -> ("flow_per_hour", ["100", "200", "300"])."""
    nombre, _, valores = texto.partition("=")
    if not valores:
        raise ValueError(f"barrido sin valores: {texto!r} (usa nombre=v1,v2,...)")
    return cfgmod.nombre_real(nombre.strip()), [v.strip() for v in valores.split(",") if v.strip()]


def combos(base: SimConfig, sweeps: list[tuple[str, list]]) -> list[tuple[dict, SimConfig]]:
    """Todas las combinaciones de valores barridos: [({param: valor}, cfg), ...]."""
    nombres = [n for n, _ in sweeps]
    out = []
    for valores in itertools.product(*[v for _, v in sweeps]):
        cfg = base
        for n, v in zip(nombres, valores):
            cfg = cfgmod.set_param(cfg, n, v)
        out.append(({n: cfgmod.get_param(cfg, n) for n in nombres}, cfg))
    return out


def _tarea(args):
    k, cfg, v, seed, viajes = args
    res = run_simulation(cfg, v, seed)
    return k, v, seed, _resumir(res, viajes)


def _media(rows, key):
    return float(np.mean([r[key] for r in rows])) if rows else float("nan")


def _resumir(res: RunResult, viajes: bool) -> dict:
    fondo = [t for t in res.trips if t["viaje_completo"] and not t["sonda"]]
    sondas = [t for t in res.trips if t["sonda"]]
    corrida = {
        "colisiones": res.collisions,
        "vehiculos_emergencia": res.emergency_vehicles,
        "n_fondo": len(fondo),
        "retraso_fondo": _media(fondo, "retraso"),
        "retraso_fondo_mediana": float(np.median([t["retraso"] for t in fondo])) if fondo else float("nan"),
        "rebases_fondo": _media(fondo, "rebases"),
        "alcances_fondo": _media(fondo, "alcances"),
        "veces_rebasado_fondo": _media(fondo, "veces_rebasado"),
        "t_lento_fondo": _media(fondo, "t_lento"),
        "rebases_sondas": _media(sondas, "rebases"),
        "alcances_sondas": _media(sondas, "alcances"),
        "rebases_en_cadena_fondo": _media(fondo, "rebases_en_cadena"),
        "camiones_fondo": sum(t["clase"] == "camion" for t in fondo),
        "retraso_camiones": _media([t for t in fondo if t["clase"] == "camion"], "retraso"),
        "pct_siguiendo_fondo": _media(fondo, "pct_tiempo_siguiendo"),
        "t_contrario_fondo": _media(fondo, "t_carril_contrario"),
        "conflictos_lider": sum(t["conflictos_lider"] for t in res.trips),
        "conflictos_contrario": sum(t["conflictos_contrario"] for t in res.trips),
    }
    probes = [{
        "indice": p.index, "t_entrada": round(p.t_entry, 2), "tiempo_viaje": round(p.travel_time, 3),
        "tiempo_libre": round(p.free_time, 3), "retraso": round(p.delay, 3), "rebases": p.overtakes,
        "t_lento": round(p.t_slow, 2), "t_espera_entrada": round(p.t_wait_entry, 2),
    } for p in res.probes]
    return {"corrida": corrida, "sondas": probes, "viajes": res.trips if viajes else []}


class _Escritor:
    """CSV al que se van añadiendo filas (crea la cabecera si el archivo es nuevo)."""

    def __init__(self, path: Path, fields: list[str]):
        nuevo = not path.exists() or path.stat().st_size == 0
        if not nuevo:  # campaña reanudada: se respetan las columnas que ya tiene el archivo
            with open(path, newline="") as f:
                previas = next(csv.reader(f), None)
            if previas:
                fields = previas
        self.f = open(path, "a", newline="")
        self.w = csv.DictWriter(self.f, fieldnames=fields, extrasaction="ignore")
        if nuevo:
            self.w.writeheader()

    def write(self, rows):
        self.w.writerows(rows)

    def flush(self):
        self.f.flush()

    def close(self):
        self.f.close()


def _limpiar_incompletas(out: Path, claves_ok: set) -> None:
    """Quita de sondas.csv y viajes.csv las filas de corridas que no llegaron a corridas.csv."""
    for nombre in ("sondas.csv", "viajes.csv"):
        path = out / nombre
        if not path.exists():
            continue
        with open(path) as f:
            r = csv.DictReader(f)
            campos, filas = r.fieldnames, [x for x in r if (x["combo"], x["v_sonda"], x["semilla"]) in claves_ok]
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=campos)
            w.writeheader()
            w.writerows(filas)


def run_campaign(
    base: SimConfig,
    sweeps: list[tuple[str, list]],
    speeds: list[float],
    seeds: list[int],
    out: str | Path,
    workers: int = 1,
    guardar_viajes: bool = True,
    verbose: bool = True,
) -> Path:
    """Corre (o reanuda) una campaña y deja los datos crudos en `out`."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    spec = {"config": cfgmod.to_dict(base), "barridos": [[n, v] for n, v in sweeps],
            "velocidades": list(speeds), "semillas": list(seeds), "viajes": guardar_viajes}
    spec_path = out / "campana.json"
    if spec_path.exists():
        previo = json.loads(spec_path.read_text())
        fijo = ("config", "barridos")  # los viajes se pueden encender al reanudar
        if any(previo.get(c) != json.loads(json.dumps(spec[c])) for c in fijo):
            raise ValueError(f"{out} ya tiene otra campaña; usa otra carpeta de salida")
        # se pueden añadir semillas o velocidades a una campaña existente
        spec["velocidades"] = sorted(set(previo["velocidades"]) | set(spec["velocidades"]))
        spec["semillas"] = sorted(set(previo["semillas"]) | set(spec["semillas"]))
        spec["viajes"] = bool(previo.get("viajes")) or guardar_viajes
    spec_path.write_text(json.dumps(spec, indent=2, ensure_ascii=False))

    lista = combos(base, sweeps)
    nombres = [n for n, _ in sweeps]
    hechas = set()
    if (out / "corridas.csv").exists():
        with open(out / "corridas.csv") as f:
            hechas = {(r["combo"], r["v_sonda"], r["semilla"]) for r in csv.DictReader(f)}
        _limpiar_incompletas(out, hechas)
    tareas = [(k, cfg, float(v), s, guardar_viajes)
              for k, (_vals, cfg) in enumerate(lista) for v in speeds for s in seeds
              if (str(k), str(float(v)), str(s)) not in hechas]
    total = len(lista) * len(speeds) * len(seeds)
    if verbose:
        print(f"Campaña: {len(lista)} combinaciones × {len(speeds)} velocidades × {len(seeds)} semillas"
              f" = {total} corridas ({total - len(tareas)} ya hechas)", flush=True)
    if not tareas:
        return out

    clave = ["combo", *nombres, "v_sonda", "semilla"]
    w_corr = _Escritor(out / "corridas.csv", clave + CAMPOS_CORRIDA)
    w_sond = _Escritor(out / "sondas.csv", clave + CAMPOS_SONDA)
    w_viaj = _Escritor(out / "viajes.csv", clave + list(_campos_viaje())) if guardar_viajes else None

    def guardar(k, v, seed, r):
        cab = {"combo": k, **lista[k][0], "v_sonda": v, "semilla": seed}
        w_sond.write([{**cab, **p} for p in r["sondas"]])
        if w_viaj:
            w_viaj.write([{**cab, **t} for t in r["viajes"]])
            w_viaj.flush()
        w_sond.flush()
        w_corr.write([{**cab, **r["corrida"], "con_viajes": int(w_viaj is not None)}])  # al final: marca la corrida como hecha
        w_corr.flush()

    t0, n = time.time(), 0
    try:
        if workers <= 1:
            for t in tareas:
                guardar(*_tarea(t))
                n += 1
                _progreso(verbose, n, len(tareas), t0)
        else:
            with ProcessPoolExecutor(max_workers=workers) as pool:
                for fut in as_completed([pool.submit(_tarea, t) for t in tareas]):
                    guardar(*fut.result())
                    n += 1
                    _progreso(verbose, n, len(tareas), t0)
    finally:
        for w in (w_corr, w_sond, w_viaj):
            if w:
                w.close()
    return out


def _campos_viaje():
    from .recorder import CAMPOS_VIAJE

    return CAMPOS_VIAJE


def _progreso(verbose, n, total, t0):
    if not verbose:
        return
    paso = max(1, total // 20)
    if n % paso == 0 or n == total:
        dt = time.time() - t0
        resta = dt / n * (total - n)
        print(f"  {n}/{total} corridas  ({dt:.0f} s, faltan ~{resta:.0f} s)", flush=True)
