"""Compara dos velocidades de sonda dentro de una campaña, emparejando por semilla (mismo tráfico de fondo).

    python .claude/skills/analisis-trafico/scripts/comparar.py results/f4_flujo --a 100 --b 130
    python .claude/skills/analisis-trafico/scripts/comparar.py results/f4_realista --a 120 --b 150 \
        --campos tiempo_viaje litros frenado_emergencia

Para cada combinación del barrido: media de `b − a` por semilla (promediando las sondas de esa semilla) con
IC 95 % (t de Student entre semillas) y si el intervalo excluye el cero.
"""

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

from trafico.stats import mean_ci


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta")
    ap.add_argument("--a", type=float, required=True, help="velocidad de referencia (km/h)")
    ap.add_argument("--b", type=float, required=True, help="velocidad a comparar (km/h)")
    ap.add_argument("--campos", nargs="+", default=["tiempo_viaje", "litros", "co2_kg", "t_carril_contrario",
                                                    "conflictos", "frenado_emergencia"])
    args = ap.parse_args()
    carpeta = Path(args.carpeta)
    with open(carpeta / "sondas.csv") as f:
        filas = list(csv.DictReader(f))
    params = [n for n, _ in json.loads((carpeta / "campana.json").read_text())["barridos"]]
    por = defaultdict(list)  # (combo, v, semilla, campo) -> valores
    nombre = {}
    for r in filas:
        nombre[r["combo"]] = ", ".join(f"{p}={r[p]}" for p in params) or "campaña"
        for c in args.campos:
            por[(r["combo"], _f(r["v_sonda"]), int(r["semilla"]), c)].append(_f(r.get(c)))
    media = lambda xs: sum(xs) / len(xs)
    print(f"{'combinación':40} {'campo':22} {'a':>10} {'b − a':>12} {'IC 95 %':>10}  ¿distinto de 0?")
    for combo in sorted(nombre, key=int):
        for c in args.campos:
            semillas = sorted({s for (k, v, s, cc) in por if k == combo and cc == c and v == args.a})
            difs, bases = [], []
            for s in semillas:
                xa, xb = por.get((combo, args.a, s, c)), por.get((combo, args.b, s, c))
                if xa and xb:
                    difs.append(media(xb) - media(xa))
                    bases.append(media(xa))
            if len(difs) < 2:
                continue
            m, hw = mean_ci(difs)
            sig = "sí" if abs(m) > hw else "no"
            print(f"{nombre[combo][:40]:40} {c:22} {media(bases):10.3f} {m:12.3f} {hw:10.3f}  {sig}")


if __name__ == "__main__":
    main()
