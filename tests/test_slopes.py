import numpy as np
import pytest

from trafico import config as cfgmod
from trafico.fleet import CAMION, TruckParams
from trafico.geometry import RELIEVES, Geometry, build_relieve, describe
from trafico.road import Road
from trafico.simulation import SimConfig, free_time, geometry_from_config, run_simulation
from trafico.slopes import (AUTO_GRADES, accel_limit, downhill_factor, engine_brake_speed, truck_response,
                            uphill_speed)


def test_velocidad_minima_en_subida_como_los_datos():
    """Mediana de camiones (~150 lb/hp) y autos frente a NCHRP 505 / SCT."""
    tipico = truck_response(150)
    assert uphill_speed(tipico, 0.03) * 3.6 == pytest.approx(73, abs=4)
    assert uphill_speed(tipico, 0.08) * 3.6 == pytest.approx(36, abs=4)
    pesado = truck_response(390)  # vehículo de proyecto SCT (75.5 t, 430 hp)
    assert pesado.engine_brake and not tipico.engine_brake
    assert uphill_speed(pesado, 0.06) < uphill_speed(tipico, 0.06)
    # autos: hasta ~4 % no lo notan; en 7 % siguen arriba de 80 km/h
    assert uphill_speed(AUTO_GRADES, 0.04) * 3.6 > 100
    assert uphill_speed(AUTO_GRADES, 0.07) * 3.6 > 80


def test_distribucion_de_potencia_de_camiones():
    rng = np.random.default_rng(1)
    w = np.array([TruckParams().response(rng).power_w_kg for _ in range(10000)])
    assert 8.0 < np.median(w) < 10.5
    assert 0.12 < (w < 5.5).mean() < 0.25  # los "fulles" cargados


def test_en_subida_pierde_velocidad_poco_a_poco():
    """En subida no se frena: el motor no da para más y la velocidad baja gradualmente."""
    geo = Geometry(12000, grades=((1000.0, 11000.0, 0.06),))
    road = Road(length=12000, dt=0.2, geometry=geo, trucks=TruckParams())
    v = road.place(100 / 3.6, 500.0, kind=CAMION)
    v.grades = truck_response(150)
    vel, peor = {}, 0.0
    while v.x < 5000:
        road.step()
        if v.x > 1000:
            peor = min(peor, v.a_prev)
        for d in (500, 1000):
            if d not in vel and v.x - 1000 >= d:
                vel[d] = v.v * 3.6
    assert peor > -0.6  # nunca "frena"
    assert vel[500] > 70
    assert vel[1000] > 55
    assert v.v * 3.6 == pytest.approx(uphill_speed(v.grades, 0.06) * 3.6, abs=1.5)
    assert v.catchups == 0


def test_en_bajada_se_dejan_llevar():
    assert downhill_factor(AUTO_GRADES, -0.05) == pytest.approx(1.10)
    assert downhill_factor(AUTO_GRADES, -0.025) == pytest.approx(1.05)
    assert downhill_factor(truck_response(150), -0.06) == pytest.approx(1.05)
    geo = Geometry(8000, grades=((2000.0, 6000.0, -0.05),))
    road = Road(length=8000, dt=0.2, geometry=geo, trucks=TruckParams())
    auto = road.place(100 / 3.6, 0.0)
    vmax = 0.0
    while auto.x < 6000:
        road.step()
        vmax = max(vmax, auto.v * 3.6)
    assert vmax == pytest.approx(110, abs=0.5)


def test_freno_de_motor_solo_en_bajadas_fuertes_y_largas():
    pesado = truck_response(390)
    assert engine_brake_speed(pesado, -0.05) * 3.6 == pytest.approx(64.8, abs=0.1)  # St John: 0.9 / G

    def vmin(largo, pct):
        geo = Geometry(12000, grades=((2000.0, 2000.0 + largo, pct),))
        road = Road(length=12000, dt=0.2, geometry=geo, trucks=TruckParams())
        v = road.place(90 / 3.6, 0.0, kind=CAMION)
        v.grades = pesado
        m = 999.0
        while v.x < 2000 + largo:
            road.step()
            if v.x > 2000:
                m = min(m, v.v * 3.6)
        return m

    assert vmin(3000, -0.07) == pytest.approx(46, abs=2)
    assert vmin(800, -0.07) > 80  # bajada corta: no frena
    assert vmin(3000, -0.03) > 80  # bajada suave: no frena


def test_pendiente_en_cada_sentido():
    geo = Geometry(5000, grades=((1000.0, 2000.0, 0.05),))
    assert geo.grade(1, 1500) == pytest.approx(0.05)
    assert geo.grade(-1, 5000 - 1500) == pytest.approx(-0.05)
    assert geo.grade(1, 500) == 0
    assert geo.elevation(2000) == pytest.approx(50)


def test_tiempo_libre_coincide_con_la_simulacion():
    cfg = SimConfig(length=8000, grades=((1000.0, 4000.0, 0.06), (4000.0, 7000.0, -0.06)))
    geo = geometry_from_config(cfg, 1)
    for kind, resp in (("auto", None), (CAMION, truck_response(150))):
        road = Road(length=8000, dt=0.2, geometry=geo, trucks=TruckParams())
        v = road.place(100 / 3.6, 0.0, kind=kind)
        if resp is not None:
            v.grades = resp
        while v.x < 8000:
            road.step()
        t = free_time(cfg, 100 / 3.6, kind=kind, grades=resp)
        assert t == pytest.approx(road.t, abs=0.5)


def test_camion_pesado_en_llano_no_sostiene_100():
    road = Road(length=10000, dt=0.2, trucks=TruckParams())
    v = road.place(100 / 3.6, 0.0, kind=CAMION)
    v.grades = truck_response(390)
    road.run(200)
    assert 80 < v.v * 3.6 < 95
    assert accel_limit(truck_response(150), 100 / 3.6, 0.0) > 0  # uno típico sí


@pytest.mark.parametrize("nombre", list(RELIEVES))
def test_relieves_generados(nombre):
    a = build_relieve(nombre, 20000, 3)
    assert a == build_relieve(nombre, 20000, 3)
    Geometry(20000, grades=a)
    for _, _, g in a:
        assert abs(100 * g) <= 7.0 + 1e-6
    if nombre == "montanoso":
        assert all(b - x <= 800.1 for x, b, _ in a)


def test_relieve_y_trazado_juntos():
    cfg = SimConfig(trazado="pocas", relieve="lomerio")
    geo = geometry_from_config(cfg, 1)
    assert geo.curves and geo.grades
    d = describe(geo, cfg.length)
    assert d["pendiente_max_pct"] <= 4.0 and d["curvas"] > 0


def test_sin_trafico_con_pendientes_no_hay_retraso():
    cfg = SimConfig(length=8000, flow_per_hour=0, warmup=10, n_probes=2, probe_spacing=30, relieve="montanoso")
    r = run_simulation(cfg, 130, seed=2)
    # la segunda sonda siente muy levemente a la primera (1 km delante) en las subidas
    assert all(abs(p.delay) < 1.0 for p in r.probes)


def test_montana_con_camiones_cero_colisiones():
    cfg = cfgmod.set_param(SimConfig(length=8000, flow_per_hour=250, warmup=500, n_probes=4,
                                     relieve="montanoso"), "camiones", 0.25)
    r = run_simulation(cfg, 130, 1)
    assert r.collisions == 0
    cam = [t for t in r.trips if t["clase"] == CAMION and t["viaje_completo"]]
    assert cam and all(t["retraso"] > -1 for t in cam)


def test_pendientes_desde_texto_en_porcentaje(tmp_path):
    cfg = cfgmod.set_param(SimConfig(), "pendientes", "1000:3000:5;4000:5000:-3")
    assert cfg.grades == ((1000.0, 3000.0, 0.05), (4000.0, 5000.0, -0.03))
    cfgmod.save(cfg, tmp_path / "c.json")
    assert cfgmod.load(tmp_path / "c.json")[0] == cfg
