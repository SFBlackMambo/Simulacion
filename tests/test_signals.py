import numpy as np
import pytest

from trafico import config as cfgmod
from trafico.drivers import DriverModel
from trafico.geometry import Geometry
from trafico.recorder import REBASE_INICIO, Recorder
from trafico.road import Road
from trafico.simulation import SimConfig, build_road, free_time, run_simulation

BASE = SimConfig(length=8000, flow_per_hour=250, warmup=500, n_probes=4)


def test_limite_por_tramo_y_anticipacion():
    geo = Geometry(5000, limits=((2000.0, 3000.0, 60.0),))
    assert geo.speed_limit(1, 1000) == np.inf
    assert geo.speed_limit(1, 1950) == pytest.approx(60 / 3.6)  # frena antes de la señal
    assert geo.speed_limit(1, 2500) == pytest.approx(60 / 3.6)
    assert geo.speed_limit(-1, 5000 - 2500) == pytest.approx(60 / 3.6)  # vale en los dos sentidos


def test_quien_respeta_no_pasa_del_limite():
    geo = Geometry(5000, limits=((0.0, 5000.0, 80.0),))
    road = Road(length=5000, dt=0.2, geometry=geo)
    v = road.place(120 / 3.6, 0.0, v=80 / 3.6)
    vmax = 0
    while v.x < 5000:
        road.step()
        vmax = max(vmax, v.v)
    assert vmax * 3.6 <= 80.01


def test_limite_general_y_tiempo_libre():
    cfg = cfgmod.set_param(SimConfig(length=6000), "limite", 90)
    assert free_time(cfg, 130 / 3.6) == pytest.approx(6000 / (90 / 3.6), abs=1)
    assert free_time(cfg, 130 / 3.6, limit_factor=1.2) == pytest.approx(6000 / (108 / 3.6), abs=1)
    assert free_time(cfg, 80 / 3.6) == pytest.approx(6000 / (80 / 3.6), abs=1)


def test_parte_no_respeta_el_limite():
    cfg = cfgmod.set_param(cfgmod.set_param(BASE, "limite", 90), "respetan_limite", 0.6)
    road = build_road(cfg, 1)
    road.run(1200)
    vehs = road.vehicles + road.finished
    excede = [v for v in vehs if v.limit_factor > 1]
    assert 0.25 < len(excede) / len(vehs) < 0.55
    assert all(1.1 <= v.limit_factor <= 1.3 for v in excede)


def test_rasgos_de_conductor_no_cambian_el_trafico():
    a = run_simulation(BASE, 130, 3)
    cfg = cfgmod.set_param(BASE, "respetan_no_rebase", 0.5)  # activa el sorteo, sin zonas no hace nada
    b = run_simulation(cfg, 130, 3)
    assert [t["v0_kmh"] for t in a.trips] == [t["v0_kmh"] for t in b.trips]
    assert [p.travel_time for p in a.probes] == [p.travel_time for p in b.probes]


def _rebases_en_zona(cfg, seeds=(1, 2, 3)):
    ini, col = [], 0
    for seed in seeds:
        rec = Recorder(snapshot_interval=None)
        r = run_simulation(cfg, 130, seed, recorder=rec)
        col += r.collisions
        ini += [e for e in rec.events if e["tipo"] == REBASE_INICIO]
    return col, ini


def test_zona_de_no_rebase():
    cfg = cfgmod.set_param(BASE, "zonas_no_rebase", "2000:6000")
    col, ini = _rebases_en_zona(cfg)
    # quien respeta no empieza un rebase que invada la zona: en sentido + no se empieza dentro
    assert not any(e["sentido"] == 1 and 2000 <= e["x"] < 6000 for e in ini)
    assert col == 0
    col2, ini2 = _rebases_en_zona(cfgmod.set_param(cfg, "respetan_no_rebase", 0.3))
    dentro = [e for e in ini2 if e["sentido"] == 1 and 2000 <= e["x"] < 6000]
    assert dentro, "quien no respeta sí rebasa en la zona"
    assert col2 == 0


def test_con_limite_cero_emergencias():
    cfg = cfgmod.set_param(cfgmod.set_param(SimConfig(length=8000, flow_per_hour=250, warmup=500, n_probes=4,
                                                      trazado="pocas"), "limite", 90), "respetan_limite", 0.7)
    for seed in (1, 2):
        r = run_simulation(cfg, 130, seed)
        assert r.collisions == 0 and r.emergency_vehicles == 0


def test_zonas_por_visibilidad_marcadas():
    cfg = cfgmod.set_param(SimConfig(trazado="muchas"), "no_rebase_sin_visibilidad", 1)
    from trafico.simulation import geometry_from_config

    geo = geometry_from_config(cfg, 1)
    assert geo.has_no_pass
    assert any(geo.marked_no_pass(s) for s in range(0, 20000, 50))


def test_driver_model_inactivo_por_defecto():
    assert not DriverModel().active
