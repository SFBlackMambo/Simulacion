"""Gráficas de exploración de una corrida única (a partir del registro completo)."""

from pathlib import Path

import numpy as np
from matplotlib.collections import LineCollection
from matplotlib.colors import LinearSegmentedColormap

from .plots import GRID, INK, INK2, SERIES, SURFACE, _ax, _guardar, plt
from .recorder import REBASE_ABORTO, REBASE_FIN, Recorder
from .simulation import RunResult, SimConfig

# Rampa secuencial azul (pasos 250 -> 700): más oscuro = más velocidad perdida
RAMPA = LinearSegmentedColormap.from_list(
    "perdida", ["#86b6ef", "#5598e7", "#2a78d6", "#1c5cab", "#104281", "#0d366b"]
)
C_SONDA = SERIES[2]  # naranja
C_SENTIDO = {1: SERIES[1], -1: SERIES[3]}  # azul, aqua
NOMBRE_SENTIDO = {1: "Sentido →", -1: "Sentido ←"}


def _estilo(ax):
    ax.set_facecolor(SURFACE)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(GRID)
    ax.tick_params(colors=INK2, length=0)


def _sombrear_curvas(ax, geo, eje: str = "y", escala: float = 1000.0) -> None:
    """Sombrea los tramos en curva (bandas grises tenues)."""
    if geo is None:
        return
    for a, b in geo.curve_spans():
        if eje == "y":
            ax.axhspan(a / escala, b / escala, color=GRID, alpha=0.5, linewidth=0, zorder=0)
        else:
            ax.axvspan(a / escala, b / escala, color=GRID, alpha=0.5, linewidth=0, zorder=0)


def plot_space_time(snapshots, path, length: float, v_max_perdida: float = 40.0, geo=None) -> None:
    """Diagrama espacio-tiempo: una línea por vehículo, color = velocidad perdida (v0 - v)."""
    tray: dict[int, list] = {}
    for t, vid, sentido, x, v, _v0, _c, sonda, _e, v_perm in snapshots:
        tray.setdefault(vid, []).append((t / 60.0, x / 1000.0, max(0.0, v_perm - v), sonda, sentido))
    fig, axes = plt.subplots(2, 1, figsize=(9.6, 7.6), dpi=150, facecolor=SURFACE, sharex=True)
    for ax, sentido in zip(axes, (1, -1)):
        _estilo(ax)
        segs, cols, sondas = [], [], []
        for pts in tray.values():
            if pts[0][4] != sentido or len(pts) < 2:
                continue
            a = np.array([p[:3] for p in pts])
            if pts[0][3]:
                sondas.append(a)
                continue
            segs.extend(np.stack([a[:-1, :2], a[1:, :2]], axis=1))
            cols.extend(0.5 * (a[:-1, 2] + a[1:, 2]))
        _sombrear_curvas(ax, geo)
        lc = LineCollection(segs, cmap=RAMPA, linewidths=0.6)
        lc.set_array(np.asarray(cols))
        lc.set_clim(0, v_max_perdida)
        ax.add_collection(lc)
        for i, a in enumerate(sondas):
            ax.plot(a[:, 0], a[:, 1], color=C_SONDA, linewidth=2, label="Sonda" if i == 0 else None)
        ax.set_ylim(0, length / 1000.0)
        ax.set_ylabel("Posición (km)", color=INK2)
        ax.set_title(NOMBRE_SENTIDO[sentido], loc="left", color=INK, fontsize=10)
        if sondas:
            ax.legend(frameon=False, labelcolor=INK2, fontsize=9, loc="lower right",
                      bbox_to_anchor=(1.0, 1.0), borderaxespad=0.2)
    axes[0].autoscale(axis="x")
    axes[-1].set_xlabel("Tiempo (min)", color=INK2)
    titulo = "Diagrama espacio-tiempo: cada línea es un vehículo"
    if geo is not None:
        titulo += " (bandas grises: curvas)"
    fig.suptitle(titulo, x=0.02, ha="left",
                 color=INK, fontsize=12, fontweight="bold")
    cb = fig.colorbar(lc, ax=axes, shrink=0.8, pad=0.02)
    cb.set_label("Velocidad perdida por el tráfico (km/h)", color=INK2)
    cb.outline.set_visible(False)
    cb.ax.tick_params(colors=INK2, length=0)
    fig.savefig(path, facecolor=SURFACE, bbox_inches="tight")
    plt.close(fig)


def plot_delay_hist(trips, path) -> None:
    """Histograma del retraso de los vehículos de fondo con viaje completo."""
    d = np.array([t["retraso"] for t in trips if t["viaje_completo"] and not t["sonda"]])
    fig, ax = _ax("Retraso de cada vehículo respecto a su tiempo libre",
                  "Retraso (s)", "Vehículos")
    if len(d):
        bins = np.linspace(0, max(10.0, np.percentile(d, 99)), 30)
        ax.hist(np.clip(d, 0, bins[-1]), bins=bins, color=SERIES[1], edgecolor=SURFACE, linewidth=2)
        med = float(np.median(d))
        ax.axvline(med, color=INK2, linestyle="--", linewidth=1.5)
        ax.annotate(f"mediana {med:.0f} s", (med, ax.get_ylim()[1] * 0.92), xytext=(6, 0),
                    textcoords="offset points", color=INK, fontsize=9)
    _guardar(fig, ax, path, leyenda=False)


def plot_delay_vs_v0(trips, path) -> None:
    """Retraso contra velocidad deseada, un punto por vehículo, con la media por tramo."""
    full = [t for t in trips if t["viaje_completo"]]
    fondo = [t for t in full if not t["sonda"]]
    sondas = [t for t in full if t["sonda"]]
    fig, ax = _ax("Quien quiere ir más rápido pierde más tiempo", "Velocidad deseada (km/h)",
                  "Retraso (s)")
    v = np.array([t["v0_kmh"] for t in fondo])
    d = np.array([t["retraso"] for t in fondo])
    ax.scatter(v, d, s=10, color=SERIES[1], alpha=0.5, linewidths=0, label="Vehículos de fondo")
    if sondas:
        ax.scatter([t["v0_kmh"] for t in sondas], [t["retraso"] for t in sondas], s=40,
                   color=C_SONDA, edgecolors=SURFACE, linewidths=1.5, label="Sondas", zorder=3)
    if len(v) > 10:
        bordes = np.arange(np.floor(v.min() / 5) * 5, v.max() + 5, 5)
        cen, med = [], []
        for a, b in zip(bordes, bordes[1:]):
            m = (v >= a) & (v < b)
            if m.sum() >= 5:
                cen.append(0.5 * (a + b))
                med.append(d[m].mean())
        ax.plot(cen, med, color=INK, linewidth=2, label="Media cada 5 km/h")
    _guardar(fig, ax, path)


def _suavizar(t, y, ventana: float = 60.0):
    """Media móvil de `ventana` s (los tiempos van espaciados de forma regular)."""
    if len(t) < 3:
        return y
    k = max(1, int(round(ventana / max(np.median(np.diff(t)), 1e-9))))
    if k <= 1:
        return y
    w = np.ones(k)
    return np.convolve(y, w, mode="same") / np.convolve(np.ones_like(y), w, mode="same")


def plot_platoons(snapshots, path, t_llenado: float = 0.0) -> None:
    """Fracción de vehículos que van en pelotón, contra el tiempo, por sentido.

    `t_llenado` (s): hasta entonces la carretera aún se está llenando y se sombrea.
    """
    from .single import platoons

    datos = platoons(snapshots)
    fig, ax = _ax("Vehículos atrapados en pelotones (a menos de 3 s del de delante)",
                  "Tiempo (min)", "Vehículos en pelotón (%, media de 1 min)")
    if t_llenado > 0:
        ax.axvspan(0, t_llenado / 60.0, color=GRID, alpha=0.6, linewidth=0)
        ax.annotate("carretera llenándose", (t_llenado / 120.0, 96), ha="center", color=INK2, fontsize=8)
    for sentido, (ts, frac, _tam) in datos.items():
        if len(ts):
            ax.plot(ts / 60.0, 100 * _suavizar(ts, frac), color=C_SENTIDO[sentido], linewidth=2,
                    label=NOMBRE_SENTIDO[sentido])
    ax.set_ylim(0, 100)
    _guardar(fig, ax, path)


def plot_overtakes_by_km(events, path, length: float, geo=None) -> None:
    """Rebases completados y abortados por kilómetro de carretera (posición de inicio... y fin)."""
    km = max(1, int(np.ceil(length / 1000.0)))
    bins = np.arange(km + 1)
    fin = np.histogram([e["x"] / 1000 for e in events if e["tipo"] == REBASE_FIN], bins)[0]
    abo = np.histogram([e["x"] / 1000 for e in events if e["tipo"] == REBASE_ABORTO], bins)[0]
    fig, ax = _ax("Dónde se rebasa" + (" (bandas grises: curvas)" if geo is not None else ""),
                  "Kilómetro", "Rebases")
    _sombrear_curvas(ax, geo, eje="x")
    ax.bar(bins[:-1] + 0.5, fin, width=0.9, color=SERIES[1], label="Completados",
           edgecolor=SURFACE, linewidth=1)
    ax.bar(bins[:-1] + 0.5, abo, width=0.9, bottom=fin, color=SERIES[2], label="Abortados",
           edgecolor=SURFACE, linewidth=1)
    _guardar(fig, ax, path)


def plot_all(out: str | Path, cfg: SimConfig, res: RunResult, rec: Recorder, geo=None) -> list[Path]:
    out = Path(out)
    rutas = {
        "espacio_tiempo.png": lambda p: plot_space_time(rec.snapshots, p, cfg.length, geo=geo),
        "retraso_histograma.png": lambda p: plot_delay_hist(res.trips, p),
        "retraso_vs_velocidad.png": lambda p: plot_delay_vs_v0(res.trips, p),
        "pelotones.png": lambda p: plot_platoons(
            rec.snapshots, p, 0.0 if cfg.mode == "lleno" else cfg.length / (cfg.v0_mean_kmh / 3.6)),
        "rebases_por_km.png": lambda p: plot_overtakes_by_km(rec.events, p, cfg.length, geo=geo),
    }
    hechas = []
    for nombre, f in rutas.items():
        f(out / nombre)
        hechas.append(out / nombre)
    return hechas
