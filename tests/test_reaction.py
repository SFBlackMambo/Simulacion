import numpy as np
import pytest

from trafico import config as cfgmod
from trafico.idm import IDMParams, hdm_acceleration, idm_acceleration
from trafico.road import Road
from trafico.simulation import SimConfig, run_simulation


def test_hdm_con_un_lider_es_el_idm():
    p = IDMParams()
    assert hdm_acceleration(25, 30, [(40, 22)], p) == pytest.approx(idm_acceleration(25, 30, 40, 22, p))
    assert hdm_acceleration(25, 30, [], p) == pytest.approx(idm_acceleration(25, 30, None, None, p))


def test_hdm_equilibrio_igual_que_idm():
    """Con todos a la misma velocidad y huecos iguales, la aceleración es la misma."""
    p = IDMParams()
    s = 40.0
    lideres = [(s, 22.0), (2 * s + 4.5, 22.0), (3 * s + 9.0, 22.0)]
    a_hdm = hdm_acceleration(22, 30, lideres, p)
    a_idm = idm_acceleration(22, 30, s, 22, p)
    assert a_hdm == pytest.approx(a_idm, abs=0.05)


def _peloton(tau):
    road = Road(length=30000, dt=0.2, reaction_time=tau)
    lider = road.place(80 / 3.6, 3000.0)
    seg = [road.place(120 / 3.6, 3000.0 - 40 * (i + 1), v=80 / 3.6) for i in range(10)]
    v_ult = []
    for k in range(int(600 / 0.2)):
        if 1000 <= k < 1025:
            lider.v0 = 60 / 3.6
        elif k == 1025:
            lider.v0 = 80 / 3.6
        road.step()
        if k > 1000:
            v_ult.append(seg[-1].v * 3.6)
    return road, np.array(v_ult)


@pytest.mark.parametrize("tau", [0.6, 1.0])
def test_peloton_estable_con_reaccion(tau):
    road, v = _peloton(tau)
    assert road.collisions == 0
    assert v.min() > 60  # el frenón no crece hasta parar a los de atrás
    assert v[-200:].std() < 1.0  # vuelve a estabilizarse


def test_la_reaccion_retrasa_la_respuesta():
    def v_tras(tau, pasos=8):
        road = Road(length=5000, dt=0.2, reaction_time=tau)
        a = road.place(25.0, 1000.0)
        b = road.place(30.0, 900.0, v=30.0)  # se acerca a uno más lento
        a.v0 = 25.0
        for _ in range(pasos):
            road.step()
        return b.v

    # con reacción, a los 1.6 s todavía no ha frenado tanto como sin ella
    assert v_tras(1.0) > v_tras(0.0)


def test_reaccion_cero_colisiones():
    cfg = SimConfig(length=8000, flow_per_hour=300, warmup=500, n_probes=4, trazado="pocas")
    for k, v in (("reaccion", 1.0), ("camiones", 0.2), ("overtaking.t_lane_change", 3)):
        cfg = cfgmod.set_param(cfg, k, v)
    for seed in (1, 2):
        r = run_simulation(cfg, 130, seed)
        assert r.collisions == 0 and r.emergency_vehicles == 0
