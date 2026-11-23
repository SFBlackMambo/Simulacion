"""Línea de comandos: `trafico <comando>` o `python -m trafico <comando>`.

Comandos:
    corrida   una simulación con todos los datos y gráficas de exploración
    campana   muchas simulaciones barriendo parámetros (datos para analizar)
    graficar  gráficas de una campaña ya corrida
    animar    animación en vivo de una corrida (requiere pygame-ce)
    menu      menú interactivo
"""

import argparse
import sys
import time
from pathlib import Path

from . import config as cfgmod
from .simulation import MODOS, SimConfig


def add_config_args(ap: argparse.ArgumentParser, defaults: SimConfig) -> None:
    g = ap.add_argument_group("tráfico y carretera")
    g.add_argument("--modo", choices=MODOS, default=defaults.mode,
                   help="flujo: llegadas por hora; lleno: N vehículos siempre; total: entran N y termina")
    g.add_argument("--flujo", type=float, default=defaults.flow_per_hour, help="veh/h por sentido")
    g.add_argument("--vehiculos", type=int, default=defaults.n_vehicles,
                   help="vehículos por sentido (modos lleno y total)")
    g.add_argument("--longitud", type=float, default=defaults.length, help="m")
    g.add_argument("--v-media", type=float, default=defaults.v0_mean_kmh, help="velocidad deseada media, km/h")
    g.add_argument("--sigma", type=float, default=defaults.v0_std_kmh, help="desviación de la velocidad deseada, km/h")
    g.add_argument("--calentamiento", type=float, default=defaults.warmup, help="s antes de la primera sonda")
    g.add_argument("--duracion", type=float, default=defaults.duration, help="s mínimos tras el calentamiento")
    g.add_argument("--sondas", type=int, default=defaults.n_probes, help="número de sondas")
    g.add_argument("--espaciado-sondas", type=float, default=defaults.probe_spacing, help="s entre sondas")
    g.add_argument("--sin-rebases", action="store_true", help="nadie puede rebasar")
    g.add_argument("--param", action="append", default=[], metavar="NOMBRE=VALOR",
                   help="cualquier otro parámetro, p. ej. idm.T=2.0 u overtaking.t_guard=8 (repetible)")


def config_from_args(args) -> SimConfig:
    cfg = SimConfig(
        mode=args.modo, flow_per_hour=args.flujo, n_vehicles=args.vehiculos, length=args.longitud,
        v0_mean_kmh=args.v_media, v0_std_kmh=args.sigma, warmup=args.calentamiento,
        duration=args.duracion, n_probes=args.sondas, probe_spacing=args.espaciado_sondas,
    )
    if args.sin_rebases:
        cfg = cfgmod.set_param(cfg, "overtaking", "none")
    for p in args.param:
        nombre, _, valor = p.partition("=")
        cfg = cfgmod.set_param(cfg, nombre.strip(), valor.strip())
    return cfg


# Valores por defecto pensados para cada uso
DEF_CORRIDA = SimConfig(flow_per_hour=200, warmup=900, n_probes=5, probe_spacing=120)


def cmd_corrida(argv=None) -> dict:
    from .single import run_single

    ap = argparse.ArgumentParser(prog="trafico corrida", description="Una simulación con todos los datos.")
    add_config_args(ap, DEF_CORRIDA)
    ap.add_argument("--vel-sonda", type=float, default=130, help="velocidad deseada de las sondas, km/h")
    ap.add_argument("--semilla", type=int, default=1)
    ap.add_argument("--fotos", type=float, default=5.0, help="s entre fotos de posiciones")
    ap.add_argument("--sin-graficas", action="store_true")
    ap.add_argument("--salida", default=None, help="carpeta (por defecto results/corrida_<fecha>)")
    args = ap.parse_args(argv)
    cfg = config_from_args(args)
    out = Path(args.salida or f"results/corrida_{time.strftime('%Y%m%d_%H%M%S')}")
    t0 = time.time()
    print(f"Corriendo ({cfg.mode}, {cfg.length / 1000:g} km)...", flush=True)
    r = run_single(cfg, args.vel_sonda, args.semilla, out, args.fotos, graficas=not args.sin_graficas)
    print(f"Listo en {time.time() - t0:.0f} s. Datos y gráficas en {out}/")
    print(f"  vehículos que salieron: {r['vehiculos_que_salieron']}  "
          f"retraso medio: {r['retraso_medio_s']:.1f} s  rebases: {r['rebases_completados']} "
          f"(abortados {r['rebases_abortados']})  colisiones: {r['colisiones']}")
    if r["sondas"]["n"]:
        s = r["sondas"]
        print(f"  sondas a {args.vel_sonda:g} km/h: tiempo {s['tiempo_viaje_medio_s']:.0f} s, "
              f"retraso {s['retraso_medio_s']:.1f} s, rebases {s['rebases_medios']:.1f}, "
              f"alcances {s['alcances_medios']:.1f}")
    return r


COMANDOS = {"corrida": cmd_corrida}


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if not argv or argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, resto = argv[0], argv[1:]
    if cmd not in COMANDOS:
        print(f"comando desconocido: {cmd}\n{__doc__}")
        sys.exit(2)
    COMANDOS[cmd](resto)
