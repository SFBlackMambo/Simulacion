import numpy as np
import pytest

from trafico.arrivals import PoissonArrivals
from trafico.road import Road
from trafico.vehicle import kmh_a_ms


def llegadas(src, horas):
    out, t = [], 0.0
    while t < horas * 3600:
        t += 1.0
        out += src.due(t)
    return out


def test_misma_semilla_misma_secuencia():
    a = llegadas(PoissonArrivals(300, seed=7), 2)
    b = llegadas(PoissonArrivals(300, seed=7), 2)
    c = llegadas(PoissonArrivals(300, seed=8), 2)
    assert a == b
    assert a != c


def test_tasa_media_coincide():
    horas = 200
    n = len(llegadas(PoissonArrivals(300, seed=1), horas))
    esperado = 300 * horas
    assert abs(n - esperado) < 4 * np.sqrt(esperado)  # ~4 sigma de Poisson


def test_velocidades_en_rango_y_media():
    v = np.array(llegadas(PoissonArrivals(600, v0_mean_kmh=100, v0_std_kmh=10, seed=3), 20))
    assert v.min() >= kmh_a_ms(60) and v.max() <= kmh_a_ms(140)
    assert v.mean() == pytest.approx(kmh_a_ms(100), rel=0.02)


def test_tasa_cero_no_genera():
    assert llegadas(PoissonArrivals(0), 1) == []


def test_parametros_invalidos():
    with pytest.raises(ValueError):
        PoissonArrivals(-1)
    with pytest.raises(ValueError):
        PoissonArrivals(100, v0_min_kmh=120, v0_max_kmh=100)


def test_fuente_en_carretera_inyecta_y_no_hay_colisiones():
    road = Road(length=10_000, dt=0.2)
    road.add_source(1, PoissonArrivals(600, seed=11))
    road.run(3600)
    total = len(road.finished) + len(road.vehicles) + len(road._pending[1])
    assert 520 < total < 680
    assert road.collisions == 0
    assert all(v.travel_time >= 10_000 / v.v0 - 1 for v in road.finished)
