import csv

import pytest

from trafico.analysis import Campaign, plot_campaign
from trafico.campaign import combos, parse_sweep, run_campaign
from trafico.cli import main
from trafico.simulation import SimConfig

BASE = SimConfig(length=3_000, flow_per_hour=200, warmup=150, n_probes=2, probe_spacing=40)


def _n(path):
    with open(path) as f:
        return sum(1 for _ in csv.DictReader(f))


def test_parse_sweep_y_combos():
    assert parse_sweep("flujo=100, 200") == ("flow_per_hour", ["100", "200"])
    with pytest.raises(ValueError):
        parse_sweep("flujo")
    cs = combos(BASE, [("flow_per_hour", ["100", "200"]), ("idm.T", ["1", "2"])])
    assert len(cs) == 4
    assert cs[3][0] == {"flow_per_hour": 200.0, "idm.T": 2.0}
    assert cs[3][1].idm.T == 2.0


def test_campana_guarda_y_reanuda(tmp_path):
    sweeps = [("flow_per_hour", ["100", "250"])]
    run_campaign(BASE, sweeps, [120, 130], [1, 2], tmp_path, verbose=False)
    assert _n(tmp_path / "corridas.csv") == 8
    assert _n(tmp_path / "sondas.csv") == 16
    # Simula un corte: la última corrida no llegó a corridas.csv
    lineas = (tmp_path / "corridas.csv").read_text().splitlines()
    (tmp_path / "corridas.csv").write_text("\n".join(lineas[:-1]) + "\n")
    run_campaign(BASE, sweeps, [120, 130], [1, 2], tmp_path, verbose=False)
    assert _n(tmp_path / "corridas.csv") == 8
    assert _n(tmp_path / "sondas.csv") == 16  # sin duplicados
    # Ampliar con más semillas reutiliza lo hecho
    run_campaign(BASE, sweeps, [120, 130], [1, 2, 3], tmp_path, verbose=False)
    assert _n(tmp_path / "corridas.csv") == 12
    # Otra configuración en la misma carpeta: error
    with pytest.raises(ValueError):
        run_campaign(BASE, [("length", ["2000"])], [120], [1], tmp_path, verbose=False)


def test_paralelo_igual_que_serie(tmp_path):
    sweeps = [("flow_per_hour", ["150"])]
    a = run_campaign(BASE, sweeps, [130], [1, 2], tmp_path / "a", verbose=False)
    b = run_campaign(BASE, sweeps, [130], [1, 2], tmp_path / "b", workers=2, verbose=False)
    key = lambda r: (r["semilla"], r["indice"])  # noqa: E731
    with open(a / "sondas.csv") as fa, open(b / "sondas.csv") as fb:
        assert sorted(csv.DictReader(fa), key=key) == sorted(csv.DictReader(fb), key=key)


def test_sin_trafico_la_ganancia_es_la_ideal(tmp_path):
    base = SimConfig(length=3_000, flow_per_hour=0, warmup=10, n_probes=2, probe_spacing=30)
    run_campaign(base, [("length", ["2000", "3000"])], [120, 130], [1, 2], tmp_path, verbose=False)
    for g in Campaign(tmp_path).gain(120, 130):
        assert g["ganancia_s"] == pytest.approx(g["ideal_s"], abs=0.5)
        assert g["ideal_s"] == pytest.approx(g["length"] / (120 / 3.6) - g["length"] / (130 / 3.6), abs=0.5)


def test_graficas_de_campana(tmp_path):
    sweeps = [("flow_per_hour", ["100", "250"]), ("length", ["2000", "3000"]), ("v0_std_kmh", ["5", "10"])]
    run_campaign(BASE, sweeps, [120, 130], [1, 2], tmp_path, verbose=False)
    rutas = plot_campaign(tmp_path)
    nombres = {p.name for p in rutas}
    assert "ganancia.csv" in nombres and "resumen_sondas.csv" in nombres
    # el tercer parámetro separa en archivos
    assert any(n.startswith("ganancia__v0_std_kmh=5") for n in nombres)
    assert all(p.exists() for p in rutas)
    rutas = plot_campaign(tmp_path, x="v0_std_kmh", serie="flow_per_hour", salida=tmp_path / "otra")
    assert any(n.name.startswith("ganancia__length=2000") for n in rutas)
    with pytest.raises(ValueError):
        plot_campaign(tmp_path, x="idm.T")


def test_cli_campana_y_graficar(tmp_path, capsys):
    main(["campana", "--longitud", "2500", "--calentamiento", "100", "--sondas", "1",
          "--barrer", "flujo=100,200", "--velocidades", "120", "130", "--semillas", "2",
          "--salida", str(tmp_path)])
    assert (tmp_path / "graficas" / "ganancia.png").exists()
    main(["graficar", str(tmp_path), "--x", "flujo", "--salida", str(tmp_path / "g2")])
    assert (tmp_path / "g2" / "ganancia.png").exists()


def test_viajes_por_defecto_y_al_reanudar(tmp_path):
    sweeps = [("flow_per_hour", ["150"])]
    run_campaign(BASE, sweeps, [130], [1], tmp_path / "a", verbose=False)
    with open(tmp_path / "a" / "viajes.csv") as f:
        filas = list(csv.DictReader(f))
    assert filas and {"combo", "flow_per_hour", "v_sonda", "semilla", "tiempo_viaje"} <= set(filas[0])
    # una campaña vieja sin viajes se puede reanudar guardándolos en las corridas nuevas
    b = tmp_path / "b"
    run_campaign(BASE, sweeps, [130], [1], b, guardar_viajes=False, verbose=False)
    assert not (b / "viajes.csv").exists()
    run_campaign(BASE, sweeps, [130], [1, 2], b, verbose=False)
    with open(b / "viajes.csv") as f:
        assert {r["semilla"] for r in csv.DictReader(f)} == {"2"}
    with open(b / "corridas.csv") as f:
        assert [r["con_viajes"] for r in csv.DictReader(f)] == ["0", "1"]


def test_cli_sin_viajes(tmp_path):
    main(["campana", "--longitud", "2000", "--calentamiento", "50", "--sondas", "1", "--velocidades", "130",
          "--semillas", "1", "--sin-viajes", "--salida", str(tmp_path)])
    assert not (tmp_path / "viajes.csv").exists()


def test_campana_con_trayectorias_solo_sondas(tmp_path):
    run_campaign(BASE, [], [130], [1], tmp_path, trayectorias=2.0, solo_sondas=True, verbose=False)
    archivo = tmp_path / "trayectorias" / "combo0_v130_s1.csv"
    with open(archivo) as f:
        filas = list(csv.DictReader(f))
    assert filas and all(r["sonda"] == "1" for r in filas)
