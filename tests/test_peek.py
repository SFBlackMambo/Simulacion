"""Asomarse para ver (F033): línea de visión detrás del vehículo de delante."""

import dataclasses
import math

import pytest

from trafico import config as cfgmod
from trafico.overtaking import OvertakeParams, _vista_geometrica
from trafico.road import Road
from trafico.simulation import SimConfig, run_simulation
from trafico.vehicle import REBASANDO, Vehicle, kmh_a_ms

PEEK = OvertakeParams(peek=True)


def _par(gap, kind_b="auto", kind_v="auto"):
    L = 16.5 if kind_b == "camion" else 4.5
    b = Vehicle(1, 20.0, x=100 + gap + L, length=L, kind=kind_b)
    v = Vehicle(2, 30.0, x=100, kind=kind_v)
    return v, b


def test_sin_asomarse_la_vista_crece_con_la_distancia_al_de_delante():
    p = dataclasses.replace(PEEK, peek_offset=0.0)
    # ojo a 0.4 m, borde del auto a 0.9, contrario a 2.6: D = g·2.2/0.5
    assert _vista_geometrica(p, *_par(20)) == pytest.approx(88.0)
    assert _vista_geometrica(p, *_par(40)) == pytest.approx(176.0)


def test_asomado_ve_todo_detras_de_un_auto_pero_no_de_un_camion():
    assert _vista_geometrica(PEEK, *_par(20)) == math.inf
    d20 = _vista_geometrica(PEEK, *_par(20, "camion"))
    assert d20 == pytest.approx(20 * 1.6 / 0.3)
    assert _vista_geometrica(PEEK, *_par(80, "camion")) == pytest.approx(4 * d20)


def test_un_camion_ve_por_encima_de_un_auto():
    assert _vista_geometrica(dataclasses.replace(PEEK, peek_offset=0.0), *_par(10, "auto", "camion")) == math.inf
    assert _vista_geometrica(PEEK, *_par(10, "camion", "camion")) == pytest.approx(10 * 1.4 / 0.1)


def _intenta(gap_camion, dist_contrario):
    road = Road(length=20_000, dt=0.1, overtaking=PEEK)
    camion = road.place(kmh_a_ms(70), x=1_000, kind="camion")
    auto = road.place(kmh_a_ms(120), x=camion.rear - gap_camion, v=kmh_a_ms(70))
    road.place(kmh_a_ms(90), x=20_000 - 1_000 - dist_contrario, direction=-1)
    for _ in range(15):
        road.step()
    return auto.state == REBASANDO


def test_pegado_al_camion_no_sale_aunque_el_hueco_sea_bueno():
    # a 15 m del camión ve ~80 m: no le alcanza para ver al que viene a 1.5 km
    assert not _intenta(15, 1_500)


def test_estres_realista_con_asomarse_sin_choques():
    cfg = cfgmod.set_param(cfgmod.set_param(cfgmod.realista(SimConfig(
        length=8_000, flow_per_hour=400, warmup=400, n_probes=4, probe_spacing=40)), "overtaking.peek", True),
        "camiones", 0.2)
    cfg = cfgmod.set_param(cfgmod.set_param(cfg, "trazado", "pocas"), "relieve", "montanoso")
    for s in (1, 2):
        assert run_simulation(cfg, 130, s).collisions == 0
