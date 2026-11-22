"""Gráficas de resultados (matplotlib, sin pantalla)."""

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

SURFACE = "#fcfcfb"
INK = "#0b0b0b"
INK2 = "#52514e"
GRID = "#e4e3df"
SERIES = {1: "#2a78d6", 2: "#eb6834", 3: "#1baf7a"}  # azul, naranja, aqua (validada)


def _ax(title: str, xlabel: str, ylabel: str):
    fig, ax = plt.subplots(figsize=(7.2, 4.4), dpi=150, facecolor=SURFACE)
    ax.set_facecolor(SURFACE)
    ax.set_title(title, loc="left", color=INK, fontsize=12, fontweight="bold")
    ax.set_xlabel(xlabel, color=INK2)
    ax.set_ylabel(ylabel, color=INK2)
    ax.grid(axis="y", color=GRID, linewidth=0.8)
    ax.set_axisbelow(True)
    for side in ("top", "right", "left"):
        ax.spines[side].set_visible(False)
    ax.spines["bottom"].set_color(GRID)
    ax.tick_params(colors=INK2, length=0)
    return fig, ax


def _linea(ax, x, y, hw, color, label, estilo="-"):
    ax.errorbar(
        x, y, yerr=hw, color=color, linewidth=2, linestyle=estilo, marker="o",
        markersize=8, markeredgecolor=SURFACE, markeredgewidth=2, capsize=3,
        elinewidth=1.2, label=label,
    )
    ax.annotate(label, (x[-1], y[-1]), xytext=(8, 0), textcoords="offset points",
                color=INK, fontsize=9, va="center")


def _guardar(fig, ax, path, leyenda=True):
    if leyenda:
        ax.legend(frameon=False, labelcolor=INK2, fontsize=9, loc="upper left")
    ax.margins(x=0.12)
    fig.tight_layout()
    fig.savefig(path, facecolor=SURFACE)
    plt.close(fig)


def plot_delay_vs_flow(flows, delays: dict, path: str, titulo_extra: str = "") -> None:
    """Retraso medio (s) contra flujo, una línea por velocidad deseada.

    `delays[v0] = (medias, semianchos)` alineados con `flows`.
    """
    fig, ax = _ax("Tiempo perdido por tráfico" + titulo_extra, "Flujo por sentido (veh/h)",
                  "Retraso sobre el tiempo libre (s)")
    for i, (v0, (m, hw)) in enumerate(delays.items(), start=1):
        _linea(ax, flows, m, hw, SERIES[i], f"{v0:g} km/h")
    _guardar(fig, ax, path)


def plot_gain_vs_flow(flows, gain, hw, ideal: float, path: str, v_slow: float, v_fast: float) -> None:
    """Tiempo ganado al ir a v_fast en vez de v_slow, contra flujo, con la ganancia ideal."""
    fig, ax = _ax(f"Tiempo que se gana al ir a {v_fast:g} en vez de {v_slow:g} km/h",
                  "Flujo por sentido (veh/h)", "Tiempo ganado (s)")
    ax.axhline(ideal, color=INK2, linewidth=1.5, linestyle="--", label="Ideal (vía libre)")
    _linea(ax, flows, gain, hw, SERIES[1], "Con tráfico y rebases")
    ax.set_ylim(0, ideal * 1.15)
    ax.legend(frameon=False, labelcolor=INK2, fontsize=9, loc="center right")
    _guardar(fig, ax, path, leyenda=False)


def plot_time_vs_speed(speeds, times, hw, ideal_times, path: str, flow: float) -> None:
    """Tiempo de viaje contra velocidad deseada, medido contra el ideal L/v0."""
    fig, ax = _ax(f"Tiempo de viaje según velocidad deseada ({flow:g} veh/h por sentido)",
                  "Velocidad deseada (km/h)", "Tiempo de viaje (s)")
    ax.plot(speeds, ideal_times, color=INK2, linewidth=1.5, linestyle="--", label="Ideal (L / v0)")
    _linea(ax, speeds, times, hw, SERIES[1], "Simulado")
    ax.legend(frameon=False, labelcolor=INK2, fontsize=9, loc="upper right")
    _guardar(fig, ax, path, leyenda=False)
