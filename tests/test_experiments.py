from trafico.experiments import con_flujo, run_replicas
from trafico.simulation import SimConfig

CFG = SimConfig(length=6_000, flow_per_hour=200, warmup=400, n_probes=4, probe_spacing=100)


def tiempos(res):
    return {k: [p.travel_time for p in r.probes] for k, r in res.items()}


def test_replicas_devuelven_una_corrida_por_velocidad_y_semilla():
    res = run_replicas(CFG, [120, 130], [1, 2])
    assert set(res) == {(120, 1), (120, 2), (130, 1), (130, 2)}
    assert all(len(r.probes) == 4 for r in res.values())


def test_paralelo_da_lo_mismo_que_serie():
    serie = run_replicas(CFG, [120, 130], [1, 2], workers=1)
    paralelo = run_replicas(CFG, [120, 130], [1, 2], workers=2)
    assert tiempos(serie) == tiempos(paralelo)


def test_con_flujo_no_modifica_el_original():
    otro = con_flujo(CFG, 450)
    assert otro.flow_per_hour == 450 and CFG.flow_per_hour == 200
