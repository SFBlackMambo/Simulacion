"""La mejor velocidad (F036): tablas, gráficas y CLI a partir de una campaña chica."""

import csv
import math

import pytest

from trafico.analysis import Campaign
from trafico.campaign import run_campaign
from trafico.cli import escenarios_precios, main
from trafico.mejor import graficar, resumen_texto, tablas
from trafico.simulation import SimConfig

BASE = SimConfig(length=4_000, flow_per_hour=150, warmup=200, n_probes=3, probe_spacing=40)


@pytest.fixture(scope="module")
def campana(tmp_path_factory):
    out = tmp_path_factory.mktemp("mejor")
    run_campaign(BASE, [("flow_per_hour", ["100", "300"])], [90, 100, 120, 150], [1, 2, 3], out, workers=4,
                 verbose=False)
    return out


def test_tablas_por_velocidad(campana):
    filas, mejores = tablas(campana)
    assert len(filas) == 2 * 4
    f100 = [f for f in filas if f["v_sonda"] == 100.0]
    assert all(f["ganancia_vs_ref"] == 0 and f["v_referencia"] == 100.0 for f in f100)
    f90 = [f for f in filas if f["v_sonda"] == 90.0]
    assert all(math.isnan(f["ganancia_paso"]) for f in f90)
    for flujo in (100.0, 300.0):
        fs = sorted((f for f in filas if f["flow_per_hour"] == flujo), key=lambda f: f["v_sonda"])
        assert fs[-1]["tiempo_viaje"] < fs[0]["tiempo_viaje"]  # más rápido llega antes
        assert fs[-1]["l_100km"] > fs[0]["l_100km"]  # y gasta más
        assert fs[-1]["riesgo_potencia_muertos"] > fs[0]["riesgo_potencia_muertos"]
        for f in fs:
            partes = sum(f[f"medio_{k}"] for k in ("tiempo", "combustible", "co2", "accidentes"))
            assert partes == pytest.approx(f["costo_medio"], rel=1e-6)
    escs = {m["escenario"] for m in mejores}
    assert escs == {"bajo", "medio", "alto"}
    for m in mejores:
        costos = {v: m[f"costo_{v:g}"] for v in (90.0, 100.0, 120.0, 150.0)}
        assert m["v_optima"] == min(costos, key=costos.get)
        lo, hi = map(float, m["rango_empate"].split("-"))
        assert lo <= m["v_optima"] <= hi


def test_valor_del_tiempo_muy_alto_premia_ir_rapido(campana):
    precios = escenarios_precios(["medio"], ["valor_tiempo_h=5000"])
    _, mejores = tablas(campana, precios)
    assert all(m["v_optima"] >= 120 for m in mejores if m["flow_per_hour"] == 100.0)
    precios = escenarios_precios(["medio"], ["valor_tiempo_h=0"])
    _, mejores = tablas(campana, precios)
    assert all(m["v_optima"] == 90 for m in mejores)


def test_graficas_y_cli(campana, tmp_path):
    rutas = graficar(campana, salida=tmp_path)
    nombres = {p.name for p in rutas}
    assert {"mejor_tiempo.png", "mejor_costo_medio.png", "mejor_velocidad.csv"} <= nombres
    assert all(p.exists() for p in rutas)
    main(["graficar", str(campana), "--mejor", "--precios", "medio", "medio_kloeden", "--salida", str(tmp_path / "c")])
    with open(tmp_path / "c" / "mejor_velocidad.csv") as f:
        filas = list(csv.DictReader(f))
    assert {r["escenario"] for r in filas} == {"medio", "medio_kloeden"}
    assert "mejor" in resumen_texto(tablas(campana)[1], Campaign(campana))


def test_campana_vieja_sin_litros_da_error_claro(campana, tmp_path):
    import shutil

    vieja = tmp_path / "vieja"
    shutil.copytree(campana, vieja)
    with open(vieja / "sondas.csv") as f:
        r = csv.DictReader(f)
        campos = [c for c in r.fieldnames if c != "litros"]
        filas = [{c: x[c] for c in campos} for x in r]
    with open(vieja / "sondas.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(filas)
    with pytest.raises(ValueError, match="correrla de nuevo"):
        tablas(vieja)



def test_valor_de_equilibrio_coincide_con_el_costo(campana):
    filas, _ = tablas(campana)
    for f in filas:
        if f["v_sonda"] == 100.0:
            assert math.isnan(f["vtt_equilibrio"])
            continue
        vtt = f["vtt_equilibrio"]
        base = next(b for b in filas if b["v_sonda"] == 100.0 and b["flow_per_hour"] == f["flow_per_hour"])
        # con ese valor del tiempo, las dos velocidades cuestan lo mismo
        p = escenarios_precios(["medio"], [f"valor_tiempo_h={vtt}"])
        g, _ = tablas(campana, p)
        a = next(x for x in g if x["v_sonda"] == f["v_sonda"] and x["flow_per_hour"] == f["flow_per_hour"])
        b = next(x for x in g if x["v_sonda"] == 100.0 and x["flow_per_hour"] == f["flow_per_hour"])
        assert a["costo_medio"] == pytest.approx(b["costo_medio"], rel=1e-6)
        assert base["v_sonda"] == 100.0
