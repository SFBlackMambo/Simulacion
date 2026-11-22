import pytest

from trafico.arrivals import PoissonArrivals
from trafico.road import Road
from trafico.vehicle import kmh_a_ms

DT = 0.1


def correr_hasta_vacio(road, max_s=3000):
    for _ in range(int(max_s / road.dt)):
        road.step()
        if not road.vehicles and not any(road._pending.values()):
            return
    raise AssertionError("la carretera no se vació")


def test_cada_sentido_usa_su_carril_y_tarda_L_sobre_v0():
    road = Road(length=5_000, dt=DT)
    a = road.inject(kmh_a_ms(100), direction=1)
    b = road.inject(kmh_a_ms(110), direction=-1)
    road.run(1.0)
    assert (a.lane, b.lane) == (0, 1)
    correr_hasta_vacio(road)
    assert a.travel_time == pytest.approx(5_000 / kmh_a_ms(100), abs=2 * DT)
    assert b.travel_time == pytest.approx(5_000 / kmh_a_ms(110), abs=2 * DT)
    assert road.collisions == 0


def test_un_sentido_no_afecta_al_otro():
    sola = Road(length=5_000, dt=DT)
    v1 = sola.inject(kmh_a_ms(120), direction=1)
    correr_hasta_vacio(sola)

    con_contrario = Road(length=5_000, dt=DT)
    v2 = con_contrario.inject(kmh_a_ms(120), direction=1)
    for _ in range(5):
        con_contrario.inject(kmh_a_ms(70), direction=-1)
    correr_hasta_vacio(con_contrario)
    assert v2.travel_time == pytest.approx(v1.travel_time, abs=DT)


def test_choque_frontal_en_mismo_carril_se_evita_con_frenado_de_emergencia():
    road = Road(length=10_000, dt=DT)
    a = road.place(kmh_a_ms(120), x=3_000, direction=1, lane=0)
    b = road.place(kmh_a_ms(120), x=3_000, direction=-1, lane=0)  # frente a frente, a 4 km
    road.run(300)
    assert road.collisions == 0
    assert a.emergency_steps > 0 and b.emergency_steps > 0
    assert a.v == pytest.approx(0, abs=0.1) and b.v == pytest.approx(0, abs=0.1)


def test_sin_aviso_hay_colision_si_se_detecta():
    """El contador de colisiones frontales funciona: vehículos ya solapados."""
    road = Road(length=1_000, dt=DT)
    road.place(kmh_a_ms(100), x=500, direction=1, lane=0)
    road.place(kmh_a_ms(100), x=500, direction=-1, lane=0)  # frente a frente, mismo punto
    road.step()
    assert road.collisions > 0


def test_entrada_se_bloquea_si_viene_un_contrario_por_el_carril():
    road = Road(length=5_000, dt=DT)
    road.place(kmh_a_ms(100), x=4_950, direction=-1, lane=0)  # contrario en el carril 0, cerca de x=0 de +1
    nuevo = road.inject(kmh_a_ms(100), direction=1)
    road.run(0.5)
    assert nuevo not in road.vehicles


def test_trafico_en_ambos_sentidos_sin_colisiones():
    road = Road(length=10_000, dt=0.2)
    road.add_source(1, PoissonArrivals(500, seed=1))
    road.add_source(-1, PoissonArrivals(500, seed=2))
    road.run(3_600)
    assert road.collisions == 0
    assert len(road.finished) > 500
    assert {v.direction for v in road.finished} == {1, -1}
