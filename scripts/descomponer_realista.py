"""¿Qué pieza del modelo realista pesa más en la ganancia 120 -> 130 km/h?

Compara el modelo simple, el realista, el realista quitando una pieza a la vez y
el simple añadiendo una pieza a la vez (recta de 20 km, 200 veh/h por sentido).

Ejemplo:
    python scripts/descomponer_realista.py --semillas 8 --nucleos 15 --salida docs/descomposicion_realista.csv
"""

import argparse
import csv
from concurrent.futures import ProcessPoolExecutor

from trafico import config as C
from trafico.simulation import SimConfig, run_simulation
from trafico.stats import mean_ci

PIEZAS = {
    "camiones": {"trucks.share": 0.0},
    "cambio de carril 3 s": {"overtaking.t_lane_change": 0.0},
    "visión tapada (asomarse)": {"overtaking.blocked_view": False, "overtaking.peek": False},
    "aceptación de hueco logit": {"overtaking.gap_logit": False},
    "rebase en cadena": {"overtaking.convoy": False},
    "conductores e impaciencia": {"drivers.share_cautious": 0.0, "drivers.share_aggressive": 0.0,
                                  "drivers.impatience_after": 0.0},
    "reacción 1 s": {"reaction_time": 0.0},
}


def variantes(base: SimConfig) -> dict:
    real = C.realista(base)
    out = {"simple": base, "realista": real}
    for nombre, cambios in PIEZAS.items():
        cfg = real
        for k, v in cambios.items():
            cfg = C.set_param(cfg, k, v)
        out[f"realista sin {nombre}"] = cfg
    for nombre, cambios in PIEZAS.items():
        cfg = base
        for k in cambios:
            cfg = C.set_param(cfg, k, C.get_param(real, k))
        out[f"simple + {nombre}"] = cfg
    return out


def _corre(args):
    nombre, cfg, v, seed = args
    r = run_simulation(cfg, v, seed)
    return nombre, v, seed, [p.travel_time for p in r.probes], r.collisions, sum(t["rebases"] for t in r.trips), len(r.trips)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--semillas", type=int, default=8)
    ap.add_argument("--nucleos", type=int, default=1)
    ap.add_argument("--flujo", type=float, default=200)
    ap.add_argument("--salida", default="results/descomposicion_realista.csv")
    args = ap.parse_args()
    base = SimConfig(flow_per_hour=args.flujo, n_probes=20)
    vs = variantes(base)
    tareas = [(n, cfg, v, s) for n, cfg in vs.items() for v in (120.0, 130.0) for s in range(1, args.semillas + 1)]
    with ProcessPoolExecutor(args.nucleos) as pool:
        res = list(pool.map(_corre, tareas))
    datos = {(n, v, s): (tt, c, rb, nv) for n, v, s, tt, c, rb, nv in res}
    filas = []
    for n in vs:
        g = []
        for s in range(1, args.semillas + 1):
            a, b = datos[(n, 120.0, s)][0], datos[(n, 130.0, s)][0]
            g.append(sum(x - y for x, y in zip(a, b)) / len(a))
        m, hw = mean_ci(g)
        reb = sum(datos[(n, v, s)][2] for v in (120.0, 130.0) for s in range(1, args.semillas + 1))
        nveh = sum(datos[(n, v, s)][3] for v in (120.0, 130.0) for s in range(1, args.semillas + 1))
        col = sum(datos[(n, v, s)][1] for v in (120.0, 130.0) for s in range(1, args.semillas + 1))
        filas.append({"variante": n, "ganancia_s": round(m, 2), "ic95_s": round(hw, 2),
                      "rebases_por_vehiculo": round(reb / nveh, 3), "colisiones": col})
        print(f"{n:38s} ganancia {m:5.1f} ± {hw:4.1f} s   rebases/vehículo {reb / nveh:.3f}   colisiones {col}")
    with open(args.salida, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(filas[0]))
        w.writeheader()
        w.writerows(filas)


if __name__ == "__main__":
    main()


def graficar(csv_path: str, png_path: str) -> None:
    """Barras horizontales con la ganancia (± IC95) de cada variante."""
    from trafico.plots import GRID, INK, INK2, SERIES, SURFACE, plt

    with open(csv_path) as f:
        filas = list(csv.DictReader(f))
    filas = list(reversed(filas))  # la primera arriba
    y = range(len(filas))
    g = [float(r["ganancia_s"]) for r in filas]
    hw = [float(r["ic95_s"]) for r in filas]
    fig, ax = plt.subplots(figsize=(8.6, 6.4), dpi=150, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.barh(list(y), g, xerr=hw, color=SERIES[1], height=0.6, error_kw={"ecolor": INK2, "elinewidth": 1.2,
                                                                         "capsize": 3})
    ax.axvline(0, color=GRID, linewidth=1)
    ax.set_yticks(list(y), [r["variante"] for r in filas], color=INK, fontsize=9)
    ax.set_xlabel("Tiempo ganado al ir a 130 en vez de 120 km/h (s, 20 km, 200 veh/h)", color=INK2)
    ax.set_title("¿Qué pieza del modelo realista pesa más?", loc="left", color=INK, fontsize=12,
                 fontweight="bold")
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, length=0)
    ax.grid(axis="x", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(png_path, facecolor=SURFACE)
    plt.close(fig)
