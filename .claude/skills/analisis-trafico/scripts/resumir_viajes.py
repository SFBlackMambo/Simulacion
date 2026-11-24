"""Resume una columna de viajes.csv por grupos, con la semilla como réplica (no cada vehículo).

    python .claude/skills/analisis-trafico/scripts/resumir_viajes.py results/f4_camiones_relieve \
        --campo retraso --por clase relieve --filtro sonda=0 viaje_completo=1 v_sonda=130

Cada vehículo de una misma corrida comparte el tráfico, así que no son independientes: primero se promedia por
(grupo, combinación, velocidad de sonda, semilla) y el IC 95 % se calcula entre esas medias. Lee el CSV en
streaming (sirve para archivos grandes).
"""

import argparse
import csv
from collections import defaultdict
from pathlib import Path

from trafico.stats import mean_ci


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("carpeta")
    ap.add_argument("--campo", required=True, help="columna numérica de viajes.csv (ver docs/datos.md)")
    ap.add_argument("--por", nargs="*", default=[], help="columnas para agrupar (p. ej. clase conductor)")
    ap.add_argument("--filtro", nargs="*", default=[], metavar="COL=VALOR",
                    help="solo filas con estos valores (numéricos se comparan como número)")
    args = ap.parse_args()
    filtros = [f.split("=", 1) for f in args.filtro]

    def coincide(r):
        for k, v in filtros:
            x = r.get(k, "")
            try:
                if float(x) != float(v):
                    return False
            except ValueError:
                if x != v:
                    return False
        return True

    acc = defaultdict(lambda: [0.0, 0])  # (grupo, combo, v, semilla) -> suma, n
    n_filas = 0
    with open(Path(args.carpeta) / "viajes.csv") as f:
        for r in csv.DictReader(f):
            if not coincide(r) or r.get(args.campo, "") == "":
                continue
            g = tuple(r[c] for c in args.por)
            a = acc[(g, r["combo"], r["v_sonda"], r["semilla"])]
            a[0] += float(r[args.campo])
            a[1] += 1
            n_filas += 1
    por_grupo = defaultdict(list)
    n_veh = defaultdict(int)
    for (g, _c, _v, _s), (suma, n) in acc.items():
        por_grupo[g].append(suma / n)
        n_veh[g] += n
    titulo = " / ".join(args.por) or "todos"
    print(f"{n_filas} viajes. {args.campo} por {titulo} (media de las medias por corrida ± IC 95 %):")
    for g in sorted(por_grupo):
        m, hw = mean_ci(por_grupo[g])
        print(f"  {' / '.join(g) or 'todos':35} {m:12.3f} ± {hw:8.3f}   ({len(por_grupo[g])} corridas, {n_veh[g]} viajes)")


if __name__ == "__main__":
    main()
