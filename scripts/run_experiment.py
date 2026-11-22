"""Corre el experimento principal y guarda tablas (CSV) y gráficas.

Ejemplo:
    python scripts/run_experiment.py --flows 100 200 300 450 --seeds 10 --workers 8
"""

import argparse
import csv
import time
from pathlib import Path

from trafico.experiments import con_flujo, run_replicas
from trafico.plots import plot_delay_vs_flow, plot_gain_vs_flow, plot_time_vs_speed
from trafico.simulation import SimConfig
from trafico.stats import ideal_gain, paired_difference, summarize


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--flows", type=float, nargs="+", default=[100, 200, 300, 450])
    ap.add_argument("--speeds", type=float, nargs="+", default=[100, 110, 120, 130, 140])
    ap.add_argument("--compare", type=float, nargs=2, default=[120, 130], metavar=("LENTA", "RAPIDA"))
    ap.add_argument("--seeds", type=int, default=10)
    ap.add_argument("--workers", type=int, default=1)
    ap.add_argument("--length", type=float, default=20_000)
    ap.add_argument("--probes", type=int, default=30)
    ap.add_argument("--out", default="results")
    args = ap.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    seeds = list(range(1, args.seeds + 1))
    speeds = sorted(set(args.speeds) | set(args.compare))
    base = SimConfig(length=args.length, n_probes=args.probes)
    v_slow, v_fast = args.compare

    filas_res, filas_dif = [], []
    delays = {v: ([], []) for v in args.compare}
    gains, gain_hw, ideal = [], [], ideal_gain(args.length, v_slow, v_fast)
    por_flujo = {}
    t0 = time.time()
    for flow in args.flows:
        res = run_replicas(con_flujo(base, flow), speeds, seeds, workers=args.workers)
        por_flujo[flow] = res
        for v in speeds:
            s = summarize(res, v, seeds)
            filas_res.append({"flow": flow, **s})
            if v in delays:
                delays[v][0].append(s["delay"])
                delays[v][1].append(s["delay_hw"])
        g, hw = paired_difference(res, v_slow, v_fast, seeds)
        gains.append(g)
        gain_hw.append(hw)
        filas_dif.append({"flow": flow, "gain_s": g, "gain_hw": hw, "ideal_s": ideal})
        col = sum(r.collisions for r in res.values())
        print(f"flujo {flow:g}: ganancia {v_slow:g}->{v_fast:g} = {g:.1f} ± {hw:.1f} s "
              f"(ideal {ideal:.1f}); colisiones {col}; {time.time() - t0:.0f} s", flush=True)

    for nombre, filas in (("resumen_por_velocidad.csv", filas_res), ("ganancia.csv", filas_dif)):
        with open(out / nombre, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(filas[0]))
            w.writeheader()
            w.writerows(filas)

    plot_delay_vs_flow(args.flows, delays, str(out / "retraso_vs_flujo.png"))
    plot_gain_vs_flow(args.flows, gains, gain_hw, ideal, str(out / "ganancia_vs_flujo.png"), v_slow, v_fast)
    flow_ref = args.flows[len(args.flows) // 2]
    fila = [s for s in filas_res if s["flow"] == flow_ref]
    plot_time_vs_speed(
        [s["v0"] for s in fila], [s["travel_time"] for s in fila], [s["travel_time_hw"] for s in fila],
        [args.length / (s["v0"] / 3.6) for s in fila], str(out / "tiempo_vs_velocidad.png"), flow_ref,
    )
    print(f"Listo. Resultados en {out}/")


if __name__ == "__main__":
    main()
