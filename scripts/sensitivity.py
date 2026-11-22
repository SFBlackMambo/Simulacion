"""Sensibilidad de la ganancia 120 -> 130 km/h a los parámetros del modelo.

Ejemplo:
    python scripts/sensitivity.py --flow 200 --seeds 6 --workers 8
"""

import argparse
import csv
from dataclasses import replace
from pathlib import Path

from trafico.experiments import run_replicas
from trafico.idm import IDMParams
from trafico.overtaking import OvertakeParams
from trafico.simulation import SimConfig
from trafico.stats import ideal_gain, paired_difference, summarize


def variantes(base: SimConfig) -> dict[str, SimConfig]:
    ot = base.overtaking
    return {
        "base": base,
        "sin rebases": replace(base, overtaking=None),
        "margen t_guard=3 s": replace(base, overtaking=replace(ot, t_guard=3.0)),
        "margen t_guard=10 s": replace(base, overtaking=replace(ot, t_guard=10.0)),
        "umbral dv_min=5 m/s": replace(base, overtaking=replace(ot, dv_min=5.0)),
        "decide cada 3 s": replace(base, overtaking=replace(ot, decision_interval=3.0)),
        "IDM T=1.0 s": replace(base, idm=IDMParams(T=1.0)),
        "IDM T=2.0 s": replace(base, idm=IDMParams(T=2.0)),
        "IDM a_max=1.5": replace(base, idm=IDMParams(a_max=1.5)),
        "velocidades sigma=15": replace(base, v0_std_kmh=15.0),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--flow", type=float, default=200)
    ap.add_argument("--seeds", type=int, default=6)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--length", type=float, default=20_000)
    ap.add_argument("--probes", type=int, default=20)
    ap.add_argument("--out", default="results/sensibilidad.csv")
    args = ap.parse_args()

    seeds = list(range(1, args.seeds + 1))
    base = SimConfig(length=args.length, flow_per_hour=args.flow, n_probes=args.probes)
    ideal = ideal_gain(args.length, 120, 130)
    filas = []
    for nombre, cfg in variantes(base).items():
        res = run_replicas(cfg, [120, 130], seeds, workers=args.workers)
        g, hw = paired_difference(res, 120, 130, seeds)
        s120, s130 = summarize(res, 120, seeds), summarize(res, 130, seeds)
        filas.append({
            "variante": nombre, "ganancia_s": g, "ic95_s": hw, "ideal_s": ideal,
            "retraso_120_s": s120["delay"], "retraso_130_s": s130["delay"],
            "rebases_120": s120["overtakes"], "rebases_130": s130["overtakes"],
            "colisiones": sum(r.collisions for r in res.values()),
        })
        print(f"{nombre:24s} ganancia {g:6.1f} ± {hw:5.1f} s  (ideal {ideal:.1f})  "
              f"retraso 120={s120['delay']:.0f} 130={s130['delay']:.0f}  colisiones {filas[-1]['colisiones']}",
              flush=True)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


if __name__ == "__main__":
    main()
