import pytest

from trafico import config as cfgmod
from trafico.overtaking import OvertakeParams
from trafico.recorder import REBASE_FIN, REBASE_INICIO, Recorder
from trafico.road import Road
from trafico.simulation import SimConfig, run_simulation


def test_cambio_de_carril_gradual():
    from trafico.vehicle import Vehicle

    v = Vehicle(0, 30.0)
    v.change_lane(1, 3.0)
    assert v.lane == 1 and v.lane_prev == 0 and v.lc == 0.0
    assert v.occupies(0) and v.occupies(1)
    v.lc = 0.4
    v.change_lane(0, 3.0)  # vuelve atrás a mitad del cambio
    assert v.lane == 0 and v.lc == pytest.approx(0.6)
    v2 = Vehicle(1, 30.0)
    v2.change_lane(1, 0.0)
    assert v2.lane == 1 and v2.lc == 1.0 and not v2.occupies(0)


def _escena(t_lc):
    rec = Recorder(snapshot_interval=None)
    road = Road(length=5000, dt=0.2, overtaking=OvertakeParams(t_lane_change=t_lc), recorder=rec)
    road.place(60 / 3.6, 600.0)
    rapido = road.place(120 / 3.6, 500.0, v=60 / 3.6)
    ocupa_dos, max_lc_pasos = 0, 0
    pasos = 0
    while rapido.x < 2500 and road.t < 400:
        road.step()
        if rapido.lc < 1.0:
            pasos += 1
            ocupa_dos += 1
            grupos = road._groups()
            assert rapido in grupos[(0, 1)] and rapido in grupos[(1, 1)]
        else:
            max_lc_pasos = max(max_lc_pasos, pasos)
            pasos = 0
    return road, rec, rapido, ocupa_dos, max_lc_pasos


def test_rebase_con_cambio_de_carril_de_3_s():
    road, rec, rapido, ocupa_dos, max_pasos = _escena(3.0)
    tipos = [e["tipo"] for e in rec.events]
    assert REBASE_INICIO in tipos and REBASE_FIN in tipos
    assert rapido.overtakes == 1
    assert max_pasos == pytest.approx(3.0 / 0.2, abs=1)  # cada cambio dura ~3 s
    assert ocupa_dos >= 2 * 14  # salir y volver
    assert road.collisions == 0


def test_seguidor_ve_al_que_sale():
    """Mientras sale, el de atrás en el carril propio lo sigue teniendo delante."""
    road = Road(length=3000, dt=0.2, overtaking=OvertakeParams(t_lane_change=3.0))
    a = road.place(25.0, 1000.0)
    a.change_lane(1, 3.0)
    b = road.place(25.0, 960.0)
    g = road._groups()
    assert g[(0, 1)].index(a) < g[(0, 1)].index(b)


def test_con_trafico_y_cambio_lento_cero_colisiones():
    for tr in ("recta", "pocas"):
        cfg = cfgmod.set_param(SimConfig(length=8000, flow_per_hour=300, warmup=500, n_probes=4, trazado=tr),
                               "overtaking.t_lane_change", 3)
        cfg = cfgmod.set_param(cfg, "camiones", 0.2)
        r = run_simulation(cfg, 130, 2)
        assert r.collisions == 0 and r.emergency_vehicles == 0
        assert sum(t["rebases"] for t in r.trips) > 0
