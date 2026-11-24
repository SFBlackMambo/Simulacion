"""Carril de rebase / tramos 2+1 (F034-F035)."""

import pytest

from trafico import config as cfgmod
from trafico.arrivals import PoissonArrivals
from trafico.overtaking import OvertakeParams
from trafico.road import Road
from trafico.simulation import SimConfig, run_simulation
from trafico.vehicle import kmh_a_ms


def _pelotón(tramos=((3000, 5000, 1),), flujo_contrario=900, p=OvertakeParams()):
    road = Road(length=10_000, dt=0.2, overtaking=p, passing_lanes=tramos)
    road.add_source(-1, PoissonArrivals(flujo_contrario, 100, 10, seed=1))
    road.run(450)  # que el tráfico de frente llene la carretera
    camion = road.place(kmh_a_ms(70), x=2700, kind="camion")
    autos = [road.place(kmh_a_ms(100 + 3 * i), x=camion.rear - 40 - 35 * i, v=kmh_a_ms(70)) for i in range(5)]
    x_extra = 0.0
    while any(v in road.vehicles for v in [camion, *autos]):
        road.step()
        for v in road.vehicles:
            if v.lane >= 2:
                assert v.lane == v.extra_lane
                x_extra = max(x_extra, v.x)
    return road, camion, autos, x_extra


def test_con_carril_extra_todos_rebasan_al_camion_sin_carril_contrario():
    road, camion, autos, x_extra = _pelotón()
    assert road.collisions == 0
    assert camion.overtaken == 5 and all(a.overtakes == 1 for a in autos)
    assert all(a.t_opposite == 0 for a in autos)  # el carril extra no es el contrario
    assert 3000 < x_extra < 5000  # nadie sigue en el carril extra después de que se acaba


def test_sin_carril_extra_y_trafico_de_frente_denso_casi_no_rebasan():
    road, camion, autos, _ = _pelotón(tramos=())
    assert camion.overtaken < 5


def test_el_otro_sentido_no_rebasa_donde_hay_carril_extra():
    road = Road(length=10_000, passing_lanes=((3000, 5000, 1),))
    # para el sentido -1 el tramo está en 5000-7000 de su coordenada propia, con 100 m de margen
    assert road.passing_blocked(-1, 4950, 5200)
    assert road.passing_blocked(-1, 6900, 7050)
    assert not road.passing_blocked(-1, 7200, 7800)
    assert road.passing_blocked(1, 3500, 3800)  # dentro de su carril extra usa ese carril
    assert not road.passing_blocked(1, 1000, 2000)
    assert road.passing_end(1, 4000) == 5000 and road.passing_end(1, 5000) is None
    assert road.passing_end(-1, 6000) is None  # el tramo es solo del sentido +1
    r2 = Road(length=10_000, passing_lanes=((6000, 8000, -1),))
    assert r2.passing_end(-1, 2500) == 4000  # 6000-8000 en la carretera = 2000-4000 en su coordenada


def test_tramos_invalidos():
    with pytest.raises(ValueError):
        Road(length=10_000, passing_lanes=((3000, 2000, 1),))
    with pytest.raises(ValueError):
        Road(length=10_000, passing_lanes=((3000, 5000, 1), (4000, 6000, -1)))


def test_configuracion_por_texto():
    cfg = cfgmod.set_param(SimConfig(), "carriles_rebase", "2000:4000:1;6000:8000:-1")
    assert cfg.passing_lanes == ((2000.0, 4000.0, 1), (6000.0, 8000.0, -1))
    d = cfgmod.from_dict(cfgmod.to_dict(cfg))
    assert d.passing_lanes == cfg.passing_lanes


def test_estres_realista_con_carriles_de_rebase_sin_choques():
    cfg = cfgmod.set_param(cfgmod.realista(SimConfig(length=8_000, flow_per_hour=600, warmup=400, n_probes=4,
                                                     probe_spacing=40)), "camiones", 0.2)
    cfg = cfgmod.set_param(cfgmod.set_param(cfg, "relieve", "montanoso"), "trazado", "pocas")
    cfg = cfgmod.set_param(cfg, "carriles_rebase", "1000:2500:1;3500:5000:-1;6000:7500:1")
    base = cfgmod.set_param(cfg, "carriles_rebase", "")
    con = [run_simulation(cfg, 130, s) for s in (1, 2)]
    assert all(r.collisions == 0 for r in con)
    sin = [run_simulation(base, 130, s) for s in (1, 2)]
    rebases = lambda rs: sum(t["rebases"] for r in rs for t in r.trips)
    assert rebases(con) > rebases(sin)


def test_patron_cada_2mas1_y_etiquetas():
    from trafico.analysis import valor_legible
    from trafico.simulation import tramos_2mas1

    cfg = cfgmod.set_param(SimConfig(), "cada_2mas1", "5000")
    assert tramos_2mas1(cfg) == ((2500.0, 4000.0, 1), (7500.0, 9000.0, -1), (12500.0, 14000.0, 1),
                                 (17500.0, 19000.0, -1))
    assert tramos_2mas1(SimConfig()) == ()
    assert valor_legible("passing_every", 0.0) == "Sin carriles de rebase"
    assert valor_legible("passing_every", 5000.0) == "2+1 cada 5 km"
    assert valor_legible("overtaking.gap_logit", True) == "Hueco con logit"
