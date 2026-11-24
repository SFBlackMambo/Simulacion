"""Riesgo y balance en dinero (F031)."""

import pytest

from trafico import costos
from trafico.costos import ESCENARIOS, Precios, balance, con_precios, riesgo_kloeden, riesgo_nilsson


def test_nilsson_en_la_referencia_es_1_y_crece_con_la_potencia():
    assert riesgo_nilsson(100) == {"muertos": 1.0, "graves": 1.0, "leves": 1.0}
    r = riesgo_nilsson(110)
    assert r["muertos"] == pytest.approx(1.1 ** 4.1)
    assert r["muertos"] > r["graves"] > r["leves"] > 1
    assert riesgo_nilsson(90)["muertos"] < 1


def test_kloeden_valores_conocidos():
    assert riesgo_kloeden(0) == 1.0
    # +10 km/h sobre la media: ~2.2 veces; +20: ~5.9 (Kloeden et al. 2001)
    assert riesgo_kloeden(10) == pytest.approx(2.2, rel=0.03)
    assert riesgo_kloeden(20) == pytest.approx(5.86, rel=0.03)
    assert riesgo_kloeden(-10) < 1


def test_balance_por_partes():
    p = Precios()
    b = balance(p, tiempo_s=3600, litros=10, co2_kg=23.48, km=100, v_kmh=100)
    assert b["tiempo"] == pytest.approx(100)
    assert b["combustible"] == pytest.approx(240)
    assert b["co2"] == pytest.approx(46.96)
    assert b["accidentes"] == pytest.approx(50)
    assert b["total"] == pytest.approx(100 + 240 + 46.96 + 50)
    assert balance(p, 0, 10, 0, 0, 100, diesel=True)["combustible"] == pytest.approx(260)


def test_accidentes_mas_caros_al_ir_mas_rapido_y_kloeden_usa_el_trafico():
    p = Precios()
    lento = balance(p, 0, 0, 0, 20, 100)["accidentes"]
    rapido = balance(p, 0, 0, 0, 20, 130)["accidentes"]
    assert rapido > 2 * lento
    k = con_precios("medio", riesgo="kloeden")
    assert balance(k, 0, 0, 0, 20, 110, v_trafico_kmh=100)["accidentes"] == pytest.approx(20 * 0.5 * riesgo_kloeden(10))
    with pytest.raises(ValueError):
        balance(k, 0, 0, 0, 20, 110)


def test_escenarios_y_cambios():
    assert ESCENARIOS["bajo"].valor_tiempo_h < ESCENARIOS["medio"].valor_tiempo_h < ESCENARIOS["alto"].valor_tiempo_h
    p = con_precios("alto", gasolina_l="30")
    assert p.gasolina_l == 30.0 and p.valor_tiempo_h == ESCENARIOS["alto"].valor_tiempo_h
    with pytest.raises(KeyError):
        con_precios("medio", gasolna_l=1)


def test_viaje_tipico_medio():
    # 20 km: a 130 se gana tiempo pero sube combustible y riesgo; con precios medios conviene ir más lento
    p = ESCENARIOS["medio"]
    a100 = balance(p, 20 / 100 * 3600, 1.13, 2.65, 20, 100)["total"]
    a130 = balance(p, 20 / 130 * 3600, 1.50, 3.52, 20, 130)["total"]
    assert a100 < a130
    assert costos.riesgo_relativo(p, 100) == pytest.approx(1.0)
