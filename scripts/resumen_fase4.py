"""Resumen de las campañas de la fase 4 (la mejor velocidad) en tablas Markdown y CSV.

Lee `results/f4_*/graficas/mejor_por_velocidad.csv` y `mejor_velocidad.csv` (de `trafico graficar --mejor`).

    python scripts/resumen_fase4.py                # imprime las tablas
    python scripts/resumen_fase4.py --docs docs    # además copia CSV y gráficas a docs/
"""

import argparse
import csv
import shutil
from pathlib import Path

from trafico.analysis import Campaign, valor_legible


def _leer(p: Path) -> list[dict]:
    with open(p) as f:
        return list(csv.DictReader(f))


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _nombre(camp: Campaign, fila: dict) -> str:
    def val(p):
        x = fila[p]
        try:
            return valor_legible(p, float(x))
        except ValueError:
            return valor_legible(p, x)
    return ", ".join(val(p) for p in camp.params)


def resumen(folder: Path) -> tuple[list[str], list[dict]]:
    camp = Campaign(folder)
    por_v = _leer(folder / "graficas" / "mejor_por_velocidad.csv")
    mejores = _leer(folder / "graficas" / "mejor_velocidad.csv")
    filas = []
    claves = []
    for f in por_v:
        k = tuple(f[p] for p in camp.params)
        if k not in claves:
            claves.append(k)
    for k in claves:
        fs = {_num(f["v_sonda"]): f for f in por_v if tuple(f[p] for p in camp.params) == k}
        ms = {m["escenario"]: m for m in mejores if tuple(m[p] for p in camp.params) == k}
        fila = {"escenario": _nombre(camp, next(iter(fs.values())))}
        for v in (120.0, 130.0, 150.0):
            if v in fs:
                fila[f"gana_100_{v:g}"] = f"{_num(fs[v]['ganancia_vs_ref']):.0f} ± {_num(fs[v]['ganancia_vs_ref_ic95']):.0f}"
        for v in (100.0, 130.0):
            if v in fs:
                fila[f"l100_{v:g}"] = f"{_num(fs[v]['l_100km']):.1f}"
        if 130.0 in fs:
            fila["v_media_130"] = f"{_num(fs[130.0]['v_media_kmh']):.0f}"
            fila["kloeden_130"] = f"{_num(fs[130.0]['riesgo_kloeden']):.1f}"
            fila["conflictos_130"] = f"{_num(fs[130.0]['conflictos']):.2f}"
        for v in (120.0, 130.0):
            if v in fs:
                fila[f"vtt_{v:g}"] = f"{_num(fs[v]['vtt_equilibrio']):.0f}"
                fila[f"vtt_sin_{v:g}"] = f"{_num(fs[v]['vtt_equilibrio_sin_accidentes']):.0f}"
        fila["choques_mvkm"] = f"{max(_num(f['choques_por_mvkm']) for f in fs.values()):.2f}"
        for esc in ("bajo", "medio", "alto", "medio_kloeden"):
            if esc in ms:
                m = ms[esc]
                rango = m["rango_empate"]
                fila[f"mejor_{esc}"] = f"{_num(m['v_optima']):g} ({rango})"
        filas.append(fila)
    return camp.params, filas


COLUMNAS = [
    ("escenario", "Escenario"), ("gana_100_120", "Gana 100→120 (s)"), ("gana_100_130", "100→130 (s)"),
    ("gana_100_150", "100→150 (s)"), ("v_media_130", "V media a 130"), ("l100_100", "L/100 a 100"),
    ("l100_130", "L/100 a 130"), ("kloeden_130", "Kloeden a 130"), ("vtt_130", "Equilibrio 130 (MXN/h)"),
    ("vtt_sin_130", "sin accidentes"), ("mejor_bajo", "Mejor: bajo"),
    ("mejor_medio", "medio"), ("mejor_alto", "alto"), ("mejor_medio_kloeden", "medio (Kloeden)"),
]


def tabla_md(filas: list[dict]) -> str:
    cols = [(k, t) for k, t in COLUMNAS if any(k in f for f in filas)]
    out = ["| " + " | ".join(t for _, t in cols) + " |", "|" + "|".join("---" if k == "escenario" else "---:"
                                                                        for k, _ in cols) + "|"]
    for f in filas:
        out.append("| " + " | ".join(f.get(k, "") for k, _ in cols) + " |")
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--resultados", default="results")
    ap.add_argument("--docs", default=None, help="carpeta donde copiar CSV y gráficas")
    args = ap.parse_args()
    for folder in sorted(Path(args.resultados).glob("f4_*")):
        if not (folder / "graficas" / "mejor_velocidad.csv").exists():
            continue
        _, filas = resumen(folder)
        print(f"\n### {folder.name}\n")
        print(tabla_md(filas))
        if args.docs:
            docs = Path(args.docs)
            nombre = folder.name
            with open(docs / f"{nombre}_resumen.csv", "w", newline="") as f:
                w = csv.DictWriter(f, fieldnames=list(filas[0]))
                w.writeheader()
                w.writerows(filas)
            for archivo in ("mejor_por_velocidad.csv", "mejor_velocidad.csv"):
                shutil.copy(folder / "graficas" / archivo, docs / f"{nombre}_{archivo}")


if __name__ == "__main__":
    main()
