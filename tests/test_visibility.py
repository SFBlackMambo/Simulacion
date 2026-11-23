import math

import pytest

from trafico.geometry import Geometry
from trafico.overtaking import OvertakeParams
from trafico.recorder import REBASE_INICIO, Recorder
from trafico.road import Road
from trafico.simulation import SimConfig, run_simulation

L = 6_000
CURVA = ((1500.0, 2500.0, 200.0),)


def test_tabla_de_visibilidad():
    geo = Geometry(L, CURVA, clearance=10.0)
    sc = math.sqrt(8 * 200 * 10)
    assert geo.sight(1, 1000) == pytest.approx(500 + sc, abs=geo.grid)
    assert geo.sight(1, 2000) == pytest.approx(sc)
    assert geo.sight(1, 3000) == math.inf  # pasada la curva, recta hasta el final
    # el otro sentido ve la misma curva desde su lado
    assert geo.sight(-1, L - 2000) == pytest.approx(sc)
    assert geo.sight(-1, L - 3000) == pytest.approx(500 + sc, abs=geo.grid)
    assert not geo.can_pass_at(2000)
    assert geo.can_pass_at(4000)


def _escena(curvas):
    """Uno rápido detrás de uno lento justo antes de una curva; nadie de frente."""
    geo = Geometry(L, curvas) if curvas else None
    rec = Recorder(snapshot_interval=None)
    road = Road(length=L, dt=0.2, overtaking=OvertakeParams(), geometry=geo, recorder=rec)
    road.place(60 / 3.6, 1250.0)
    rapido = road.place(120 / 3.6, 1150.0, v=60 / 3.6)
    while rapido.x < 3500 and road.t < 600:
        road.step()
    return road, rec


def test_en_recta_rebasa_enseguida():
    road, rec = _escena(())
    inicios = [e["x"] for e in rec.events if e["tipo"] == REBASE_INICIO]
    assert inicios and inicios[0] < 1500


def test_sin_visibilidad_espera_a_salir_de_la_curva():
    road, rec = _escena(CURVA)
    inicios = [e["x"] for e in rec.events if e["tipo"] == REBASE_INICIO]
    assert inicios, "debe rebasar en algún momento"
    # la maniobra completa necesita varios cientos de metros: no cabe en la curva
    assert all(x < 1000 or x >= 2400 for x in inicios)
    assert road.collisions == 0


def test_con_curvas_y_trafico_cero_colisiones_y_cero_emergencias():
    curvas = ((1500.0, 1900.0, 150.0), (3500.0, 4200.0, 400.0), (6000.0, 6300.0, 250.0))
    for seed in (1, 2):
        cfg = SimConfig(length=8_000, flow_per_hour=300, warmup=400, n_probes=4, probe_spacing=60, curves=curvas)
        r = run_simulation(cfg, 130, seed)
        assert r.collisions == 0
        assert r.emergency_vehicles == 0


def test_mas_despeje_permite_mas_rebases():
    curvas = ((1000.0, 1800.0, 600.0), (3000.0, 3800.0, 600.0), (5000.0, 5800.0, 600.0))
    tot = []
    for m in (2.0, 40.0):
        cfg = SimConfig(length=7_000, flow_per_hour=250, warmup=500, n_probes=6, probe_spacing=60,
                        curves=curvas, sight_clearance=m)
        r = run_simulation(cfg, 130, 1)
        tot.append(sum(t["rebases"] for t in r.trips))
    assert tot[1] > tot[0]


def test_curvas_desde_texto():
    from trafico import config as cfgmod

    cfg = cfgmod.set_param(SimConfig(), "curves", "1500:2500:200; 6000:6400:350")
    assert cfg.curves == ((1500.0, 2500.0, 200.0), (6000.0, 6400.0, 350.0))
