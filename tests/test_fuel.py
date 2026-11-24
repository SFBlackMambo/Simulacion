"""Combustible y CO2 (F030): revisión contra consumos de referencia y que no cambie la dinámica."""

import pytest

from trafico.fuel import AUTO_FUEL, CO2_DIESEL, CO2_GASOLINA, l_100km_constante, litros_por_s, truck_fuel
from trafico.road import Road
from trafico.simulation import SimConfig, run_simulation

# Valores típicos de un auto compacto de gasolina en llano (L/100 km); el plan pide ±15 %.
REF_AUTO = {100: 5.8, 120: 7.0, 130: 7.6}


@pytest.mark.parametrize("v,ref", REF_AUTO.items())
def test_auto_contra_referencia(v, ref):
    assert l_100km_constante(AUTO_FUEL, v) == pytest.approx(ref, rel=0.15)


def test_mas_rapido_gasta_mas_y_de_100_a_130_unos_30_por_ciento():
    c = [l_100km_constante(AUTO_FUEL, v) for v in (90, 100, 110, 120, 130, 140, 150)]
    assert c == sorted(c)
    assert 1.2 < c[4] / c[1] < 1.45


def test_camion_contra_referencia():
    # tractocamión de ~30 t a 90 km/h: 30-40 L/100 km; un full de ~76 t gasta bastante más
    assert 27 < l_100km_constante(truck_fuel(150), 90) < 40
    assert l_100km_constante(truck_fuel(390), 90) > 1.4 * l_100km_constante(truck_fuel(150), 90)


def test_subida_gasta_mas_y_bajada_solo_ralenti():
    assert l_100km_constante(AUTO_FUEL, 100, 0.05) > 2 * l_100km_constante(AUTO_FUEL, 100)
    ralenti = AUTO_FUEL.p0_kw / (AUTO_FUEL.mj_l * 1000)
    assert litros_por_s(AUTO_FUEL, 27.8, 0.0, -0.06) == pytest.approx(ralenti)
    assert litros_por_s(AUTO_FUEL, 27.8, -3.0, 0.0) == pytest.approx(ralenti)


def test_co2_por_litro_epa():
    assert CO2_GASOLINA == pytest.approx(2.348, abs=0.002)
    assert CO2_DIESEL == pytest.approx(2.689, abs=0.002)


def test_viaje_a_velocidad_constante_gasta_lo_de_referencia():
    road = Road(length=5_000, dt=0.2, overtaking=None)
    veh = road.place(120 / 3.6, 0.0)
    while road.vehicles:
        road.step()
    l100 = veh.fuel_l * 100_000 / 5_000
    assert l100 == pytest.approx(l_100km_constante(AUTO_FUEL, 120), rel=0.02)


def test_columnas_de_combustible_en_viajes():
    cfg = SimConfig(length=3_000, flow_per_hour=300, warmup=200, n_probes=2, probe_spacing=30)
    from trafico import config as cfgmod

    cfg = cfgmod.set_param(cfgmod.set_param(cfg, "camiones", 0.3), "relieve", "montanoso")
    res = run_simulation(cfg, 130, 3)
    autos = [t for t in res.trips if t["clase"] == "auto" and t["viaje_completo"]]
    camiones = [t for t in res.trips if t["clase"] == "camion" and t["viaje_completo"]]
    assert autos and camiones
    assert all(t["litros"] > 0 and t["co2_kg"] > 2 * t["litros"] for t in res.trips)
    media = lambda xs: sum(xs) / len(xs)
    assert media([t["l_100km"] for t in camiones]) > 3 * media([t["l_100km"] for t in autos])
