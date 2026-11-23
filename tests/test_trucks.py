import numpy as np
import pytest

from trafico import config as cfgmod
from trafico.arrivals import PoissonArrivals
from trafico.fleet import CAMION, TruckParams
from trafico.road import Road
from trafico.simulation import SimConfig, build_road, run_simulation


def test_distribucion_de_velocidad_de_camiones():
    rng = np.random.default_rng(1)
    t = TruckParams(share=1.0)
    v = np.array([t.sample_kmh(rng) for _ in range(40_000)])
    h, e = np.histogram(v, bins=np.arange(50, 130, 1))
    assert 103 <= e[h.argmax()] <= 107  # la mayoría cerca de 105
    entre = ((v >= 90) & (v <= 110)).mean()
    assert 0.92 < entre < 0.97
    assert 0.01 < (v < 90).mean() < 0.03  # pocos lentos (incluye anomalías)
    assert 0.02 < (v > 110).mean() < 0.06
    assert v.max() <= 125 and v.min() >= 50


def test_sin_camiones_no_se_consumen_numeros_aleatorios():
    a = PoissonArrivals(300, seed=4)
    b = PoissonArrivals(300, seed=4, trucks=TruckParams(share=0.0))
    assert a.due(3600) == b.due(3600)


def test_proporcion_de_camiones_y_su_tamano():
    src = PoissonArrivals(3600, seed=2, trucks=TruckParams(share=0.25))
    tipos = [k for _, k in src.due_vehicles(4 * 3600)]
    assert abs(tipos.count(CAMION) / len(tipos) - 0.25) < 0.03
    road = Road(trucks=TruckParams())
    c = road.inject(25.0, kind=CAMION)
    assert c.length == 16.5 and c.idm.a_max == 0.5


def test_camion_solo_acelera_mas_despacio():
    road = Road(length=5000, dt=0.2, trucks=TruckParams())
    auto = road.place(25.0, 0.0, v=10.0)
    cam = road.place(25.0, 0.0, v=10.0, direction=-1, kind=CAMION)
    road.run(10)
    assert cam.v < auto.v


def test_simulacion_con_camiones_sin_colisiones():
    for tr in ("recta", "pocas"):
        cfg = cfgmod.set_param(SimConfig(length=8000, flow_per_hour=300, warmup=500, n_probes=4, trazado=tr),
                               "camiones", "0.3")
        r = run_simulation(cfg, 130, 1)
        assert r.collisions == 0 and r.emergency_vehicles == 0
        cam = [t for t in r.trips if t["clase"] == CAMION]
        assert 0.15 < len(cam) / len(r.trips) < 0.45
        assert all(t["v0_kmh"] <= 125 for t in cam)


def test_lleno_con_camiones():
    cfg = cfgmod.set_param(SimConfig(length=6000, mode="lleno", n_vehicles=30, warmup=0, n_probes=0, duration=300),
                           "camiones", 0.5)
    road = build_road(cfg, 1)
    assert any(v.kind == CAMION for v in road.vehicles)
    road.run(300)
    assert road.collisions == 0


def test_camiones_por_json(tmp_path):
    cfg = cfgmod.set_param(SimConfig(), "trucks.share", 0.2)
    cfgmod.save(cfg, tmp_path / "c.json")
    assert cfgmod.load(tmp_path / "c.json")[0] == cfg
