import csv
import json

import pytest

from trafico import config as cfgmod
from trafico.cli import main
from trafico.simulation import SimConfig
from trafico.single import platoons, run_single

PEQ = SimConfig(length=5_000, flow_per_hour=300, warmup=300, n_probes=2, probe_spacing=60)


def _filas(path):
    with open(path) as f:
        return list(csv.DictReader(f))


def test_corrida_unica_guarda_datos_y_graficas(tmp_path):
    r = run_single(PEQ, 130, 1, tmp_path, snapshot_interval=5.0)
    for nombre in ("viajes.csv", "eventos.csv", "fotos.csv", "config.json", "resumen.json",
                   "espacio_tiempo.png", "retraso_histograma.png", "retraso_vs_velocidad.png",
                   "pelotones.png", "rebases_por_km.png"):
        assert (tmp_path / nombre).exists(), nombre
    viajes = _filas(tmp_path / "viajes.csv")
    assert len(viajes) == r["vehiculos_que_salieron"]
    assert r["sondas"]["n"] == 2
    assert r["colisiones"] == 0
    eventos = _filas(tmp_path / "eventos.csv")
    assert r["rebases_completados"] == sum(e["tipo"] == "rebase_fin" for e in eventos)
    cfg, extra = cfgmod.load(tmp_path / "config.json")
    assert cfg == PEQ and extra["velocidad_sonda"] == 130


def test_pelotones_sinteticos():
    # sentido +1, carril 0; a 25 m/s: 3 s = 75 m
    fotos = [
        (0.0, 1, 1, 1000.0, 90.0, 100.0, 0, 0, "SIGUIENDO"),
        (0.0, 2, 1, 950.0, 90.0, 100.0, 0, 0, "SIGUIENDO"),  # pegado a 1
        (0.0, 3, 1, 500.0, 90.0, 100.0, 0, 0, "SIGUIENDO"),  # solo
        (0.0, 4, 1, 300.0, 90.0, 100.0, 0, 0, "SIGUIENDO"),  # solo
        (0.0, 5, 1, 250.0, 90.0, 100.0, 0, 0, "SIGUIENDO"),  # pegado a 4
        (0.0, 6, 1, 200.0, 90.0, 100.0, 0, 0, "SIGUIENDO"),  # pegado a 5
    ]
    ts, frac, tam = platoons(fotos)[1]
    assert frac[0] == pytest.approx(5 / 6)
    assert tam[0] == pytest.approx(5 / 2)  # dos pelotones: (1,2) y (4,5,6)


def test_set_param():
    cfg = SimConfig()
    assert cfgmod.set_param(cfg, "flujo", "250").flow_per_hour == 250.0
    assert cfgmod.set_param(cfg, "idm.T", "2").idm.T == 2.0
    assert cfgmod.set_param(cfg, "overtaking.t_guard", 8).overtaking.t_guard == 8
    assert cfgmod.set_param(cfg, "sondas", "4").n_probes == 4
    assert cfgmod.set_param(cfg, "rebases", "no").overtaking is None
    assert cfgmod.get_param(cfgmod.set_param(cfg, "modo", "lleno"), "modo") == "lleno"
    with pytest.raises(KeyError):
        cfgmod.set_param(cfg, "no_existe", 1)
    assert cfgmod.from_dict(cfgmod.to_dict(cfg)) == cfg


def test_cli_corrida(tmp_path, capsys):
    main(["corrida", "--longitud", "4000", "--flujo", "200", "--calentamiento", "200",
          "--sondas", "1", "--sin-graficas", "--param", "idm.T=1.2", "--salida", str(tmp_path)])
    assert "colisiones: 0" in capsys.readouterr().out
    cfg, _ = cfgmod.load(tmp_path / "config.json")
    assert cfg.idm.T == 1.2 and cfg.length == 4000
    resumen = json.loads((tmp_path / "resumen.json").read_text())
    assert resumen["sondas"]["n"] == 1
