"""Conductores: cumplimiento de señales, tipos (prudente/normal/agresivo) e impaciencia.

Los rasgos de cada conductor se sortean con un generador aleatorio propio
(independiente de las llegadas), así que activar esto no cambia el tráfico: los
mismos vehículos llegan en los mismos instantes con las mismas velocidades.
"""

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class DriverModel:
    # --- señales (F022) ---
    limit_compliance: float = 1.0  # fracción que respeta los límites de velocidad
    excess_min: float = 0.10  # quien no respeta se pasa entre estos porcentajes del límite
    excess_max: float = 0.30
    no_pass_compliance: float = 1.0  # fracción que respeta las zonas de no rebase
    # --- tipos de conductor (F023) ---
    share_cautious: float = 0.0  # fracción de prudentes
    share_aggressive: float = 0.0  # fracción de agresivos
    cautious_guard: float = 1.5  # multiplica el margen con el contrario (t_guard)
    aggressive_guard: float = 0.5
    cautious_T: float = 1.3  # multiplica el intervalo con el de delante (IDM T)
    aggressive_T: float = 0.7
    cautious_dv: float = 1.5  # multiplica la diferencia de velocidad que hace falta para rebasar
    aggressive_dv: float = 0.5
    # impaciencia: tras `impatience_after` s atrapado, el margen baja hasta `impatience_floor`
    impatience_after: float = 0.0  # 0 = sin impaciencia
    impatience_full: float = 120.0  # s atrapado (además de `after`) para llegar al mínimo
    impatience_floor: float = 0.5  # fracción mínima del margen

    @property
    def active(self) -> bool:
        return (self.limit_compliance < 1.0 or self.no_pass_compliance < 1.0 or self.share_cautious > 0
                or self.share_aggressive > 0)

    def assign(self, veh, rng: np.random.Generator) -> None:
        """Sortea los rasgos de un conductor (siempre el mismo número de sorteos)."""
        u = rng.random(4)
        veh.limit_factor = 1.0 if u[0] < self.limit_compliance else 1.0 + (
            self.excess_min + (self.excess_max - self.excess_min) * u[1])
        veh.respects_no_pass = bool(u[2] < self.no_pass_compliance)
        if u[3] < self.share_cautious:
            veh.driver = "prudente"
        elif u[3] < self.share_cautious + self.share_aggressive:
            veh.driver = "agresivo"
        else:
            veh.driver = "normal"

    def guard_factor(self, veh) -> float:
        """Factor sobre los márgenes de rebase según el tipo y la impaciencia."""
        f = {"prudente": self.cautious_guard, "agresivo": self.aggressive_guard}.get(veh.driver, 1.0)
        if self.impatience_after > 0:
            espera = veh.t_stuck - self.impatience_after
            if espera > 0:
                f *= 1.0 - (1.0 - self.impatience_floor) * min(1.0, espera / self.impatience_full)
        return f

    def dv_factor(self, veh) -> float:
        return {"prudente": self.cautious_dv, "agresivo": self.aggressive_dv}.get(veh.driver, 1.0)

    def T_factor(self, veh) -> float:
        return {"prudente": self.cautious_T, "agresivo": self.aggressive_T}.get(veh.driver, 1.0)
