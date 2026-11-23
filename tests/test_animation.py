import os

import pytest

pygame = pytest.importorskip("pygame")
os.environ["SDL_VIDEODRIVER"] = "dummy"

from trafico.animation import VELOCIDADES, Animacion, captura, color_de, C_SONDA, C_REBASE  # noqa: E402
from trafico.simulation import SimConfig  # noqa: E402

CFG = SimConfig(length=5_000, mode="lleno", n_vehicles=25, warmup=20, n_probes=2, probe_spacing=60)


def test_captura_sin_ventana(tmp_path):
    p = tmp_path / "a.png"
    a = captura(CFG, str(p), frames=3, sim_segundos=200)
    assert p.exists() and p.stat().st_size > 10_000
    assert a.road.t >= 199
    assert a.road.collisions == 0
    assert len(a.sondas) == 2


def test_controles():
    a = Animacion(CFG, size=(1200, 800))
    pg = a.pg

    def tecla(k):
        return a.manejar(pg.event.Event(pg.KEYDOWN, key=k))

    tecla(pg.K_SPACE)
    assert a.pausa
    t = a.road.t
    a.avanzar(1.0)
    assert a.road.t == t  # en pausa no avanza
    tecla(pg.K_SPACE)
    v = a.velocidad
    tecla(pg.K_PLUS)
    assert a.velocidad == VELOCIDADES[VELOCIDADES.index(v) + 1]
    a.avanzar(1.0)
    assert a.road.t == pytest.approx(t + a.velocidad, abs=a.road.dt)
    w = a.ventana
    tecla(pg.K_z)
    assert a.ventana < w
    tecla(pg.K_RIGHT)
    assert not a.seguir
    tecla(pg.K_s)
    assert a.seguir
    a.avanzar(3)  # unos 30 s simulados más: la primera sonda ya entró
    a.dibujar()
    assert a.sonda_activa() is not None
    assert color_de(a.sonda_activa()) == C_SONDA
    tecla(pg.K_r)
    assert a.road.t == 0
    assert tecla(pg.K_ESCAPE) is False
    pg.quit()


def test_color_rebasando():
    a = Animacion(CFG, size=(800, 600))
    v = a.road.vehicles[0]
    v.state = "REBASANDO"
    assert color_de(v) == C_REBASE
    a.pg.quit()


def test_captura_realista_con_pendientes_y_limites(tmp_path):
    from trafico import config as cfgmod

    cfg = cfgmod.realista(SimConfig(length=6_000, mode="lleno", n_vehicles=25, warmup=20, n_probes=1,
                                    relieve="montanoso", trazado="pocas"))
    cfg = cfgmod.set_param(cfg, "limites", "2000:4000:80")
    p = tmp_path / "r.png"
    a = captura(cfg, str(p), frames=2, sim_segundos=300)
    assert p.exists()
    assert a.road.collisions == 0
    assert any(v.kind == "camion" for v in a.road.vehicles + a.road.finished)


def test_preset_realista():
    from trafico import config as cfgmod

    cfg = cfgmod.realista(SimConfig())
    assert cfg.trucks.share == 0.10 and cfg.overtaking.t_lane_change == 3.0 and cfg.overtaking.convoy
    assert cfg.reaction_time == 1.0 and cfg.drivers.share_aggressive == 0.15
    sin = cfgmod.realista(cfgmod.set_param(SimConfig(), "overtaking", "none"))
    assert sin.overtaking is None
