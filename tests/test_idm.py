import pytest

from trafico.idm import IDMParams, idm_acceleration, step
from trafico.vehicle import Vehicle, kmh_a_ms, ms_a_kmh

DT = 0.1
P = IDMParams()


def avanzar(vehiculos, segundos):
    """Avanza todos los vehículos (ordenados de atrás hacia delante, líder al final)."""
    for _ in range(int(segundos / DT)):
        estados = [(v.x, v.v) for v in vehiculos]
        # copia del líder al inicio del paso
        for i, veh in enumerate(vehiculos):
            lider = None
            if i + 1 < len(vehiculos):
                l = vehiculos[i + 1]
                lider = Vehicle(l.id, l.v0, estados[i + 1][0], estados[i + 1][1], l.length)
            step(veh, lider, DT, P)


def test_conversion_unidades():
    assert kmh_a_ms(36) == pytest.approx(10)
    assert ms_a_kmh(10) == pytest.approx(36)


def test_gap_y_parte_trasera():
    lider = Vehicle(1, 30, x=100, length=5)
    seguidor = Vehicle(2, 30, x=80)
    assert lider.rear == 95
    assert seguidor.gap_to(lider) == 15


def test_aceleracion_cero_a_velocidad_deseada():
    v0 = kmh_a_ms(120)
    assert idm_acceleration(v0, v0, None, None, P) == pytest.approx(0)


def test_vehiculo_solo_converge_a_su_velocidad_deseada():
    v = Vehicle(1, kmh_a_ms(120))
    maximo = 0.0
    for _ in range(int(300 / DT)):
        step(v, None, DT, P)
        maximo = max(maximo, v.v)
    assert v.v == pytest.approx(kmh_a_ms(120), abs=0.05)
    assert maximo <= kmh_a_ms(120) + 1e-9  # nunca se pasa de su v0


def test_tiempo_libre_cercano_a_L_sobre_v0():
    """Ya arrancado a su v0, el tiempo en recorrer L es L / v0."""
    v0 = kmh_a_ms(100)
    v = Vehicle(1, v0, v=v0)
    pasos = 0
    while v.x < 10_000:
        step(v, None, DT, P)
        pasos += 1
    assert pasos * DT == pytest.approx(10_000 / v0, abs=2 * DT)  # error de discretización: hasta un paso


def test_rapido_frena_detras_de_uno_lento_y_no_choca():
    lento = Vehicle(1, kmh_a_ms(80), x=400, v=kmh_a_ms(80))
    rapido = Vehicle(2, kmh_a_ms(120), x=200, v=kmh_a_ms(120))
    min_gap = float("inf")
    for _ in range(int(600 / DT)):
        avanzar([rapido, lento], DT)
        min_gap = min(min_gap, rapido.gap_to(lento))
    assert min_gap > 0
    assert rapido.v == pytest.approx(lento.v, abs=0.2)
    # distancia de equilibrio ≈ s0 + v*T
    assert rapido.gap_to(lento) == pytest.approx(P.s0 + lento.v * P.T, rel=0.15)


def test_frena_hasta_parar_detras_de_vehiculo_detenido():
    parado = Vehicle(1, kmh_a_ms(50), x=500, v=0.0)
    veh = Vehicle(2, kmh_a_ms(120), x=0, v=kmh_a_ms(120))
    min_gap = float("inf")
    for _ in range(int(120 / DT)):
        step(veh, parado, DT, P)
        min_gap = min(min_gap, veh.gap_to(parado))
    assert min_gap > 0
    assert veh.v == pytest.approx(0, abs=0.05)


def test_velocidad_nunca_negativa():
    veh = Vehicle(1, kmh_a_ms(100), x=0, v=1.0)
    parado = Vehicle(2, 10, x=6, v=0.0, length=2)
    for _ in range(100):
        step(veh, parado, DT, P)
        assert veh.v >= 0
