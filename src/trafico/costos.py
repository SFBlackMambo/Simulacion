"""Riesgo y balance en dinero de un viaje. Se aplica después de simular: cambiar un precio no obliga
a volver a correr nada.

Riesgo: tres medidas que se reportan por separado (ninguna se mezcla con otra):

1. Modelo potencia (Nilsson 2004; exponentes de Elvik 2009 para carreteras rurales): el número de
   accidentes cambia como (v / v_ref)^k, con k = 4.1 para muertos, 2.6 para heridos graves y 1.1 para
   heridos leves. Se estimó para la velocidad media del flujo, no para un vehículo; aquí se aplica a la
   velocidad media del viaje como aproximación ("si todos fueran así").
2. Curva individual de Kloeden, Ponte y McLean (2001, carreteras rurales de Australia del Sur): riesgo
   relativo de verse en un accidente con heridos según cuánto se aleja de la velocidad media del tráfico,
   RR = exp(0.07039·Δv + 0.0008617·Δv²), Δv en km/h. Medida en −10 a +30 km/h aprox.; fuera de ahí es
   extrapolación.
3. Medidas del propio simulador: TTC mínimo, conflictos (TTC < 1.5 s), frenados de emergencia, tiempo
   en el carril contrario y choques. Están en sondas.csv y viajes.csv; no tienen precio.

Dinero (MXN): tiempo × valor del tiempo + litros × precio + CO2 × precio social + km × costo de los
accidentes por veh-km × riesgo relativo. Los precios son supuestos (ver docs/datos.md); por eso hay
tres escenarios, y se puede cambiar cualquiera con `con_precios(escenario, campo=valor)`.
"""

import dataclasses
import math
from dataclasses import dataclass

# Elvik (2009), carreteras rurales y autopistas
EXP_MUERTOS = 4.1
EXP_GRAVES = 2.6
EXP_LEVES = 1.1
KLOEDEN_A = 0.07039
KLOEDEN_B = 0.0008617


@dataclass(frozen=True)
class Precios:
    """Precios en MXN. Los accidentes van por veh-km a la velocidad de referencia `v_ref_kmh`."""

    valor_tiempo_h: float = 100.0  # por vehículo y hora (≈1.5 ocupantes)
    gasolina_l: float = 24.0
    diesel_l: float = 26.0
    co2_t: float = 2000.0  # costo social del carbono, por tonelada
    accidentes_vkm: float = 0.50  # costo esperado de los accidentes por veh-km a v_ref
    v_ref_kmh: float = 100.0
    # cómo se reparte ese costo entre la gravedad (para el modelo potencia)
    parte_muertos: float = 0.5
    parte_graves: float = 0.3
    parte_leves: float = 0.2
    riesgo: str = "nilsson"  # "nilsson" o "kloeden": qué riesgo se pone en dinero


ESCENARIOS = {
    "bajo": Precios(valor_tiempo_h=50.0, gasolina_l=22.0, diesel_l=24.0, co2_t=1000.0, accidentes_vkm=0.25),
    "medio": Precios(),
    "alto": Precios(valor_tiempo_h=200.0, gasolina_l=27.0, diesel_l=29.0, co2_t=3800.0, accidentes_vkm=1.0),
}


def con_precios(base: str | Precios = "medio", **cambios) -> Precios:
    """Un escenario con algunos precios cambiados (los valores pueden venir como texto)."""
    p = ESCENARIOS[base] if isinstance(base, str) else base
    tipos = {f.name: f.type for f in dataclasses.fields(Precios)}
    for k in cambios:
        if k not in tipos:
            raise KeyError(f"precio desconocido: {k}; opciones: {', '.join(tipos)}")
    return dataclasses.replace(p, **{k: (v if k == "riesgo" else float(v)) for k, v in cambios.items()})


def riesgo_nilsson(v_kmh: float, v_ref_kmh: float = 100.0) -> dict:
    """Riesgo relativo de accidentes con muertos, heridos graves y leves (modelo potencia)."""
    r = v_kmh / v_ref_kmh
    return {"muertos": r ** EXP_MUERTOS, "graves": r ** EXP_GRAVES, "leves": r ** EXP_LEVES}


def riesgo_kloeden(dv_kmh: float) -> float:
    """Riesgo relativo de accidente con heridos al ir `dv_kmh` por encima de la media del tráfico."""
    return math.exp(KLOEDEN_A * dv_kmh + KLOEDEN_B * dv_kmh * dv_kmh)


def riesgo_relativo(p: Precios, v_kmh: float, v_trafico_kmh: float | None = None) -> float:
    """Factor que multiplica el costo de los accidentes por veh-km según `p.riesgo`."""
    if p.riesgo == "kloeden":
        if v_trafico_kmh is None:
            raise ValueError("el riesgo de Kloeden necesita la velocidad media del tráfico")
        return riesgo_kloeden(v_kmh - v_trafico_kmh)
    if p.riesgo != "nilsson":
        raise ValueError(f"riesgo desconocido {p.riesgo!r}: nilsson o kloeden")
    r = riesgo_nilsson(v_kmh, p.v_ref_kmh)
    total = p.parte_muertos + p.parte_graves + p.parte_leves
    return (p.parte_muertos * r["muertos"] + p.parte_graves * r["graves"] + p.parte_leves * r["leves"]) / total


def balance(p: Precios, tiempo_s: float, litros: float, co2_kg: float, km: float, v_kmh: float,
            v_trafico_kmh: float | None = None, diesel: bool = False) -> dict:
    """Costo de un viaje en MXN, por partes, y el total."""
    out = {
        "tiempo": tiempo_s / 3600.0 * p.valor_tiempo_h,
        "combustible": litros * (p.diesel_l if diesel else p.gasolina_l),
        "co2": co2_kg / 1000.0 * p.co2_t,
        "accidentes": km * p.accidentes_vkm * riesgo_relativo(p, v_kmh, v_trafico_kmh),
    }
    out["total"] = sum(out.values())
    return out
