"""Puente para la página web (site/, Pyodide): misma simulación que la animación, datos para dibujar."""

from trafico.web import CAMPOS, SimWeb, configurar


def test_configurar_escenarios():
    cfg = configurar({"realista": True, "cada_2mas1_km": 3, "longitud_km": 9, "vehiculos": 30, "camiones": 0.2})
    assert cfg.length == 9000 and cfg.n_vehicles == 30 and cfg.mode == "lleno"
    assert cfg.passing_every == 3000 and cfg.trucks.share == 0.2 and cfg.overtaking.peek
    assert configurar({}).overtaking.peek is False  # sin realista: modelo simple


def test_estado_info_y_geometria():
    s = SimWeb({"realista": True, "cada_2mas1_km": 3, "relieve": "lomerio", "trazado": "pocas", "vehiculos": 20})
    pasos = s.avanzar(400)
    assert pasos == 2000  # tope de pasos por llamada
    e = s.estado()
    assert len(e) == CAMPOS * len(s.road.vehicles) and len(e) > 0
    for i in range(0, len(e), CAMPOS):
        assert 0 <= e[i] <= s.cfg.length + 50
        assert e[i + 5] in (0, 1, 2, 3)
    info = s.info()
    assert info["en_carretera"] == len(s.road.vehicles) and info["colisiones"] == 0
    assert info["activa"] is not None or info["hechas"]
    g = s.geometria()
    assert g["longitud"] == s.cfg.length and len(g["carriles_rebase"]) == 2 and len(g["perfil"]) == 301
    assert any("2+1" in t for t in g["modelo"])


def test_sondas_terminan_y_tienen_perdida():
    s = SimWeb({"vehiculos": 10, "longitud_km": 3})
    while not s.info()["hechas"]:
        s.avanzar(60)
    h = s.info()["hechas"][0]
    assert h["tardo"] >= h["libre"] - 1 and h["n"] == 1
