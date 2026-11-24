"""Aceptación de hueco con logit (F032) y conteo de choques por par."""

import dataclasses
import statistics

import pytest

from trafico import config as cfgmod
from trafico.overtaking import OvertakeParams, _u01, eta_conductor
from trafico.road import Road
from trafico.simulation import SimConfig, run_simulation
from trafico.vehicle import REBASANDO, Vehicle, kmh_a_ms

LOGIT = OvertakeParams(gap_logit=True)


def test_u01_determinista_y_uniforme():
    assert _u01(1, 2, 3) == _u01(1, 2, 3)
    assert _u01(1, 2, 3) != _u01(1, 2, 4)
    xs = [_u01(7, i, -1, 3) for i in range(20_000)]
    assert all(0 < x < 1 for x in xs)
    assert statistics.mean(xs) == pytest.approx(0.5, abs=0.01)
    assert sum(x < 0.1 for x in xs) / len(xs) == pytest.approx(0.1, abs=0.01)


def test_eta_normal_y_cero_para_sondas():
    etas = [eta_conductor(11, Vehicle(i, 25.0)) for i in range(20_000)]
    assert statistics.mean(etas) == pytest.approx(0.0, abs=0.03)
    assert statistics.stdev(etas) == pytest.approx(1.0, abs=0.03)
    assert eta_conductor(11, Vehicle(3, 25.0, probe=True)) == 0.0


def _con_contrario(dist_contrario: float, seed: int, p=LOGIT):
    """Un rápido detrás de un lento; un contrario viene de frente a `dist_contrario` m."""
    road = Road(length=20_000, dt=0.1, overtaking=p, logit_seed=seed)
    road.place(kmh_a_ms(80), x=400)
    rapido = road.place(kmh_a_ms(120), x=360, v=kmh_a_ms(80))
    road.place(kmh_a_ms(100), x=20_000 - 400 - dist_contrario, direction=-1)
    for _ in range(15):  # 1.5 s: al menos una decisión
        road.step()
    return rapido.state == REBASANDO


def test_hueco_grande_casi_siempre_y_chico_casi_nunca():
    grandes = sum(_con_contrario(3_000, s) for s in range(40))
    chicos = sum(_con_contrario(250, s) for s in range(40))
    medios = sum(_con_contrario(900, s) for s in range(40))
    assert grandes >= 36
    assert chicos <= 3
    assert chicos < medios < grandes  # la probabilidad crece con el hueco


def test_con_piso_nunca_acepta_lo_que_el_criterio_seguro_rechaza():
    piso = dataclasses.replace(LOGIT, gap_floor=True)
    sin = OvertakeParams()
    for d in (600, 900, 1200):
        seguro = _con_contrario(d, 0, sin)
        for s in range(10):
            if _con_contrario(d, s, piso):
                assert seguro


def test_logit_apagado_no_cambia_nada_y_encendido_no_cambia_el_trafico():
    cfg = SimConfig(length=5_000, flow_per_hour=300, warmup=300, n_probes=3, probe_spacing=40)
    a = run_simulation(cfg, 130, 4)
    b = run_simulation(cfgmod.set_param(cfg, "rebase_logit", True), 130, 4)
    llegadas = lambda r: sorted((t["sentido"], t["id"], t["v0_kmh"]) for t in r.trips)
    assert llegadas(a) == llegadas(b)  # mismos vehículos y velocidades deseadas
    c = run_simulation(cfgmod.set_param(cfg, "rebase_logit", True), 130, 4)
    assert [t["tiempo_viaje"] for t in b.trips] == [t["tiempo_viaje"] for t in c.trips]


def test_estres_con_piso_cero_choques():
    cfg = cfgmod.set_param(cfgmod.set_param(cfgmod.realista(
        SimConfig(length=8_000, flow_per_hour=400, warmup=400, n_probes=4, probe_spacing=40)),
        "rebase_logit", True), "piso_seguro", True)
    for s in (1, 2):
        assert run_simulation(cfg, 130, s).collisions == 0


def test_un_choque_cuenta_una_vez_por_par():
    road = Road(length=2_000, dt=0.1, overtaking=None)
    a = road.place(kmh_a_ms(50), x=500)
    b = road.place(kmh_a_ms(50), x=498)  # encimado: el frente de b está dentro de a
    for _ in range(30):
        road.step()
    assert road.collisions == 1
    assert a.crashes == 1 and b.crashes == 1
