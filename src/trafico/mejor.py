"""La mejor velocidad deseada: tiempo contra combustible, CO2 y riesgo (`trafico graficar DIR --mejor`).

Lee `sondas.csv`, `corridas.csv` y `campana.json` de una campaña (con las columnas de F030-F032: litros,
CO2, velocidad media, conflictos...). No vuelve a simular: los precios se aplican aquí (`costos.py`).

Para cada combinación del barrido y cada velocidad de sonda:
- tiempo de viaje, ganancia contra 100 km/h (o la más baja) y contra la velocidad anterior, emparejadas
  sonda a sonda (mismo tráfico de fondo);
- litros, CO2 y las tres medidas de riesgo, por separado (modelo potencia, Kloeden y las del simulador);
- costo del viaje en MXN por escenario de precios, y la velocidad con el menor costo.

Todas las medias llevan IC 95 % entre semillas.
"""

from collections import defaultdict
from pathlib import Path

from .analysis import SERIES8, Campaign, _formato, _guardar_arriba, _redondear, valor_legible
from .costos import ESCENARIOS, Precios, balance, riesgo_kloeden, riesgo_nilsson
from .plots import GRID, INK, INK2, SURFACE, _ax, plt
from .recorder import write_csv
from .stats import mean_ci

CAMPOS_MEDIDOS = ("tiempo_viaje", "retraso", "rebases", "litros", "co2_kg", "v_media_kmh", "t_carril_contrario",
                  "conflictos", "frenado_emergencia", "choques")


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return float("nan")


def _media(xs):
    xs = [x for x in xs if x == x]
    return sum(xs) / len(xs) if xs else float("nan")


class _Datos:
    """Sondas de la campaña agrupadas por (combo, velocidad, semilla)."""

    def __init__(self, camp: Campaign):
        if not camp.sondas or "litros" not in camp.sondas[0]:
            raise ValueError("la campaña no tiene litros por sonda: hay que correrla de nuevo con esta versión")
        self.camp = camp
        self.length = {c: float(vals.get("length", camp.spec["config"]["length"])) for c, vals in camp.combos.items()}
        self.por = defaultdict(list)  # (combo, v, semilla) -> filas de sondas
        for r in camp.sondas:
            self.por[(r["combo"], float(r["v_sonda"]), int(r["semilla"]))].append(r)
        self.fondo = {(r["combo"], float(r["v_sonda"]), int(r["semilla"])): _f(r.get("v_media_fondo"))
                      for r in camp.corridas}
        self.veh_km = {(r["combo"], float(r["v_sonda"]), int(r["semilla"])): _f(r.get("veh_km"))
                       for r in camp.corridas}
        self.choques_corr = {(r["combo"], float(r["v_sonda"]), int(r["semilla"])): _f(r.get("colisiones"))
                             for r in camp.corridas}

    def semillas(self, combo, v):
        return sorted(s for (c, vv, s) in self.por if c == combo and vv == v)


def _costos_sonda(r: dict, km: float, v_fondo: float, p: Precios) -> dict:
    return balance(p, _f(r["tiempo_viaje"]), _f(r["litros"]), _f(r["co2_kg"]), km, _f(r["v_media_kmh"]),
                   v_trafico_kmh=v_fondo if v_fondo == v_fondo else None)


def tablas(folder, precios: dict[str, Precios] | None = None) -> tuple[list[dict], list[dict]]:
    """(una fila por combo y velocidad, una fila por combo y escenario con la mejor velocidad)."""
    precios = precios or dict(ESCENARIOS)
    camp = Campaign(folder)
    d = _Datos(camp)
    ref = 100.0 if 100.0 in camp.speeds else camp.speeds[0]
    filas, mejores = [], []
    for combo, vals in camp.combos.items():
        km = d.length[combo] / 1000.0
        # tiempo medio por semilla y velocidad (para las ganancias emparejadas)
        t_sem = {v: {s: _media([_f(r["tiempo_viaje"]) for r in d.por[(combo, v, s)]]) for s in d.semillas(combo, v)}
                 for v in camp.speeds}
        costo_por_v = {}
        for i, v in enumerate(camp.speeds):
            sems = d.semillas(combo, v)
            if not sems:
                continue
            fila = {**vals, "v_sonda": v, "n_semillas": len(sems)}
            for campo in CAMPOS_MEDIDOS:
                m, hw = mean_ci([_media([_f(r.get(campo)) for r in d.por[(combo, v, s)]]) for s in sems])
                fila[campo], fila[campo + "_ic95"] = m, hw
            fila["l_100km"] = fila["litros"] / km * 100.0
            for nombre, v_otro in (("ganancia_vs_ref", ref), ("ganancia_paso", camp.speeds[i - 1] if i else None)):
                if v_otro is None:  # la primera velocidad no tiene anterior
                    fila[nombre], fila[nombre + "_ic95"] = float("nan"), float("nan")
                    continue
                if v_otro == v:
                    fila[nombre], fila[nombre + "_ic95"] = 0.0, 0.0
                    continue
                difs = [t_sem[v_otro][s] - t_sem[v][s] for s in sems if s in t_sem[v_otro]]
                fila[nombre], fila[nombre + "_ic95"] = mean_ci(difs)
            fila["v_referencia"] = ref
            # riesgo 1: modelo potencia (con la velocidad media del viaje)
            rn = riesgo_nilsson(fila["v_media_kmh"])
            fila.update({f"riesgo_potencia_{k}": x for k, x in rn.items()})
            # riesgo 2: Kloeden (contra la velocidad media del tráfico de fondo en la misma corrida)
            v_fondo = _media([d.fondo.get((combo, v, s), float("nan")) for s in sems])
            fila["v_media_fondo"] = v_fondo
            fila["dv_fondo_kmh"] = fila["v_media_kmh"] - v_fondo
            fila["riesgo_kloeden"] = riesgo_kloeden(fila["dv_fondo_kmh"]) if v_fondo == v_fondo else float("nan")
            # riesgo 3: del simulador (por sonda; además choques de toda la corrida por millón de veh-km)
            vkm = sum(d.veh_km.get((combo, v, s), 0.0) for s in sems)
            ch = sum(d.choques_corr.get((combo, v, s), 0.0) for s in sems)
            fila["choques_por_mvkm"] = ch / vkm * 1e6 if vkm > 0 else float("nan")
            # dinero
            costo_por_v[v] = {}
            for esc, p in precios.items():
                por_sem = defaultdict(list)
                partes = defaultdict(list)
                for s in sems:
                    vf = d.fondo.get((combo, v, s), float("nan"))
                    for r in d.por[(combo, v, s)]:
                        b = _costos_sonda(r, km, vf, p)
                        por_sem[s].append(b["total"])
                        for k, x in b.items():
                            partes[k].append(x)
                m, hw = mean_ci([_media(x) for x in por_sem.values()])
                fila[f"costo_{esc}"], fila[f"costo_{esc}_ic95"] = m, hw
                if esc == "medio":
                    for k in ("tiempo", "combustible", "co2", "accidentes"):
                        fila[f"medio_{k}"] = _media(partes[k])
                costo_por_v[v][esc] = (m, hw, {s: _media(x) for s, x in por_sem.items()})
            filas.append(fila)
        _equilibrio(filas, combo_vals=vals, ref=ref)
        for esc in precios:
            disp = {v: c[esc] for v, c in costo_por_v.items()}
            if not disp:
                continue
            v_opt = min(disp, key=lambda v: disp[v][0])
            m_opt, hw_opt, sem_opt = disp[v_opt]
            # velocidades cuyo costo no se distingue del mínimo: diferencia emparejada por semilla (mismo
            # tráfico de fondo) con un IC 95 % que incluye el cero
            empate = []
            for v, (_m, _hw, sem) in disp.items():
                difs = [sem[s] - sem_opt[s] for s in sem if s in sem_opt]
                dm, dhw = mean_ci(difs) if len(difs) > 1 else (difs[0] if difs else 0.0, 0.0)
                if v == v_opt or dm - dhw <= 0:
                    empate.append(v)
            mejores.append({**vals, "escenario": esc, "riesgo": precios[esc].riesgo, "v_optima": v_opt,
                            "costo_optimo": m_opt, "costo_optimo_ic95": hw_opt,
                            "rango_empate": f"{min(empate):g}-{max(empate):g}",
                            **{f"costo_{v:g}": disp[v][0] for v in sorted(disp)}})
    return filas, mejores


def _equilibrio(filas: list[dict], combo_vals: dict, ref: float) -> None:
    """Valor del tiempo (MXN por vehículo y hora) con el que ir a cada velocidad cuesta lo mismo que a `ref`.

    = (combustible + CO2 + accidentes de más, con precios medios) / horas ganadas. Si el valor del tiempo es
    mayor, conviene ir más rápido que `ref`. También sin accidentes (solo combustible y CO2).
    """
    fs = [f for f in filas if all(f.get(k) == v for k, v in combo_vals.items())]
    base = next((f for f in fs if f["v_sonda"] == ref), None)
    if base is None or "medio_combustible" not in base:
        return
    for f in fs:
        horas = f["ganancia_vs_ref"] / 3600.0
        extra_sin = (f["medio_combustible"] + f["medio_co2"]) - (base["medio_combustible"] + base["medio_co2"])
        extra = extra_sin + f["medio_accidentes"] - base["medio_accidentes"]
        ok = f["v_sonda"] != ref and horas > 0
        f["vtt_equilibrio"] = extra / horas if ok else float("nan")
        f["vtt_equilibrio_sin_accidentes"] = extra_sin / horas if ok else float("nan")


# --- gráficas -------------------------------------------------------------------------------------------
def _nombre_combo(camp: Campaign, vals: dict) -> str:
    return ", ".join(valor_legible(p, vals[p]) for p in camp.params) or "Campaña"


def _por_combo(filas, camp):
    out = defaultdict(list)
    for f in filas:
        out[tuple(f[p] for p in camp.params)].append(f)
    return out


def _serie(ax, xs, ys, hw, i, label):
    ax.errorbar(xs, ys, yerr=hw, color=SERIES8[i], linewidth=2, marker="o", markersize=8, markeredgecolor=SURFACE,
                markeredgewidth=2, capsize=3, elinewidth=1.2, label=label)


def _etiquetar_fin(ax, finales):
    if len(finales) <= 4:
        from .analysis import _etiquetas_finales

        _etiquetas_finales(ax, finales)


def graficar(folder, precios: dict[str, Precios] | None = None, salida=None) -> list[Path]:
    """Tablas y gráficas de la mejor velocidad. Devuelve las rutas generadas."""
    precios = precios or dict(ESCENARIOS)
    camp = Campaign(folder)
    filas, mejores = tablas(folder, precios)
    out = Path(salida or Path(folder) / "graficas")
    out.mkdir(parents=True, exist_ok=True)
    rutas = [out / "mejor_por_velocidad.csv", out / "mejor_velocidad.csv"]
    write_csv(rutas[0], list(filas[0]), _redondear(filas))
    write_csv(rutas[1], list(mejores[0]), _redondear(mejores))
    grupos = _por_combo(filas, camp)
    if len(grupos) > len(SERIES8):
        grupos = dict(list(grupos.items())[:len(SERIES8)])  # el resto queda en las tablas
    nombres = {k: _nombre_combo(camp, fs[0]) for k, fs in grupos.items()}
    ref = filas[0]["v_referencia"]

    def lineas(campo, titulo, yl, archivo, cero=False):
        fig, ax = _ax(titulo, "Velocidad deseada de la sonda (km/h)", yl)
        finales = []
        for i, (k, fs) in enumerate(grupos.items()):
            fs = sorted((f for f in fs if f[campo] == f[campo]), key=lambda f: f["v_sonda"])
            if not fs:
                continue
            xs = [f["v_sonda"] for f in fs]
            ys = [f[campo] for f in fs]
            _serie(ax, xs, ys, [f.get(campo + "_ic95", 0) for f in fs], i, nombres[k])
            finales.append((xs[-1], ys[-1], nombres[k]))
        if cero:
            ax.axhline(0, color=GRID, linewidth=1)
        _etiquetar_fin(ax, finales)
        p = out / archivo
        _guardar_arriba(fig, ax, p)
        rutas.append(p)

    lineas("tiempo_viaje", "Tiempo de viaje según la velocidad deseada", "Tiempo de viaje (s)", "mejor_tiempo.png")
    lineas("ganancia_vs_ref", f"Tiempo que se gana contra ir a {ref:g} km/h", "Tiempo ganado (s)",
           "mejor_ganancia.png", cero=True)
    lineas("ganancia_paso", "Lo que gana cada paso de +10 km/h", "Tiempo ganado contra la velocidad anterior (s)",
           "mejor_ganancia_paso.png", cero=True)
    lineas("l_100km", "Combustible de la sonda", "L/100 km", "mejor_combustible.png")
    lineas("riesgo_kloeden", "Riesgo individual (Kloeden): según cuánto se aleja del tráfico",
           "Riesgo relativo de accidente", "mejor_riesgo_kloeden.png")
    lineas("vtt_equilibrio", f"¿Cuánto tendría que valer una hora para que convenga ir más rápido que {ref:g}?",
           "MXN por vehículo y hora (combustible, CO2 y accidentes)", "mejor_valor_equilibrio.png")
    lineas("vtt_equilibrio_sin_accidentes", f"Lo mismo sin contar accidentes (solo combustible y CO2)",
           "MXN por vehículo y hora", "mejor_valor_equilibrio_sin_accidentes.png")
    for esc in precios:
        riesgo = "riesgo individual de Kloeden" if precios[esc].riesgo == "kloeden" else "riesgo con el modelo potencia"
        lineas(f"costo_{esc}", f"Costo del viaje: precios {esc.split('_')[0]}, {riesgo}", "MXN por viaje",
               f"mejor_costo_{esc}.png")
    for k, fs in grupos.items():
        rutas.append(_partes(fs, out / f"mejor_partes{_sufijo(camp, fs[0])}.png", nombres[k]))
    plt.close("all")
    return rutas


def _sufijo(camp, f):
    return "".join(f"__{p}={_formato(f[p])}" for p in camp.params)


PARTES = (("tiempo", "Tiempo"), ("combustible", "Combustible"), ("co2", "CO2"), ("accidentes", "Accidentes"))


def _partes(fs, path: Path, nombre: str) -> Path:
    """Barras apiladas: de qué se compone el costo del viaje a cada velocidad (precios medios)."""
    fs = sorted(fs, key=lambda f: f["v_sonda"])
    fig, ax = _ax(f"De qué se compone el costo (precios medios) · {nombre}", "Velocidad deseada de la sonda (km/h)",
                  "MXN por viaje")
    xs = [f["v_sonda"] for f in fs]
    base = [0.0] * len(fs)
    ancho = 6.0
    for i, (k, lab) in enumerate(PARTES):
        alto = [f[f"medio_{k}"] for f in fs]
        ax.bar(xs, alto, bottom=base, width=ancho, color=SERIES8[i], edgecolor=SURFACE, linewidth=2, label=lab)
        base = [b + a for b, a in zip(base, alto)]
    i_min = min(range(len(fs)), key=lambda j: base[j])
    ax.annotate(f"mínimo: {xs[i_min]:g} km/h", (xs[i_min], base[i_min]), xytext=(0, 8), textcoords="offset points",
                ha="center", color=INK, fontsize=9)
    ax.set_xticks(xs)
    _guardar_arriba(fig, ax, path)
    return path


def resumen_texto(mejores: list[dict], camp: Campaign) -> str:
    """Texto corto con la mejor velocidad por combinación y escenario."""
    lineas = []
    for m in mejores:
        lineas.append(f"{_nombre_combo(camp, m)} · precios {m['escenario']}: mejor {m['v_optima']:g} km/h "
                      f"({m['costo_optimo']:.1f} ± {m['costo_optimo_ic95']:.1f} MXN; no se distingue de "
                      f"{m['rango_empate']} km/h)")
    return "\n".join(lineas)


__all__ = ["tablas", "graficar", "resumen_texto", "INK2"]
