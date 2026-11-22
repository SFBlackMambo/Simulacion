import math

import pytest

from trafico.experiments import run_replicas
from trafico.simulation import SimConfig
from trafico.stats import ideal_gain, mean_ci, paired_difference, summarize, t_critical


def test_mean_ci_conocido():
    m, hw = mean_ci([1.0, 2.0, 3.0, 4.0, 5.0])
    assert m == 3.0
    assert hw == pytest.approx(2.776 * math.sqrt(2.5 / 5))


def test_mean_ci_casos_borde():
    assert math.isnan(mean_ci([])[0])
    m, hw = mean_ci([7.0])
    assert m == 7.0 and math.isnan(hw)


def test_t_critical():
    assert t_critical(4) == 2.776
    assert t_critical(22) == 2.086  # cota conservadora (df 20)
    assert t_critical(100) == 1.96
    assert math.isnan(t_critical(0))


def test_ganancia_ideal_120_vs_130():
    assert ideal_gain(20_000, 120, 130) == pytest.approx(46.15, abs=0.05)


def test_sin_trafico_la_diferencia_pareada_es_la_ideal():
    cfg = SimConfig(length=6_000, flow_per_hour=0, warmup=10, n_probes=3, probe_spacing=60)
    res = run_replicas(cfg, [120, 130], [1, 2, 3])
    gain, hw = paired_difference(res, 120, 130, [1, 2, 3])
    assert gain == pytest.approx(ideal_gain(6_000, 120, 130), abs=0.5)
    s = summarize(res, 130, [1, 2, 3])
    assert s["delay"] == pytest.approx(0, abs=0.5)


def test_con_trafico_la_ganancia_es_menor_que_la_ideal():
    cfg = SimConfig(length=10_000, flow_per_hour=350, warmup=900, n_probes=6, probe_spacing=100)
    seeds = [1, 2, 3, 4]
    res = run_replicas(cfg, [120, 130], seeds, workers=4)
    gain, hw = paired_difference(res, 120, 130, seeds)
    assert 0 < gain < ideal_gain(10_000, 120, 130) + 1
