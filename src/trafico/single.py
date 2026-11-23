"""Corrida única: una simulación con todos los datos guardados y gráficas de exploración."""

import json
from pathlib import Path

import numpy as np

from . import config as cfgmod
from .recorder import CAMPOS_VIAJE, REBASE_ABORTO, REBASE_FIN, REBASE_INICIO, Recorder, write_csv
from .geometry import describe
from .simulation import RunResult, SimConfig, geometry_from_config, run_simulation

HEADWAY_PELOTON = 3.0  # s: quien va a menos de esto de su líder está en un pelotón


def run_single(
    cfg: SimConfig,
    probe_v0_kmh: float,
    seed: int,
    out: str | Path,
    snapshot_interval: float = 5.0,
    graficas: bool = True,
) -> dict:
    """Corre una simulación, guarda CSV, `config.json`, `resumen.json` y gráficas en `out`."""
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    rec = Recorder(snapshot_interval=snapshot_interval)
    res = run_simulation(cfg, probe_v0_kmh, seed, recorder=rec)
    write_csv(out / "viajes.csv", CAMPOS_VIAJE, res.trips)
    rec.save(out)
    cfgmod.save(cfg, out / "config.json", velocidad_sonda=probe_v0_kmh, semilla=seed,
                intervalo_fotos=snapshot_interval)
    resumen = summarize_run(cfg, res, rec)
    resumen["trazado"] = describe(geometry_from_config(cfg, seed), cfg.length)
    with open(out / "resumen.json", "w") as f:
        json.dump(resumen, f, indent=2, ensure_ascii=False)
    if graficas:
        from .plots_explore import plot_all

        plot_all(out, cfg, res, rec, geometry_from_config(cfg, seed))
    return resumen


def summarize_run(cfg: SimConfig, res: RunResult, rec: Recorder) -> dict:
    completos = [t for t in res.trips if t["viaje_completo"]]
    fondo = [t for t in completos if not t["sonda"]]
    sondas = [t for t in completos if t["sonda"]]
    tipos = [e["tipo"] for e in rec.events]

    def media(rows, key):
        return float(np.mean([r[key] for r in rows])) if rows else float("nan")

    return {
        "vehiculos_que_salieron": len(res.trips),
        "viajes_completos": len(completos),
        "duracion_simulada_s": max((t["t_salida"] for t in res.trips), default=0.0),
        "retraso_medio_s": media(fondo, "retraso"),
        "retraso_mediano_s": float(np.median([t["retraso"] for t in fondo])) if fondo else float("nan"),
        "rebases_iniciados": tipos.count(REBASE_INICIO),
        "rebases_completados": tipos.count(REBASE_FIN),
        "rebases_abortados": tipos.count(REBASE_ABORTO),
        "alcances_medios": media(fondo, "alcances"),
        "colisiones": res.collisions,
        "vehiculos_con_frenado_emergencia": res.emergency_vehicles,
        "sondas": {
            "n": len(sondas),
            "tiempo_viaje_medio_s": media(sondas, "tiempo_viaje"),
            "retraso_medio_s": media(sondas, "retraso"),
            "rebases_medios": media(sondas, "rebases"),
            "alcances_medios": media(sondas, "alcances"),
        },
    }


def platoons(snapshots: list[tuple], headway: float = HEADWAY_PELOTON):
    """Fracción de vehículos en pelotón por instante y sentido.

    Devuelve {sentido: (tiempos, fracción, tamaño medio de pelotón)}. Un vehículo
    está en pelotón si va en su carril a menos de `headway` s del de delante.
    """
    por_t: dict[tuple[float, int], list[tuple[float, float]]] = {}
    for t, _vid, sentido, x, v_kmh, _v0, carril, _sonda, _estado, *_ in snapshots:
        if carril != (0 if sentido == 1 else 1):
            continue  # rebasando: no cuenta
        por_t.setdefault((t, sentido), []).append((x * sentido, v_kmh / 3.6))
    out = {}
    for sentido in (1, -1):
        ts, frac, tam = [], [], []
        for (t, s), vehs in sorted(por_t.items()):
            if s != sentido:
                continue
            vehs.sort(reverse=True)  # de delante hacia atrás
            n = len(vehs)
            liga = [False] * (n + 1)  # liga[i]: el i va pegado al i-1
            for i in range(1, n):
                gap = vehs[i - 1][0] - 4.5 - vehs[i][0]
                liga[i] = gap / max(vehs[i][1], 0.1) < headway
            en = sum(1 for i in range(n) if liga[i] or liga[i + 1])
            n_pel = sum(1 for i in range(n) if liga[i + 1] and not liga[i])
            ts.append(t)
            frac.append(en / n)
            tam.append(en / n_pel if n_pel else 0.0)
        out[sentido] = (np.array(ts), np.array(frac), np.array(tam))
    return out
