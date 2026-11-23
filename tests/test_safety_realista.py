from trafico import config as cfgmod
from trafico.overtaking import OvertakeParams, _try_return
from trafico.road import Road
from trafico.simulation import SimConfig, run_simulation
from trafico.vehicle import REBASANDO, REGRESANDO


def test_tope_fisico_de_frenado():
    road = Road(length=3000, dt=0.2, b_physical=9.0)
    road.place(0.1, 1000.0, v=0.0)  # parado
    b = road.place(30.0, 960.0, v=30.0)
    v0 = b.v
    road.step()
    assert (v0 - b.v) / 0.2 <= 9.0 + 1e-9
    sin_tope = Road(length=3000, dt=0.2)
    sin_tope.place(0.1, 1000.0, v=0.0)
    c = sin_tope.place(30.0, 960.0, v=30.0)
    sin_tope.step()
    assert (30.0 - c.v) / 0.2 > 9.0  # sin tope (fases 1 y 2) el IDM puede frenar más


def test_no_sale_si_no_cabe_la_salida():
    p = OvertakeParams(t_lane_change=3.0)
    road = Road(length=6000, dt=0.2, overtaking=p)
    road.place(10 / 3.6, 1000.0)  # casi parado
    b = road.place(120 / 3.6, 980.0, v=60 / 3.6)  # 15 m detrás, mucho más rápido
    road.step()
    assert b.state != REBASANDO


def test_volver_considera_la_diferencia_de_velocidad():
    p = OvertakeParams(return_closing=True)
    road = Road(length=6000, dt=0.2, overtaking=p)
    lento = road.place(30 / 3.6, 1030.0)  # en su carril, delante, muy lento
    r = road.place(90 / 3.6, 1000.0, lane=1)  # rebasando, 25 m detrás del lento
    r.state = REGRESANDO
    r.targets = []
    assert not _try_return(road, p, r, road._groups())  # no se mete delante de él a 60 km/h de diferencia
    p2 = OvertakeParams(return_closing=False)
    road.overtaking = p2
    r.state = REGRESANDO
    assert _try_return(road, p2, r, road._groups())  # la regla vieja sí lo dejaba


def test_no_sale_si_el_peloton_frena():
    p = OvertakeParams(no_start_braking=True)
    road = Road(length=6000, dt=0.2, overtaking=p)
    lider = road.place(60 / 3.6, 1000.0)
    b = road.place(120 / 3.6, 940.0, v=60 / 3.6)
    lider.a_prev = -2.0  # frenando fuerte
    from trafico.overtaking import _start

    lst = road._groups()[(0, 1)]
    assert not _start(road, p, b, lst, lst.index(b))
    lider.a_prev = 0.0
    assert _start(road, p, b, lst, lst.index(b))


def test_realista_en_montana_sin_colisiones():
    cfg = cfgmod.set_param(cfgmod.realista(SimConfig(length=10000, flow_per_hour=200, relieve="montanoso",
                                                     n_probes=5)), "camiones", 0.15)
    for seed in (1, 2):
        r = run_simulation(cfg, 130, seed)
        assert r.collisions == 0
