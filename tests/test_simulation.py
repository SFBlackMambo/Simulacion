import pytest

from trafico.simulation import SimConfig, run_simulation

PEQ = SimConfig(length=8_000, flow_per_hour=250, warmup=600, n_probes=6, probe_spacing=120)


def test_sin_trafico_las_sondas_tardan_L_sobre_v0():
    cfg = SimConfig(length=8_000, flow_per_hour=0, warmup=10, n_probes=4, probe_spacing=60)
    res = run_simulation(cfg, 120, seed=1)
    assert len(res.probes) == 4
    for p in res.probes:
        assert p.travel_time == pytest.approx(p.free_time, abs=1.0)
        assert p.delay == pytest.approx(0, abs=1.0)
    assert res.collisions == 0


def test_misma_semilla_es_reproducible():
    a = run_simulation(PEQ, 120, seed=3)
    b = run_simulation(PEQ, 120, seed=3)
    assert [p.travel_time for p in a.probes] == [p.travel_time for p in b.probes]


def test_numeros_aleatorios_comunes_sondas_entran_en_los_mismos_instantes():
    a = run_simulation(PEQ, 120, seed=3)
    b = run_simulation(PEQ, 130, seed=3)
    assert [round(p.t_entry) for p in a.probes] == [round(p.t_entry) for p in b.probes]
    assert all(p.v0_kmh == 130 for p in b.probes)


def test_distinta_semilla_da_distintos_resultados():
    a = run_simulation(PEQ, 120, seed=3)
    b = run_simulation(PEQ, 120, seed=4)
    assert [p.travel_time for p in a.probes] != [p.travel_time for p in b.probes]


def test_con_trafico_la_sonda_rapida_pierde_tiempo_pero_sigue_ganando_al_lento():
    res120 = run_simulation(PEQ, 120, seed=5)
    res130 = run_simulation(PEQ, 130, seed=5)
    d120 = sum(p.delay for p in res120.probes) / len(res120.probes)
    d130 = sum(p.delay for p in res130.probes) / len(res130.probes)
    assert d120 >= -1.0 and d130 >= -1.0  # nunca más rápido que su tiempo libre
    t120 = sum(p.travel_time for p in res120.probes)
    t130 = sum(p.travel_time for p in res130.probes)
    assert t130 < t120  # ir a 130 sigue siendo más rápido en promedio
    assert (res120.collisions, res130.collisions) == (0, 0)
