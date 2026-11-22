"""Estadística de las réplicas: medias, intervalos de confianza y diferencias pareadas."""

import math

from .simulation import RunResult

# t de Student, dos colas, 95 %
_T95 = {
    1: 12.706, 2: 4.303, 3: 3.182, 4: 2.776, 5: 2.571, 6: 2.447, 7: 2.365, 8: 2.306,
    9: 2.262, 10: 2.228, 11: 2.201, 12: 2.179, 13: 2.160, 14: 2.145, 15: 2.131,
    16: 2.120, 17: 2.110, 18: 2.101, 19: 2.093, 20: 2.086, 25: 2.060, 30: 2.042,
}


def t_critical(df: int) -> float:
    """Valor crítico t al 95 % (dos colas) con `df` grados de libertad."""
    if df < 1:
        return math.nan
    if df in _T95:
        return _T95[df]
    if df > 30:
        return 2.0 if df <= 60 else 1.96
    return _T95[max(k for k in _T95 if k < df)]  # df entre 20 y 30: cota conservadora


def mean_ci(values: list[float]) -> tuple[float, float]:
    """Media y semiancho del intervalo de confianza del 95 %."""
    n = len(values)
    if n == 0:
        return math.nan, math.nan
    mean = sum(values) / n
    if n == 1:
        return mean, math.nan
    var = sum((v - mean) ** 2 for v in values) / (n - 1)
    return mean, t_critical(n - 1) * math.sqrt(var / n)


def _por_semilla(results: dict, v0: float, seeds: list[int], attr: str) -> list[float]:
    """Media por semilla (promedio sobre las sondas de cada corrida)."""
    out = []
    for s in seeds:
        probes = results[(v0, s)].probes
        out.append(sum(getattr(p, attr) for p in probes) / len(probes))
    return out


def summarize(results: dict[tuple[float, int], RunResult], v0: float, seeds: list[int]) -> dict:
    """Resumen de una velocidad de sonda: media ± IC95 entre semillas."""
    tt, tt_hw = mean_ci(_por_semilla(results, v0, seeds, "travel_time"))
    dl, dl_hw = mean_ci(_por_semilla(results, v0, seeds, "delay"))
    ov, _ = mean_ci(_por_semilla(results, v0, seeds, "overtakes"))
    sl, _ = mean_ci(_por_semilla(results, v0, seeds, "t_slow"))
    return {
        "v0": v0, "travel_time": tt, "travel_time_hw": tt_hw,
        "delay": dl, "delay_hw": dl_hw, "overtakes": ov, "t_slow": sl,
    }


def paired_difference(
    results: dict[tuple[float, int], RunResult],
    v_slow: float,
    v_fast: float,
    seeds: list[int],
    attr: str = "travel_time",
) -> tuple[float, float]:
    """Tiempo ganado por ir a `v_fast` en vez de `v_slow` (segundos, positivo = gana).

    Se empareja sonda con sonda (mismo índice y misma semilla, por tanto mismo
    instante de entrada y mismo tráfico de fondo), se promedia por semilla y se
    calcula el IC95 entre semillas.
    """
    por_semilla = []
    for s in seeds:
        a, b = results[(v_slow, s)].probes, results[(v_fast, s)].probes
        diffs = [pa.__getattribute__(attr) - pb.__getattribute__(attr) for pa, pb in zip(a, b)]
        por_semilla.append(sum(diffs) / len(diffs))
    return mean_ci(por_semilla)


def ideal_gain(length: float, v_slow_kmh: float, v_fast_kmh: float) -> float:
    """Tiempo ganado en vía libre (s): L/v_slow - L/v_fast."""
    return length / (v_slow_kmh / 3.6) - length / (v_fast_kmh / 3.6)
