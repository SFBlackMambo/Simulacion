"""Análisis de una campaña: tablas con media ± IC95 y gráficas, a partir de los CSV crudos.

No vuelve a simular: lee `campana.json`, `corridas.csv` y `sondas.csv`.
"""

import csv
import json
from collections import defaultdict
from pathlib import Path

from .plots import INK2, SURFACE, _guardar, plt
from .plots import _ax as _ax_base
from .recorder import write_csv
from .stats import mean_ci

# Paleta categórica validada (orden fijo, nunca cíclico)
SERIES8 = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"]

ETIQUETAS = {
    "flow_per_hour": "Flujo por sentido (veh/h)",
    "length": "Longitud de la carretera (m)",
    "n_vehicles": "Vehículos por sentido",
    "v0_std_kmh": "Dispersión de velocidades deseadas σ (km/h)",
    "v0_mean_kmh": "Velocidad deseada media (km/h)",
    "mode": "Modo de tráfico",
    "trazado": "Tipo de carretera",
    "sight_clearance": "Despeje lateral en curvas (m)",
    "curve_a_lat": "Aceleración lateral en curva (m/s²)",
    "overtaking": "Rebases",
    "idm.T": "Intervalo IDM T (s)",
    "idm.a_max": "Aceleración máxima (m/s²)",
    "overtaking.t_guard": "Margen con el contrario (s)",
    "overtaking.dv_min": "Diferencia mínima para rebasar (m/s)",
}


def etiqueta(param: str) -> str:
    return ETIQUETAS.get(param, param)


def valor_legible(param: str, v) -> str:
    """Texto corto para un valor de parámetro (p. ej. 20000 m -> "20 km")."""
    if param == "trazado":
        return {"recta": "Recta", "pocas": "Pocas curvas", "muchas": "Muchas curvas", "montana": "Montaña"}.get(v, v)
    if param == "length" and isinstance(v, float):
        return f"{v / 1000:g} km"
    if param == "flow_per_hour" and isinstance(v, float):
        return f"{v:g} veh/h"
    if param == "n_vehicles" and isinstance(v, float):
        return f"{v:g} vehículos"
    if param in ("v0_std_kmh", "v0_mean_kmh") and isinstance(v, float):
        return f"{v:g} km/h"
    return f"{etiqueta(param).split(' (')[0]} {_formato(v)}"


def _redondear(filas, nd=3):
    return [{k: round(v, nd) if isinstance(v, float) else v for k, v in f.items()} for f in filas]


def _guardar_arriba(fig, ax, path):
    """Leyenda en una fila sobre el gráfico, para que no tape los datos."""
    h, l = ax.get_legend_handles_labels()
    if h:
        ncol = min(5, len(h))
        filas = -(-len(h) // ncol)
        ax.legend(h, l, frameon=False, labelcolor=INK2, fontsize=9, loc="lower left",
                  bbox_to_anchor=(0.0, 1.0), ncol=ncol, borderaxespad=0.3, columnspacing=1.2)
        ax.set_title(ax.get_title(loc="left"), loc="left", pad=12 + 16 * filas, color="#0b0b0b",
                     fontsize=12, fontweight="bold")
    _guardar(fig, ax, path, leyenda=False)


def _num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return x


def _leer(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with open(path) as f:
        return list(csv.DictReader(f))


class Campaign:
    """Datos de una campaña ya corrida."""

    def __init__(self, folder: str | Path):
        self.folder = Path(folder)
        self.spec = json.loads((self.folder / "campana.json").read_text())
        self.params = [n for n, _ in self.spec["barridos"]]
        self.corridas = _leer(self.folder / "corridas.csv")
        self.sondas = _leer(self.folder / "sondas.csv")
        self.speeds = sorted({float(r["v_sonda"]) for r in self.corridas})
        self.seeds = sorted({int(r["semilla"]) for r in self.corridas})
        # valores de cada combinación (clave = índice de combo)
        # orden en que se dieron los valores de cada barrido (para valores de texto)
        self.orden = {str(v): i for _, vals in self.spec["barridos"] for i, v in enumerate(vals)}
        self.combos: dict[str, dict] = {}
        for r in self.corridas:
            self.combos.setdefault(r["combo"], {p: _num(r[p]) for p in self.params})

    # --- agregados ---------------------------------------------------------
    def _por_semilla(self, combo: str, v: float, campo: str) -> dict[int, float]:
        acc = defaultdict(list)
        for r in self.sondas:
            if r["combo"] == combo and float(r["v_sonda"]) == v:
                acc[int(r["semilla"])].append(float(r[campo]))
        return {s: sum(x) / len(x) for s, x in acc.items()}

    def probe_summary(self) -> list[dict]:
        filas = []
        for combo, vals in self.combos.items():
            for v in self.speeds:
                fila = {**vals, "v_sonda": v}
                for campo in ("tiempo_viaje", "retraso", "rebases", "t_lento"):
                    m, hw = mean_ci(list(self._por_semilla(combo, v, campo).values()))
                    fila[campo], fila[campo + "_ic95"] = m, hw
                corr = [r for r in self.corridas if r["combo"] == combo and float(r["v_sonda"]) == v]
                fila["alcances"] = mean_ci([float(r["alcances_sondas"]) for r in corr])[0]
                fila["colisiones"] = sum(int(r["colisiones"]) for r in corr)
                fila["n_semillas"] = len(corr)
                filas.append(fila)
        return filas

    def background_summary(self) -> list[dict]:
        filas = []
        for combo, vals in self.combos.items():
            corr = [r for r in self.corridas if r["combo"] == combo]
            fila = dict(vals)
            for campo in ("retraso_fondo", "rebases_fondo", "alcances_fondo", "t_lento_fondo", "n_fondo"):
                por_s = defaultdict(list)
                for r in corr:
                    por_s[r["semilla"]].append(float(r[campo]))
                m, hw = mean_ci([sum(x) / len(x) for x in por_s.values()])
                fila[campo], fila[campo + "_ic95"] = m, hw
            fila["colisiones"] = sum(int(r["colisiones"]) for r in corr)
            filas.append(fila)
        return filas

    def gain(self, v_slow: float, v_fast: float) -> list[dict]:
        """Tiempo ganado al ir a `v_fast` en vez de `v_slow`, emparejado sonda a sonda."""
        idx = defaultdict(dict)
        for r in self.sondas:
            idx[(r["combo"], int(r["semilla"]), int(r["indice"]))][float(r["v_sonda"])] = r
        filas = []
        for combo, vals in self.combos.items():
            g, ideal = defaultdict(list), defaultdict(list)
            for (c, s, _i), por_v in idx.items():
                if c == combo and v_slow in por_v and v_fast in por_v:
                    a, b = por_v[v_slow], por_v[v_fast]
                    g[s].append(float(a["tiempo_viaje"]) - float(b["tiempo_viaje"]))
                    ideal[s].append(float(a["tiempo_libre"]) - float(b["tiempo_libre"]))
            if not g:
                continue
            m, hw = mean_ci([sum(x) / len(x) for x in g.values()])
            ide = sum(sum(x) / len(x) for x in ideal.values()) / len(ideal)
            filas.append({**vals, "v_lenta": v_slow, "v_rapida": v_fast, "ganancia_s": m, "ganancia_s_ic95": hw,
                          "ideal_s": ide, "ganancia_pct_ideal": 100 * m / ide if ide else float("nan"),
                          "ganancia_pct_ideal_ic95": 100 * hw / ide if ide else float("nan")})
        return filas


# --- gráficas ----------------------------------------------------------------
def _ax(title, xlabel, ylabel):
    return _ax_base(title, xlabel, ylabel)


def _eje_x(ax, xs):
    """Valores no numéricos van como categorías equiespaciadas."""
    if all(isinstance(x, float) for x in xs):
        return list(xs)
    pos = list(range(len(xs)))
    ax.set_xticks(pos, [str(x) for x in xs])
    return pos


def _formato(v):
    return f"{v:g}" if isinstance(v, float) else str(v)


_ORDEN: dict = {}


def _clave(v):
    """Números en orden numérico; textos en el orden en que se barrieron."""
    return (1, _ORDEN.get(v, 99), v) if isinstance(v, str) else (0, 0, v)


def _lineas(ax, filas, x, serie, campo, nombre_serie, ideal=None):
    """Una línea por valor de `serie` (máximo 8, en el orden fijo de la paleta).

    Las series se desplazan un poco en x para que no se tapen las barras de error,
    y las etiquetas finales se separan para que no se encimen.
    """
    xs = sorted({f[x] for f in filas}, key=_clave)
    series = sorted({f[serie] for f in filas}, key=_clave) if serie else [None]
    if len(series) > len(SERIES8):
        raise ValueError(f"demasiadas series ({len(series)}); máximo {len(SERIES8)}")
    pos = _eje_x(ax, xs)
    paso = (min(b - a for a, b in zip(pos, pos[1:])) if len(pos) > 1 else 1.0) * 0.04
    finales = []
    for i, sv in enumerate(series):
        sel = {f[x]: f for f in filas if serie is None or f[serie] == sv}
        dx = (i - (len(series) - 1) / 2) * paso
        px = [p + dx for p, xv in zip(pos, xs) if xv in sel]
        ys = [sel[xv][campo] for xv in xs if xv in sel]
        hw = [sel[xv].get(campo + "_ic95", 0) or 0 for xv in xs if xv in sel]
        if not px:
            continue
        color = SERIES8[i]
        label = nombre_serie(sv)
        ax.errorbar(px, ys, yerr=hw, color=color, linewidth=2, marker="o", markersize=8,
                    markeredgecolor=SURFACE, markeredgewidth=2, capsize=3, elinewidth=1.2, label=label)
        finales.append((px[-1], ys[-1], label))
        if ideal:
            ax.plot(px, [sel[xv][ideal] for xv in xs if xv in sel], color=color, linewidth=1.2,
                    linestyle="--")
    if len(series) <= 4 and finales:
        _etiquetas_finales(ax, finales)


def _etiquetas_finales(ax, finales, sep_pt: float = 12.0):
    """Etiquetas al final de cada línea, separadas al menos `sep_pt` puntos en vertical."""
    sep_px = sep_pt * ax.figure.dpi / 72.0
    ax.figure.canvas.draw()  # fija los límites para convertir a píxeles
    tr = ax.transData
    pts = sorted(((tr.transform((x, y)), x, y, lab) for x, y, lab in finales), key=lambda t: t[0][1])
    x_max = max(p[0][0] for p in pts)
    ys_px = [p[0][1] for p in pts]
    for i in range(1, len(ys_px)):
        ys_px[i] = max(ys_px[i], ys_px[i - 1] + sep_px)
    a_pt = 72.0 / ax.figure.dpi  # de píxeles a puntos
    for ((x0, y0), x, y, lab), y_new in zip(pts, ys_px):
        ax.annotate(lab, (x, y), xytext=((x_max - x0) * a_pt + 8, (y_new - y0) * a_pt),
                    textcoords="offset points", color="#0b0b0b", fontsize=9, va="center")


def _grupos(filas, params, x, serie):
    """Separa las filas por los parámetros que no son ni el eje x ni la serie."""
    otros = [p for p in params if p not in (x, serie)]
    grupos = defaultdict(list)
    for f in filas:
        grupos[tuple((p, f[p]) for p in otros)].append(f)
    return grupos


def _sufijo(clave):
    return "".join(f"__{p}={_formato(v)}" for p, v in clave)


def _titulo_grupo(clave):
    return ", ".join(valor_legible(p, v) for p, v in clave)


def plot_campaign(folder, x: str | None = None, serie: str | None = None,
                  comparar: tuple[float, float] | None = None, salida: str | Path | None = None) -> list[Path]:
    """Tablas (CSV) y gráficas de una campaña. Devuelve las rutas generadas."""
    camp = Campaign(folder)
    _ORDEN.clear()
    _ORDEN.update(camp.orden)
    out = Path(salida or Path(folder) / "graficas")
    out.mkdir(parents=True, exist_ok=True)
    params = camp.params
    if not params:
        raise ValueError("la campaña no barre ningún parámetro")
    x = x or params[0]
    if serie is None and len(params) > 1:
        serie = next(p for p in params if p != x)
    for p in (x, serie):
        if p is not None and p not in params:
            raise ValueError(f"{p} no es un parámetro barrido; opciones: {params}")
    if comparar is None and len(camp.speeds) >= 2:
        comparar = (camp.speeds[-2], camp.speeds[-1])

    rutas = []
    sondas, fondo = camp.probe_summary(), camp.background_summary()
    if x == "length":  # en km se lee mejor
        sondas = [{**f, "length": f["length"] / 1000} for f in sondas]
        fondo = [{**f, "length": f["length"] / 1000} for f in fondo]
    write_csv(out / "resumen_sondas.csv", list(sondas[0]), _redondear(sondas))
    write_csv(out / "resumen_fondo.csv", list(fondo[0]), _redondear(fondo))
    rutas += [out / "resumen_sondas.csv", out / "resumen_fondo.csv"]
    nom_serie = (lambda v: valor_legible(serie, v)) if serie else (lambda v: "Simulado")
    xl = "Longitud de la carretera (km)" if x == "length" else etiqueta(x)

    if comparar:
        vs, vf = comparar
        gan = camp.gain(vs, vf)
        write_csv(out / "ganancia.csv", list(gan[0]), _redondear(gan))
        if x == "length":
            gan = [{**f, "length": f["length"] / 1000} for f in gan]
        rutas.append(out / "ganancia.csv")
        for clave, filas in _grupos(gan, params, x, serie).items():
            fig, ax = _ax(f"Tiempo que se gana al ir a {vf:g} en vez de {vs:g} km/h", xl, "Tiempo ganado (s)")
            _lineas(ax, filas, x, serie, "ganancia_s", nom_serie, ideal="ideal_s")
            ax.plot([], [], color=INK2, linestyle="--", linewidth=1.2, label="Ideal en vía libre")
            ax.set_ylim(bottom=0)
            p = out / f"ganancia{_sufijo(clave)}.png"
            _guardar_arriba(fig, ax, p)
            rutas.append(p)
            fig, ax = _ax(f"Ganancia {vs:g} → {vf:g} km/h como % de la ideal", xl, "% de la ganancia ideal")
            _lineas(ax, filas, x, serie, "ganancia_pct_ideal", nom_serie)
            ax.set_ylim(bottom=0)
            p = out / f"ganancia_pct{_sufijo(clave)}.png"
            _guardar_arriba(fig, ax, p)
            rutas.append(p)

    for campo, titulo, yl in (("retraso", "Retraso de las sondas", "Retraso sobre el tiempo libre (s)"),
                              ("tiempo_viaje", "Tiempo de viaje de las sondas", "Tiempo de viaje (s)"),
                              ("rebases", "Vehículos que rebasa cada sonda", "Rebases por viaje")):
        for clave, filas in _grupos(sondas, params, x, serie).items():
            # una gráfica por valor de la serie; dentro, una línea por velocidad de sonda
            series_vals = sorted({f[serie] for f in filas}, key=_clave) if serie else [None]
            for sv in series_vals:
                sel = [f for f in filas if serie is None or f[serie] == sv]
                extra = f" ({', '.join(filter(None, [nom_serie(sv) if serie else '', _titulo_grupo(clave)]))})"
                extra = "" if extra == " ()" else extra
                fig, ax = _ax(titulo + extra, xl, yl)
                _lineas(ax, sel, x, "v_sonda", campo, lambda v: f"{v:g} km/h")
                suf = _sufijo(clave) + (f"__{serie}={_formato(sv)}" if serie else "")
                p = out / f"sondas_{campo}{suf}.png"
                _guardar_arriba(fig, ax, p)
                rutas.append(p)

    for campo, titulo, yl in (("retraso_fondo", "Retraso medio del tráfico de fondo", "Retraso (s)"),
                              ("alcances_fondo", "Veces que cada vehículo tuvo que frenar por otro",
                               "Alcances por viaje"),
                              ("rebases_fondo", "Rebases por vehículo de fondo", "Rebases por viaje")):
        for clave, filas in _grupos(fondo, params, x, serie).items():
            fig, ax = _ax(titulo, xl, yl)
            _lineas(ax, filas, x, serie, campo, nom_serie)
            p = out / f"fondo_{campo}{_sufijo(clave)}.png"
            _guardar_arriba(fig, ax, p)
            rutas.append(p)
    plt.close("all")
    return rutas
