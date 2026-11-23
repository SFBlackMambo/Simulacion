import collections

import numpy as np
import pytest

from trafico import config as cfgmod
from trafico.drivers import DriverModel
from trafico.road import Road
from trafico.simulation import SimConfig, build_road, run_simulation
from trafico.vehicle import Vehicle

BASE = SimConfig(length=10000, flow_per_hour=300, warmup=600, n_probes=6)


def test_reparto_de_tipos():
    m = DriverModel(share_cautious=0.3, share_aggressive=0.2)
    rng = np.random.default_rng(1)
    tipos = collections.Counter()
    for i in range(5000):
        v = Vehicle(i, 30.0)
        m.assign(v, rng)
        tipos[v.driver] += 1
    assert abs(tipos["prudente"] / 5000 - 0.3) < 0.03
    assert abs(tipos["agresivo"] / 5000 - 0.2) < 0.03


def test_factores_e_impaciencia():
    m = DriverModel(share_aggressive=1.0, impatience_after=60, impatience_full=100, impatience_floor=0.5)
    v = Vehicle(0, 30.0)
    v.driver = "agresivo"
    assert m.guard_factor(v) == pytest.approx(0.5)
    v.t_stuck = 110  # 50 s más allá del umbral: a mitad de camino
    assert m.guard_factor(v) == pytest.approx(0.5 * 0.75)
    v.t_stuck = 1000
    assert m.guard_factor(v) == pytest.approx(0.25)
    v.driver = "normal"
    v.t_stuck = 0
    assert m.guard_factor(v) == 1.0


def test_intervalo_idm_por_tipo():
    cfg = cfgmod.set_param(cfgmod.set_param(BASE, "prudentes", 0.5), "agresivos", 0.5)
    road = build_road(cfg, 1)
    road.run(600)
    Ts = {v.driver: (v.idm or road.idm).T for v in road.vehicles}
    assert Ts["prudente"] == pytest.approx(1.5 * 1.3)
    assert Ts["agresivo"] == pytest.approx(1.5 * 0.7)


def test_agresivos_rebasan_mas_que_prudentes():
    cfg = cfgmod.set_param(cfgmod.set_param(BASE, "prudentes", 0.4), "agresivos", 0.4)
    por = collections.defaultdict(list)
    col = 0
    for seed in (1, 2, 3):
        r = run_simulation(cfg, 130, seed)
        col += r.collisions
        for t in r.trips:
            if not t["sonda"] and t["viaje_completo"]:
                por[t["conductor"]].append(t["rebases"])
    assert np.mean(por["agresivo"]) > np.mean(por["prudente"])
    assert col == 0


def test_tiempo_atrapado():
    road = Road(length=4000, dt=0.2)
    road.place(60 / 3.6, 500.0)
    b = road.place(120 / 3.6, 450.0, v=60 / 3.6)
    road.run(30)
    assert b.t_stuck == pytest.approx(30, abs=1)
