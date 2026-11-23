import math

import pytest

from trafico import config as cfgmod
from trafico.fleet import CAMION, TruckParams
from trafico.geometry import RELIEVES, Geometry, build_relieve, describe
from trafico.road import Road
from trafico.simulation import SimConfig, free_time, geometry_from_config, run_simulation
from trafico.slopes import AUTO_GRADES, GradeResponse, downhill_speed, speed_limit, uphill_speed

CAM = GradeResponse(power_w_kg=7.5, engine_brake=True)


def test_velocidades_de_camion_por_pendiente():
    assert uphill_speed(7.5, 0.03) * 3.6 == pytest.approx(68.8, abs=0.5)
    assert uphill_speed(7.5, 0.06) * 3.6 == pytest.approx(39.3, abs=0.5)
    assert uphill_speed(7.5, 0.08) * 3.6 == pytest.approx(30.6, abs=0.5)
    assert downhill_speed(CAM, -0.03) == math.inf
    assert downhill_speed(CAM, -0.05) * 3.6 == pytest.approx(78)
    assert downhill_speed(CAM, -0.09) * 3.6 == pytest.approx(54)
    assert downhill_speed(CAM, -0.20) * 3.6 == pytest.approx(40)  # mínimo
    assert speed_limit(AUTO_GRADES, 0.06) > 140 / 3.6  # un auto casi no lo nota
    assert speed_limit(AUTO_GRADES, -0.09) == math.inf


@pytest.mark.parametrize("pct, esperado", [(6, 39.3), (-7, 66.0)])
def test_camion_solo_en_pendiente(pct, esperado):
    geo = Geometry(8000, grades=((1000.0, 7000.0, pct / 100),))
    road = Road(length=8000, dt=0.2, geometry=geo, trucks=TruckParams())
    v = road.place(105 / 3.6, 0.0, kind=CAMION)
    auto = road.place(105 / 3.6, 0.0, direction=-1)  # el otro sentido ve la pendiente contraria
    vs, va = [], []
    while v.x < 8000 and road.t < 3000:
        road.step()
        if 5000 < v.x < 6900:
            vs.append(v.v * 3.6)
        if 2000 < auto.x < 6000:
            va.append(auto.v * 3.6)
    assert min(vs) == pytest.approx(esperado, abs=0.5)
    assert min(va) == pytest.approx(105, abs=0.5)
    assert v.catchups == 0  # frenar por la pendiente no es "alcanzar a alguien"


def test_pendiente_en_cada_sentido():
    geo = Geometry(5000, grades=((1000.0, 2000.0, 0.05),))
    assert geo.grade(1, 1500) == pytest.approx(0.05)
    assert geo.grade(-1, 5000 - 1500) == pytest.approx(-0.05)
    assert geo.grade(1, 500) == 0
    assert geo.elevation(2000) == pytest.approx(50)


def test_tiempo_libre_con_pendientes():
    cfg = SimConfig(length=8000, grades=((1000.0, 7000.0, 0.06),))
    t_auto = free_time(cfg, 105 / 3.6)
    t_cam = free_time(cfg, 105 / 3.6, kind=CAMION)
    assert t_auto == pytest.approx(8000 / (105 / 3.6), abs=1)
    assert t_cam > 6000 / (39.3 / 3.6)


@pytest.mark.parametrize("nombre", list(RELIEVES))
def test_relieves_generados(nombre):
    a = build_relieve(nombre, 20000, 3)
    assert a == build_relieve(nombre, 20000, 3)
    Geometry(20000, grades=a)
    r = RELIEVES[nombre]
    for _, _, g in a:
        assert r.pct_min - 1e-6 <= abs(100 * g) <= r.pct_max + 1e-6


def test_relieve_y_trazado_juntos():
    cfg = SimConfig(trazado="pocas", relieve="lomerio")
    geo = geometry_from_config(cfg, 1)
    assert geo.curves and geo.grades
    d = describe(geo, cfg.length)
    assert d["pendiente_max_pct"] <= 4.0 and d["curvas"] > 0


def test_sin_trafico_con_pendientes_no_hay_retraso():
    cfg = SimConfig(length=8000, flow_per_hour=0, warmup=10, n_probes=2, probe_spacing=30, relieve="montanoso")
    r = run_simulation(cfg, 130, seed=2)
    assert all(abs(p.delay) < 0.5 for p in r.probes)


def test_montana_con_camiones_cero_colisiones():
    cfg = cfgmod.set_param(SimConfig(length=8000, flow_per_hour=250, warmup=500, n_probes=4,
                                     relieve="montanoso"), "camiones", 0.25)
    r = run_simulation(cfg, 130, 1)
    assert r.collisions == 0 and r.emergency_vehicles == 0
    cam = [t for t in r.trips if t["clase"] == CAMION and t["viaje_completo"]]
    assert cam and all(t["retraso"] > -1 for t in cam)


def test_pendientes_desde_texto_en_porcentaje(tmp_path):
    cfg = cfgmod.set_param(SimConfig(), "pendientes", "1000:3000:5;4000:5000:-3")
    assert cfg.grades == ((1000.0, 3000.0, 0.05), (4000.0, 5000.0, -0.03))
    cfgmod.save(cfg, tmp_path / "c.json")
    assert cfgmod.load(tmp_path / "c.json")[0] == cfg
