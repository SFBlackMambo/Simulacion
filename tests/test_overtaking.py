import pytest

from trafico.arrivals import PoissonArrivals
from trafico.overtaking import OvertakeParams
from trafico.road import Road
from trafico.vehicle import REBASANDO, SIGUIENDO, kmh_a_ms

DT = 0.1
P = OvertakeParams()


def correr_hasta_vacio(road, max_s=4000):
    for _ in range(int(max_s / road.dt)):
        road.step()
        if not road.vehicles and not any(road._pending.values()):
            return
    raise AssertionError("la carretera no se vació")


def escenario(lento_kmh=80, rapido_kmh=120, longitud=20_000, **kw):
    road = Road(length=longitud, dt=DT, overtaking=P, **kw)
    lento = road.place(kmh_a_ms(lento_kmh), x=400)
    rapido = road.place(kmh_a_ms(rapido_kmh), x=250)
    return road, lento, rapido


def test_con_carril_contrario_libre_el_rapido_rebasa_al_lento():
    road, lento, rapido = escenario()
    estados = set()
    for _ in range(int(2000 / DT)):
        road.step()
        estados.add(rapido.state)
        if not road.vehicles:
            break
    assert road.collisions == 0
    assert rapido.overtakes == 1 and rapido.aborts == 0
    assert REBASANDO in estados
    assert rapido.t_exit < lento.t_exit  # llegó antes que el lento
    assert rapido.travel_time < 20_000 / kmh_a_ms(80) - 100  # mucho mejor que quedarse detrás
    assert rapido.travel_time == pytest.approx(20_000 / kmh_a_ms(120), rel=0.08)
    assert rapido.emergency_steps == 0


def test_sin_rebase_el_rapido_se_queda_detras():
    road = Road(length=20_000, dt=DT)  # overtaking=None
    lento = road.place(kmh_a_ms(80), x=400)
    rapido = road.place(kmh_a_ms(120), x=250)
    correr_hasta_vacio(road)
    assert rapido.overtakes == 0
    assert rapido.travel_time > 20_000 / kmh_a_ms(80) - 30


def test_con_trafico_contrario_denso_no_rebasa():
    road, lento, rapido = escenario()
    # flujo contrario continuo: un vehículo cada 120 m a lo largo de toda la carretera
    for k in range(160):
        road.place(kmh_a_ms(100), x=20 + 120 * k, direction=-1)
    for _ in range(int(60 / DT)):
        road.step()
    assert rapido.state == SIGUIENDO and rapido.overtakes == 0 and rapido.lane == 0
    assert road.collisions == 0


def test_rebasa_cuando_el_contrario_pasa_y_hay_hueco():
    road, lento, rapido = escenario()
    # un solo vehículo contrario cerca, ya pasa antes de que se pueda rebasar
    contrario = road.place(kmh_a_ms(100), x=17_000, direction=-1)  # frente en 3 km del frente de +1
    road.run(5)
    assert rapido.lane == 0  # con el contrario a ~3 km aún no es seguro
    road.run(300)
    assert rapido.overtakes == 1
    assert road.collisions == 0


def test_rebasa_un_pelotón_de_dos():
    road = Road(length=20_000, dt=DT, overtaking=P)
    road.place(kmh_a_ms(80), x=470)
    road.place(kmh_a_ms(85), x=440)  # va pegado al primero (cadena de 2)
    rapido = road.place(kmh_a_ms(125), x=300)
    for _ in range(int(2500 / DT)):
        road.step()
        if not road.vehicles:
            break
    assert road.collisions == 0
    assert rapido.overtakes == 2
    assert rapido.aborts == 0


def test_no_rebasa_si_el_lider_es_casi_igual_de_rapido():
    road, lento, rapido = escenario(lento_kmh=119, rapido_kmh=120)
    road.run(300)
    assert rapido.lane == 0 and rapido.overtakes == 0


def test_no_rebasa_cerca_del_final_de_la_carretera():
    road = Road(length=3_000, dt=DT, overtaking=P)
    road.place(kmh_a_ms(80), x=2_600)
    rapido = road.place(kmh_a_ms(120), x=2_450)
    road.run(60)
    assert rapido.overtakes == 0 and road.collisions == 0


def test_aborta_si_aparece_un_vehiculo_de_frente():
    """Un contrario inesperado (fuera del plan) provoca aborto o frenado, no choque."""
    road, lento, rapido = escenario()
    road.run(60)
    assert rapido.state != SIGUIENDO or rapido.overtakes == 1
    if rapido.state != SIGUIENDO:
        # aparece de golpe un vehículo contrario, muy cerca, por el carril ocupado
        road.place(kmh_a_ms(100), x=road.length - (rapido.x + 600), direction=-1, lane=rapido.lane)
        road.run(120)
    assert road.collisions == 0


@pytest.mark.parametrize("semilla", [1, 2, 3])
def test_estres_trafico_aleatorio_sin_colisiones_ni_bloqueos(semilla):
    road = Road(length=10_000, dt=0.2, overtaking=P)
    road.add_source(1, PoissonArrivals(500, seed=100 + semilla))
    road.add_source(-1, PoissonArrivals(500, seed=200 + semilla))
    road.run(2_400)
    assert road.collisions == 0
    assert sum(v.overtakes for v in road.finished) > 0
    # un rebase bien planeado no obliga a nadie a frenar de emergencia
    assert sum(v.emergency_steps > 0 for v in road.finished) <= 0.01 * len(road.finished)
    # sin bloqueos: no se acumulan vehículos parados ni en la carretera
    assert len(road.vehicles) < 200
    assert sum(v.v < 1 for v in road.vehicles) <= 2
