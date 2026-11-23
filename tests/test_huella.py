"""Huella de regresión: corridas cortas cuyos resultados deben quedar idénticos bit a bit.

Si un cambio altera la dinámica con todo lo nuevo apagado, esta prueba falla.
Para regenerar los valores (solo si el cambio de resultados es intencional):
    python tests/test_huella.py --actualizar
"""

import hashlib
import json
import sys
from pathlib import Path

try:
    import pytest
except ImportError:  # PyPy sin pytest: solo para comparar huellas
    pytest = None

from trafico import config as cfgmod
from trafico.simulation import SimConfig, run_simulation

DATOS = Path(__file__).parent / "data" / "huella.json"

# Solo los campos de la dinámica de las fases 1-3: columnas nuevas no cambian la huella.
CAMPOS = ("id", "sentido", "v0_kmh", "sonda", "t_entrada", "t_salida", "tiempo_viaje", "rebases", "abortos",
          "veces_rebasado", "alcances", "t_lento", "t_espera_entrada", "frenado_emergencia", "clase")

_BASE = SimConfig(length=10_000, flow_per_hour=250, warmup=600, n_probes=4, probe_spacing=60)


def escenarios() -> dict:
    return {
        "simple_recta": _BASE,
        "simple_curvas": cfgmod.set_param(_BASE, "trazado", "pocas"),
        "sin_rebases": cfgmod.set_param(_BASE, "overtaking", "none"),
        "realista_montana": cfgmod.set_param(cfgmod.realista(cfgmod.set_param(
            cfgmod.set_param(_BASE, "relieve", "montanoso"), "trazado", "pocas")), "camiones", 0.2),
        "realista_recta": cfgmod.realista(_BASE),
    }


def huella(cfg: SimConfig, seed: int = 3, v: float = 130) -> str:
    res = run_simulation(cfg, v, seed)
    filas = [[repr(t[c]) for c in CAMPOS] for t in sorted(res.trips, key=lambda t: t["id"])]
    filas.append([repr(p.travel_time) for p in res.probes])
    filas.append([res.collisions, res.emergency_vehicles])
    return hashlib.sha256(json.dumps(filas).encode()).hexdigest()


def _param(f):
    return pytest.mark.parametrize("nombre", list(escenarios()))(f) if pytest else f


@_param
def test_huella(nombre):
    esperado = json.loads(DATOS.read_text())[nombre]
    assert huella(escenarios()[nombre]) == esperado, f"cambió la dinámica de {nombre}"


if __name__ == "__main__" and "--mostrar" in sys.argv:
    print({k: huella(c) for k, c in escenarios().items()})
elif __name__ == "__main__" and "--actualizar" in sys.argv:
    DATOS.write_text(json.dumps({k: huella(c) for k, c in escenarios().items()}, indent=2) + "\n")
    print(DATOS.read_text())
