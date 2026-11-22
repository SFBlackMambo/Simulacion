import pytest

from trafico.road import Road
from trafico.vehicle import kmh_a_ms

DT = 0.1


def correr_hasta_vacio(road, max_s=3000):
    for _ in range(int(max_s / road.dt)):
        road.step()
        if not road.vehicles and not any(road._pending.values()):
            return
    raise AssertionError("la carretera no se vació")


def test_vehiculo_libre_tarda_L_sobre_v0():
    road = Road(length=5_000, dt=DT)
    v = road.inject(kmh_a_ms(100))
    correr_hasta_vacio(road)
    assert road.finished == [v]
    assert v.travel_time == pytest.approx(5_000 / kmh_a_ms(100), abs=2 * DT)


def test_registra_entrada_y_salida():
    road = Road(length=2_000, dt=DT)
    road.run(10.0)
    v = road.inject(kmh_a_ms(90))
    correr_hasta_vacio(road)
    assert v.t_entry == pytest.approx(10.0, abs=DT)
    assert v.t_exit > v.t_entry
    assert v.x >= 2_000
    assert road.vehicles == []


def test_vehiculo_aun_en_carretera_no_tiene_tiempo_de_viaje():
    road = Road(length=5_000, dt=DT)
    v = road.inject(kmh_a_ms(100))
    road.run(5.0)
    assert v.travel_time is None


def test_rapido_detras_de_lento_no_choca_y_pierde_tiempo():
    road = Road(length=10_000, dt=DT)
    lento = road.place(kmh_a_ms(80), x=300)
    rapido = road.place(kmh_a_ms(120), x=0)
    correr_hasta_vacio(road)
    assert road.collisions == 0
    assert rapido.travel_time > 10_000 / kmh_a_ms(100)  # mucho peor que L / 120
    assert rapido.t_exit >= lento.t_exit - 5
    assert rapido.t_slow > 100


def test_entrada_espera_hueco_y_no_se_solapa():
    road = Road(length=5_000, dt=DT)
    a = road.inject(kmh_a_ms(100))
    b = road.inject(kmh_a_ms(100))
    road.run(1.0)
    assert a in road.vehicles and b not in road.vehicles  # b espera
    correr_hasta_vacio(road)
    assert b.t_entry > a.t_entry
    assert b.t_wait_entry > 0
    assert road.collisions == 0


def test_dos_sentidos_tienen_colas_independientes():
    road = Road(length=5_000, dt=DT)
    a = road.inject(kmh_a_ms(100), direction=1)
    b = road.inject(kmh_a_ms(100), direction=-1)
    road.run(0.5)
    assert a in road.vehicles and b in road.vehicles
