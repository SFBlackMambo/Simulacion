import math

import pytest

from trafico import config as cfgmod
from trafico.geometry import Geometry
from trafico.idm import IDMParams
from trafico.road import Road
from trafico.simulation import SimConfig, free_time, geometry_from_config, run_simulation

L = 6_000
UNA = ((3000.0, 3400.0, 150.0),)


def _solo(geo, direction, v0_kmh=120):
    road = Road(length=L, dt=0.2, geometry=geo)
    v = road.place(v0_kmh / 3.6, 0.0, direction=direction)
    v_curva = 0.0
    while v.x < L and road.t < 2000:
        road.step()
        if 3000 <= road.position(v) < 3400:
            v_curva = max(v_curva, v.v)
    return road, v, v_curva


@pytest.mark.parametrize("direction", [1, -1])
def test_nadie_supera_la_velocidad_de_curva(direction):
    geo = Geometry(L, UNA)
    road, v, v_curva = _solo(geo, direction)
    limite = math.sqrt(geo.a_lat * 150.0)
    assert v_curva <= limite + 0.05
    assert v_curva >= limite - 0.5  # y sí llega a ella (no frena de más)
    assert v.catchups == 0  # frenar por la curva no es "alcanzar a alguien"


def test_frena_antes_de_entrar():
    geo = Geometry(L, UNA)
    assert geo.limit(1, 2500) > geo.limit(1, 2900) > geo.limit(1, 3100) - 1e-9
    assert geo.limit(1, 1000) > 140 / 3.6  # lejos de la curva no limita a nadie
    assert geo.limit(1, 4000) == math.inf  # después de la curva no hay límite
    assert geo.limit(-1, L - 3200) == pytest.approx(math.sqrt(2.0 * 150))


def test_tiempo_libre_con_curvas_coincide_con_la_simulacion():
    geo = Geometry(L, UNA)
    road, v, _ = _solo(geo, 1)
    assert geo.free_time(120 / 3.6, 1, IDMParams(), 0.2) == pytest.approx(v.travel_time, abs=0.21)
    assert geo.free_time(120 / 3.6, 1, IDMParams(), 0.2) > L / (120 / 3.6) + 10
    assert geo.free_time_interp(120 / 3.6, 1, IDMParams(), 0.2) == pytest.approx(v.travel_time, abs=0.5)


def test_curvas_invalidas():
    with pytest.raises(ValueError):
        Geometry(1000, ((500, 400, 100),))
    with pytest.raises(ValueError):
        Geometry(1000, ((100, 400, 100), (300, 600, 100)))


def test_sin_curvas_es_recta():
    cfg = SimConfig(length=5000)
    assert geometry_from_config(cfg) is None
    assert free_time(cfg, 30.0) == pytest.approx(5000 / 30.0)


def test_sondas_con_curvas_miden_contra_el_ideal_con_curvas():
    cfg = SimConfig(length=6000, flow_per_hour=0, warmup=10, n_probes=2, probe_spacing=60, curves=UNA)
    r = run_simulation(cfg, 120, seed=1)
    for p in r.probes:
        assert p.delay == pytest.approx(0, abs=0.5)
        assert p.free_time > 6000 / (120 / 3.6)


def test_config_con_curvas_va_y_vuelve_por_json(tmp_path):
    cfg = SimConfig(curves=((1000.0, 1500.0, 300.0),))
    cfgmod.save(cfg, tmp_path / "c.json")
    assert cfgmod.load(tmp_path / "c.json")[0] == cfg
