import pytest

from trafico.analysis import Campaign
from trafico.campaign import run_campaign
from trafico.geometry import PRESETS, Geometry, build_trazado, describe
from trafico.simulation import SimConfig, geometry_from_config, run_simulation


@pytest.mark.parametrize("nombre", list(PRESETS))
def test_trazados_validos_y_reproducibles(nombre):
    a = build_trazado(nombre, 20_000, seed=3)
    assert a == build_trazado(nombre, 20_000, seed=3)
    p = PRESETS[nombre]
    assert len(a) == round(p.curvas_por_km * 20)
    Geometry(20_000, a)  # sin solapes ni curvas fuera de la carretera
    for (_, b1, _), (a2, _, _) in zip(a, a[1:]):
        assert a2 - b1 >= p.recta_min - 0.2
    for _, _, r in a:
        assert p.r_min - 0.1 <= r <= p.r_max + 0.1


def test_semilla_distinta_trazado_distinto():
    assert build_trazado("muchas", 20_000, 1) != build_trazado("muchas", 20_000, 2)


def test_trazado_desconocido():
    with pytest.raises(ValueError):
        build_trazado("espiral", 1000, 1)


def test_mas_curvas_menos_visibilidad():
    d = {n: describe(geometry_from_config(SimConfig(trazado=n), 1), 20_000) for n in ("recta", "pocas", "muchas")}
    assert d["recta"]["curvas"] == 0
    assert d["recta"]["pct_no_rebase"] < d["pocas"]["pct_no_rebase"] < d["muchas"]["pct_no_rebase"]


def test_semilla_de_trazado_cero_sigue_al_trafico():
    cfg = SimConfig(trazado="muchas")
    assert geometry_from_config(cfg, 1).curves != geometry_from_config(cfg, 2).curves
    fijo = SimConfig(trazado="muchas", geometry_seed=7)
    assert geometry_from_config(fijo, 1).curves == geometry_from_config(fijo, 2).curves


def test_sin_trafico_con_curvas_la_sonda_no_pierde_tiempo():
    cfg = SimConfig(length=8_000, flow_per_hour=0, warmup=10, n_probes=2, probe_spacing=30, trazado="montana")
    r = run_simulation(cfg, 130, seed=2)
    for p in r.probes:
        assert p.delay == pytest.approx(0, abs=0.5)


def test_campana_recta_vs_curvas(tmp_path):
    base = SimConfig(length=6_000, flow_per_hour=200, warmup=300, n_probes=3, probe_spacing=40)
    run_campaign(base, [("trazado", ["recta", "muchas"])], [120, 130], [1, 2], tmp_path, verbose=False)
    camp = Campaign(tmp_path)
    gan = {g["trazado"]: g for g in camp.gain(120, 130)}
    # con curvas, la ganancia ideal (en vía libre) es menor: en las curvas todos van igual
    assert gan["muchas"]["ideal_s"] < gan["recta"]["ideal_s"]
    assert sum(int(r["colisiones"]) for r in camp.corridas) == 0
