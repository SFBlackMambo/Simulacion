import math

import pytest

from trafico.recorder import viaje
from trafico.road import Road


def test_headway_y_ttc_con_el_de_delante():
    road = Road(length=5000, dt=0.2)
    lider = road.place(20.0, 1050.0, v=20.0)
    b = road.place(30.0, 1000.0, v=25.0)  # 45.5 m detrás, 5 m/s más rápido
    road.step()
    assert b.ttc_leader_min == pytest.approx(45.5 / 5.0)
    assert b.t_hw3 == pytest.approx(0.2)  # headway (50 m / 25 m/s) = 2 s < 3
    assert b.t_hw25 == pytest.approx(0.2)
    assert math.isinf(lider.ttc_leader_min) and lider.t_hw3 == 0.0


def test_ttc_frente_a_frente_y_tiempo_en_contrario():
    road = Road(length=5000, dt=0.2)
    r = road.place(30.0, 1000.0, v=30.0, lane=1)  # sentido +1 en el carril contrario
    c = road.place(25.0, 5000 - 1550.0, v=25.0, direction=-1)  # su frente en x = 1550 (carretera)
    road.step()
    assert r.ttc_opp_min == pytest.approx(550.0 / 55.0)
    assert c.ttc_opp_min == pytest.approx(550.0 / 55.0)
    assert r.t_opposite == pytest.approx(0.2) and c.t_opposite == 0.0


def test_episodios_de_conflicto():
    road = Road(length=5000, dt=0.2)
    road.place(0.1, 1020.0, v=0.0)  # parado
    b = road.place(30.0, 1000.0, v=20.0)  # TTC 15.5/20 < 1.5 s
    road.step()
    road.step()
    assert b.conflicts_leader == 1  # un solo episodio aunque dure varios pasos


def test_columnas_del_viaje():
    road = Road(length=1000, dt=0.2)
    v = road.place(25.0, 990.0)
    road.run(1.0)
    fila = viaje(v, 1000 / 25.0, 1000.0)
    assert fila["ttc_min_lider"] == "" and fila["lb_hp"] == "" and fila["potencia_w_kg"] == 22.0
    assert fila["pct_tiempo_siguiendo"] == 0.0
