"""Registro de datos de una corrida: viajes, eventos de rebase y fotos periódicas.

El registro es opcional. Sin él, la simulación hace exactamente lo mismo (el
registro solo lee el estado, nunca lo cambia), así que encenderlo no altera los
resultados.
"""

import csv
import math
from pathlib import Path

from .slopes import AUTO_GRADES
from .vehicle import Vehicle, ms_a_kmh

# Tipos de evento
REBASE_INICIO = "rebase_inicio"
REBASE_FIN = "rebase_fin"
REBASE_ABORTO = "rebase_aborto"

CAMPOS_VIAJE = [
    "id", "sentido", "v0_kmh", "sonda", "viaje_completo", "t_entrada", "t_salida",
    "tiempo_viaje", "tiempo_libre", "retraso", "rebases", "abortos", "veces_rebasado",
    "alcances", "t_lento", "t_espera_entrada", "frenado_emergencia", "clase", "rebases_en_cadena", "conductor",
    "v_media_kmh", "t_headway_2_5", "t_headway_3", "pct_tiempo_siguiendo", "t_carril_contrario",
    "ttc_min_lider", "ttc_min_contrario", "conflictos_lider", "conflictos_contrario",
    "factor_limite", "potencia_w_kg", "lb_hp",
]
CAMPOS_EVENTO = ["t", "tipo", "id", "sentido", "x", "n", "en_cadena"]
CAMPOS_FOTO = ["t", "id", "sentido", "x", "v_kmh", "v0_kmh", "carril", "sonda", "estado", "v_permitida_kmh", "clase"]


def viaje(veh: Vehicle, free_time: float, length: float = 0.0) -> dict:
    """Resumen del viaje de un vehículo que ya salió (`length`: lo que recorrió, m)."""
    tt = veh.t_exit - veh.t_entry
    pot = (veh.grades or AUTO_GRADES).power_w_kg
    return {
        "id": veh.id,
        "sentido": veh.direction,
        "v0_kmh": round(ms_a_kmh(veh.v0), 3),
        "sonda": int(veh.probe),
        "viaje_completo": int(veh.full_trip),
        "t_entrada": round(veh.t_entry, 2),
        "t_salida": round(veh.t_exit, 2),
        "tiempo_viaje": round(tt, 3),
        "tiempo_libre": round(free_time, 3),
        "retraso": round(tt - free_time, 3),
        "rebases": veh.overtakes,
        "abortos": veh.aborts,
        "veces_rebasado": veh.overtaken,
        "alcances": veh.catchups,
        "t_lento": round(veh.t_slow, 2),
        "t_espera_entrada": round(veh.t_wait_entry, 2),
        "frenado_emergencia": int(veh.emergency_steps > 0),
        "clase": veh.kind,
        "rebases_en_cadena": veh.convoy_overtakes,
        "conductor": veh.driver,
        "v_media_kmh": round(ms_a_kmh(length / tt), 3) if length and tt > 0 else "",
        "t_headway_2_5": round(veh.t_hw25, 2),
        "t_headway_3": round(veh.t_hw3, 2),
        "pct_tiempo_siguiendo": round(100.0 * veh.t_hw3 / tt, 2) if tt > 0 else "",
        "t_carril_contrario": round(veh.t_opposite, 2),
        "ttc_min_lider": _num(veh.ttc_leader_min),
        "ttc_min_contrario": _num(veh.ttc_opp_min),
        "conflictos_lider": veh.conflicts_leader,
        "conflictos_contrario": veh.conflicts_opp,
        "factor_limite": round(veh.limit_factor, 4),
        "potencia_w_kg": round(pot, 2),
        "lb_hp": round(1644.0 * 0.87 / pot, 1) if veh.kind == "camion" else "",
    }


def _num(x: float):
    """Número redondeado, o vacío si no hubo (infinito)."""
    return round(x, 3) if math.isfinite(x) else ""


class Recorder:
    """Guarda eventos de rebase y fotos de posiciones cada `snapshot_interval` s.

    Con `snapshot_interval=None` no toma fotos (solo eventos).
    """

    def __init__(self, snapshot_interval: float | None = 5.0, events: bool = True) -> None:
        self.snapshot_interval = snapshot_interval
        self.keep_events = events
        self.events: list[dict] = []
        self.snapshots: list[tuple] = []
        self._next_snapshot = 0.0

    def event(self, road, kind: str, veh: Vehicle, n: int = 0, cadena: bool = False) -> None:
        if self.keep_events:
            self.events.append({
                "t": round(road.t, 2), "tipo": kind, "id": veh.id, "sentido": veh.direction,
                "x": round(road.position(veh), 1), "n": n, "en_cadena": int(cadena),
            })

    def on_step(self, road) -> None:
        if self.snapshot_interval is None or road.t + 1e-9 < self._next_snapshot:
            return
        t = round(road.t, 2)
        for v in road.vehicles:
            self.snapshots.append((
                t, v.id, v.direction, round(road.position(v), 1), round(ms_a_kmh(v.v), 2),
                round(ms_a_kmh(v.v0), 2), v.lane, int(v.probe), v.state, round(ms_a_kmh(v.v_des), 2), v.kind,
            ))
        self._next_snapshot += self.snapshot_interval

    def save(self, folder: str | Path) -> None:
        """Escribe `eventos.csv` y `fotos.csv` en `folder`."""
        folder = Path(folder)
        folder.mkdir(parents=True, exist_ok=True)
        write_csv(folder / "eventos.csv", CAMPOS_EVENTO, self.events)
        with open(folder / "fotos.csv", "w", newline="") as f:
            w = csv.writer(f)
            w.writerow(CAMPOS_FOTO)
            w.writerows(self.snapshots)


def write_csv(path: str | Path, fields: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
