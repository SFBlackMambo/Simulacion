import pytest

from trafico.arrivals import PoissonArrivals
from trafico.simulation import SimConfig, build_road, run_simulation


def test_poisson_con_limite_genera_exactamente_n():
    src = PoissonArrivals(3600, seed=1, max_count=7)
    out = src.due(10_000)
    assert len(out) == 7 and src.exhausted
    assert src.due(20_000) == []


def test_lleno_arranca_con_n_por_sentido_sin_colisiones():
    cfg = SimConfig(length=10_000, mode="lleno", n_vehicles=60, warmup=0, n_probes=0)
    road = build_road(cfg, seed=1)
    assert sum(v.direction == 1 for v in road.vehicles) == 60
    assert sum(v.direction == -1 for v in road.vehicles) == 60
    assert all(not v.full_trip for v in road.vehicles)
    road.run(900)
    assert road.collisions == 0
    for d in (1, -1):  # la cantidad se mantiene (en la carretera o esperando para entrar)
        en_via = sum(v.direction == d for v in road.vehicles)
        assert en_via + len(road._pending[d]) == 60
    assert len(road.finished) > 60  # hubo recambio
    assert any(v.full_trip for v in road.finished)


def test_lleno_demasiados_vehiculos_da_error():
    cfg = SimConfig(length=1_000, mode="lleno", n_vehicles=500)
    with pytest.raises(ValueError):
        build_road(cfg, seed=1)


def test_total_salen_exactamente_n_por_sentido_y_termina():
    cfg = SimConfig(length=5_000, mode="total", n_vehicles=40, flow_per_hour=400, warmup=0, n_probes=0)
    res = run_simulation(cfg, 120, seed=3)
    assert res.background_finished == 80
    assert sum(t["sentido"] == 1 for t in res.trips) == 40
    assert all(t["viaje_completo"] for t in res.trips)
    assert res.collisions == 0


def test_total_con_sondas():
    cfg = SimConfig(length=5_000, mode="total", n_vehicles=30, flow_per_hour=400, warmup=100,
                    n_probes=3, probe_spacing=60)
    res = run_simulation(cfg, 130, seed=3)
    assert len(res.probes) == 3
    assert res.background_finished == 60


def test_flujo_con_duracion_sin_sondas():
    cfg = SimConfig(length=5_000, flow_per_hour=300, warmup=0, duration=1200, n_probes=0)
    res = run_simulation(cfg, 120, seed=3)
    assert res.probes == []
    assert res.background_finished > 100


def test_modo_desconocido():
    with pytest.raises(ValueError):
        build_road(SimConfig(mode="otro"), seed=1)
