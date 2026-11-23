import csv
from collections import Counter, defaultdict

from trafico.recorder import REBASE_ABORTO, REBASE_FIN, REBASE_INICIO, Recorder
from trafico.simulation import SimConfig, run_simulation

PEQ = SimConfig(length=6_000, flow_per_hour=300, warmup=400, n_probes=4, probe_spacing=60)


def test_registro_no_cambia_los_resultados():
    a = run_simulation(PEQ, 130, seed=2)
    b = run_simulation(PEQ, 130, seed=2, recorder=Recorder(snapshot_interval=2.0))
    assert [p.travel_time for p in a.probes] == [p.travel_time for p in b.probes]
    assert a.trips == b.trips


def test_viajes_de_todos_los_vehiculos():
    res = run_simulation(PEQ, 130, seed=2)
    assert len(res.trips) == res.background_finished + PEQ.n_probes
    assert sum(t["sonda"] for t in res.trips) == PEQ.n_probes
    assert {t["sentido"] for t in res.trips} == {1, -1}
    for t in res.trips:
        assert t["retraso"] > -1.0
        assert t["tiempo_viaje"] > 0


def test_eventos_cuadran_con_los_contadores():
    rec = Recorder(snapshot_interval=None)
    res = run_simulation(PEQ, 130, seed=2, recorder=rec)
    tipos = Counter(e["tipo"] for e in rec.events)
    assert tipos[REBASE_INICIO] > 0
    assert tipos[REBASE_INICIO] >= tipos[REBASE_FIN] + tipos[REBASE_ABORTO]
    rebasados = defaultdict(int)
    abortos = defaultdict(int)
    for e in rec.events:
        if e["tipo"] == REBASE_FIN:
            rebasados[e["id"]] += e["n"]
        elif e["tipo"] == REBASE_ABORTO:
            abortos[e["id"]] += 1
    for t in res.trips:
        assert t["rebases"] == rebasados[t["id"]]
        assert t["abortos"] == abortos[t["id"]]
    assert sum(t["veces_rebasado"] for t in res.trips) <= sum(rebasados.values())
    assert all(0 <= e["x"] <= PEQ.length for e in rec.events)
    assert rec.snapshots == []


def test_fotos_periodicas_en_coordenadas_de_la_carretera(tmp_path):
    rec = Recorder(snapshot_interval=5.0)
    run_simulation(PEQ, 130, seed=2, recorder=rec)
    tiempos = sorted({s[0] for s in rec.snapshots})
    assert len(tiempos) > 50
    pasos = {round(b - a, 1) for a, b in zip(tiempos, tiempos[1:])}
    assert pasos <= {5.0, 5.2}  # cada 5 s (redondeo al paso dt = 0.2)
    trayectorias = defaultdict(list)
    for t, vid, sentido, x, *_ in rec.snapshots:
        assert 0 <= x <= PEQ.length
        trayectorias[(vid, sentido)].append(x)
    for (_, sentido), xs in trayectorias.items():
        dif = [b - a for a, b in zip(xs, xs[1:])]
        assert all(d * sentido >= 0 for d in dif)  # cada uno avanza en su sentido
    rec.save(tmp_path)
    with open(tmp_path / "fotos.csv") as f:
        assert sum(1 for _ in csv.reader(f)) == len(rec.snapshots) + 1
    assert (tmp_path / "eventos.csv").exists()


def test_alcances_cuentan_episodios_lentos():
    res = run_simulation(PEQ, 130, seed=2)
    for t in res.trips:
        if t["t_lento"] == 0:
            assert t["alcances"] == 0
    assert any(t["alcances"] > 0 for t in res.trips)
