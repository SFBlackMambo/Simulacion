from trafico import config as cfgmod
from trafico.fleet import CAMION, TruckParams
from trafico.overtaking import OvertakeParams
from trafico.recorder import REBASE_INICIO, Recorder
from trafico.road import Road
from trafico.simulation import SimConfig, run_simulation


def _escena(lider_camion=False, **kw):
    """Un lento y dos rápidos detrás, separados ~3 s; nadie de frente."""
    rec = Recorder(snapshot_interval=None)
    road = Road(length=6000, dt=0.2, overtaking=OvertakeParams(**kw), recorder=rec, trucks=TruckParams())
    road.place(60 / 3.6, 1000.0, kind=CAMION if lider_camion else "auto")
    a = road.place(120 / 3.6, 975.0, v=60 / 3.6)
    b = road.place(120 / 3.6, 925.0, v=60 / 3.6)
    while b.x < 4000 and road.t < 400:
        road.step()
    return road, rec, a, b


def _inicios(rec):
    return [e for e in rec.events if e["tipo"] == REBASE_INICIO]


def test_sin_cadena_el_segundo_espera():
    road, rec, a, b = _escena()
    ini = _inicios(rec)
    assert all(e["en_cadena"] == 0 for e in ini)
    t_a = min(e["t"] for e in ini if e["id"] == a.id)
    t_b = min(e["t"] for e in ini if e["id"] == b.id)
    assert t_b > t_a + 5  # no salió mientras el primero rebasaba
    assert road.collisions == 0


def test_con_cadena_salen_casi_juntos():
    road, rec, a, b = _escena(convoy=True)
    ini = _inicios(rec)
    assert any(e["en_cadena"] == 1 and e["id"] == b.id for e in ini)
    assert b.convoy_overtakes >= 1
    assert a.overtakes >= 1 and b.overtakes >= 1
    assert road.collisions == 0


def test_detras_de_un_camion_cercano_no_ve():
    from trafico.overtaking import _visible

    road = Road(length=6000, overtaking=OvertakeParams(blocked_view=True), trucks=TruckParams())
    cam = road.place(20.0, 1000.0, kind=CAMION)
    auto = road.place(20.0, 1000.0 - 16.5 - 30.0)  # 30 m detrás: 1.5 s
    assert _visible(road, road.overtaking, auto, cam, []) == 0.0
    lejos = road.place(20.0, 1000.0 - 16.5 - 80.0)  # 4 s detrás: ve
    assert _visible(road, road.overtaking, lejos, cam, []) > 1000
    coche = road.place(20.0, 2000.0)
    pegado = road.place(20.0, 2000.0 - 4.5 - 20.0)  # 1 s detrás de un auto
    assert _visible(road, road.overtaking, pegado, coche, []) == 500.0


def test_vista_tapada_sin_ella_no_cambia_nada():
    road, rec, a, b = _escena(convoy=True, blocked_view=False)
    road2, rec2, a2, b2 = _escena(convoy=True, blocked_view=False)
    assert [e["t"] for e in rec.events] == [e["t"] for e in rec2.events]


def test_cadena_con_trafico_cero_colisiones():
    cfg = SimConfig(length=8000, flow_per_hour=300, warmup=500, n_probes=4)
    for k, v in (("overtaking.t_lane_change", 3), ("camiones", 0.15), ("overtaking.convoy", 1),
                 ("overtaking.blocked_view", 1)):
        cfg = cfgmod.set_param(cfg, k, v)
    for seed in (1, 2):
        r = run_simulation(cfg, 130, seed)
        assert r.collisions == 0 and r.emergency_vehicles == 0
