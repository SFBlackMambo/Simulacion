"""Línea de comandos: `trafico <comando>` o `python -m trafico <comando>`.

Comandos:
    corrida   una simulación con todos los datos y gráficas de exploración
    campana   muchas simulaciones barriendo parámetros (datos para analizar)
    graficar  gráficas de una campaña ya corrida
    animar    animación en vivo de una corrida (requiere pygame-ce)
    menu      menú interactivo (también si se llama sin comando)
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
    from .geometry import PRESETS

    g.add_argument("--trazado", choices=list(PRESETS), default=defaults.trazado,
                   help="tipo de carretera: " + "; ".join(f"{k}: {v.descripcion}" for k, v in PRESETS.items()))
    from .geometry import RELIEVES

    g.add_argument("--relieve", choices=list(RELIEVES), default=defaults.relieve,
                   help="pendientes: " + "; ".join(f"{k}: {v.descripcion}" for k, v in RELIEVES.items()))
    g.add_argument("--camiones", type=float, default=defaults.trucks.share,
                   help="fracción de camiones en el tráfico (0 a 1)")
    g.add_argument("--semilla-trazado", type=int, default=defaults.geometry_seed,
                   help="trazado concreto (0: uno distinto en cada réplica, según la semilla del tráfico)")
    g.add_argument("--sin-rebases", action="store_true", help="nadie puede rebasar")
    g.add_argument("--realista", action="store_true",
                   help="10%% camiones, cambio de carril de 3 s, rebase en cadena con visión tapada, "
                        "conductores prudentes/agresivos con impaciencia, reacción de 1 s y no rebase donde no se ve")
    g.add_argument("--param", action="append", default=[], metavar="NOMBRE=VALOR",
                   help="cualquier otro parámetro, p. ej. idm.T=2.0 u overtaking.t_guard=8 (repetible)")


def config_from_args(args) -> SimConfig:
    cfg = SimConfig(
        mode=args.modo, flow_per_hour=args.flujo, n_vehicles=args.vehiculos, length=args.longitud,
        v0_mean_kmh=args.v_media, v0_std_kmh=args.sigma, warmup=args.calentamiento,
        duration=args.duracion, n_probes=args.sondas, probe_spacing=args.espaciado_sondas,
        trazado=args.trazado, geometry_seed=args.semilla_trazado, relieve=args.relieve,
    )
    if args.camiones:
        cfg = cfgmod.set_param(cfg, "trucks.share", args.camiones)
    if args.sin_rebases:
        cfg = cfgmod.set_param(cfg, "overtaking", "none")
    if args.realista:
        cfg = cfgmod.realista(cfg)
        if args.camiones:
            cfg = cfgmod.set_param(cfg, "trucks.share", args.camiones)
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
    t = r["trazado"]
    if t["curvas"]:
        print(f"  trazado: {t['curvas']} curvas, {t['pct_en_curva']}% en curva, "
              f"{t['pct_no_rebase']}% sin visibilidad para rebasar, radio mínimo {t['radio_min_m']:.0f} m")
    if t["pendiente_max_pct"]:
        print(f"  relieve: pendiente máxima {t['pendiente_max_pct']}%, {t['pct_pendiente_fuerte']}% del recorrido "
              f"con más de 3%, {t['desnivel_subida_m']:.0f} m de subida acumulada")
    print(f"  vehículos que salieron: {r['vehiculos_que_salieron']}  "
          f"retraso medio: {r['retraso_medio_s']:.1f} s  rebases: {r['rebases_completados']} "
          f"(abortados {r['rebases_abortados']})  colisiones: {r['colisiones']}")
    if r["sondas"]["n"]:
        s = r["sondas"]
        print(f"  sondas a {args.vel_sonda:g} km/h: tiempo {s['tiempo_viaje_medio_s']:.0f} s, "
              f"retraso {s['retraso_medio_s']:.1f} s, rebases {s['rebases_medios']:.1f}, "
              f"alcances {s['alcances_medios']:.1f}")
    return r


DEF_CAMPANA = SimConfig(n_probes=20)


def cmd_campana(argv=None):
    from .campaign import parse_sweep, run_campaign

    ap = argparse.ArgumentParser(
        prog="trafico campana",
        description="Muchas simulaciones barriendo parámetros. Se puede reanudar con el mismo comando.",
        epilog="Ejemplo: trafico campana --barrer flujo=100,200,300 --barrer longitud=10000,20000 "
               "--velocidades 120 130 --semillas 8 --nucleos 8 --salida results/camp1",
    )
    add_config_args(ap, DEF_CAMPANA)
    ap.add_argument("--barrer", action="append", default=[], metavar="NOMBRE=V1,V2,...",
                    help="parámetro a barrer (repetible: se combinan todos)")
    ap.add_argument("--velocidades", type=float, nargs="+", default=[120, 130], help="velocidades de sonda, km/h")
    ap.add_argument("--semillas", type=int, default=8, help="réplicas por combinación")
    ap.add_argument("--nucleos", type=int, default=1, help="procesos en paralelo")
    ap.add_argument("--viajes", action="store_true", help=argparse.SUPPRESS)  # ya es lo normal; se acepta por compatibilidad
    ap.add_argument("--sin-viajes", action="store_true",
                    help="no guardar viajes.csv (el viaje de cada vehículo; se guarda por defecto)")
    ap.add_argument("--sin-graficas", action="store_true")
    ap.add_argument("--rapido", action="store_true",
                    help="simular con PyPy (de 2 a 5 veces más rápido; instálalo con scripts/instalar_pypy.sh)")
    ap.add_argument("--salida", required=True, help="carpeta de la campaña")
    args = ap.parse_args(argv)
    if args.rapido:
        return _campana_con_pypy(argv, args)
    base = config_from_args(args)
    sweeps = [parse_sweep(b) for b in args.barrer]
    out = run_campaign(base, sweeps, args.velocidades, list(range(1, args.semillas + 1)), args.salida,
                       workers=args.nucleos, guardar_viajes=not args.sin_viajes)
    if sweeps and not args.sin_graficas:
        try:
            from .analysis import plot_campaign

            rutas = plot_campaign(out)
            print(f"Gráficas y tablas en {rutas[0].parent}/")
        except ImportError:  # p. ej. PyPy sin matplotlib
            print(f"Sin gráficas (falta matplotlib). Hazlas con: trafico graficar {out}")
    print(f"Datos en {out}/")
    return out


def pypy_path() -> Path | None:
    """Python de PyPy del proyecto (.venv-pypy) o el de la variable TRAFICO_PYPY."""
    import os

    env = os.environ.get("TRAFICO_PYPY")
    candidatos = [Path(env)] if env else []
    raiz = Path(__file__).resolve().parents[2]
    candidatos.append(raiz / ".venv-pypy" / "bin" / "python")
    return next((c for c in candidatos if c.exists()), None)


def _campana_con_pypy(argv, args):
    """Corre la simulación de la campaña con PyPy y después las gráficas con este Python."""
    import subprocess

    from .analysis import plot_campaign

    pypy = pypy_path()
    if pypy is None:
        print("No encontré PyPy. Instálalo con:  bash scripts/instalar_pypy.sh   (o quita --rapido)")
        sys.exit(1)
    resto = [a for a in argv if a not in ("--rapido",)]
    if "--sin-graficas" not in resto:
        resto.append("--sin-graficas")
    print(f"Simulando con PyPy ({pypy})...", flush=True)
    r = subprocess.run([str(pypy), "-m", "trafico", "campana", *resto])
    if r.returncode != 0:
        sys.exit(r.returncode)
    out = Path(args.salida)
    if args.barrer and not args.sin_graficas:
        rutas = plot_campaign(out)
        print(f"Gráficas y tablas en {rutas[0].parent}/")
    return out


def cmd_graficar(argv=None):
    from .analysis import plot_campaign

    ap = argparse.ArgumentParser(prog="trafico graficar", description="Gráficas de una campaña ya corrida.")
    ap.add_argument("carpeta")
    ap.add_argument("--x", default=None, help="parámetro del eje x (por defecto el primero barrido)")
    ap.add_argument("--serie", default=None, help="parámetro que separa las líneas (por defecto el segundo)")
    ap.add_argument("--comparar", type=float, nargs=2, default=None, metavar=("LENTA", "RAPIDA"))
    ap.add_argument("--salida", default=None)
    args = ap.parse_args(argv)
    nombre = cfgmod.nombre_real
    rutas = plot_campaign(args.carpeta, nombre(args.x) if args.x else None,
                          nombre(args.serie) if args.serie else None, args.comparar, args.salida)
    print(f"{len(rutas)} archivos en {rutas[0].parent}/")
    return rutas


DEF_ANIMAR = SimConfig(mode="lleno", n_vehicles=70, warmup=30, n_probes=5, probe_spacing=150)


def cmd_animar(argv=None):
    try:
        import pygame  # noqa: F401
    except ImportError:
        print('Falta pygame-ce. Instálalo con:  pip install -e ".[anim]"')
        sys.exit(1)
    from .animation import animar, captura

    ap = argparse.ArgumentParser(prog="trafico animar", description="Animación en vivo de una corrida.")
    add_config_args(ap, DEF_ANIMAR)
    ap.add_argument("--vel-sonda", type=float, default=130)
    ap.add_argument("--semilla", type=int, default=1)
    ap.add_argument("--pantalla-completa", action="store_true")
    ap.add_argument("--ancho", type=int, default=1600)
    ap.add_argument("--alto", type=int, default=900)
    ap.add_argument("--velocidad", type=int, default=5, help="segundos simulados por segundo real")
    ap.add_argument("--ventana-km", type=float, default=0.8, help="km visibles en el tramo ampliado")
    ap.add_argument("--captura", default=None, help="no abre ventana: guarda una imagen PNG y sale")
    ap.add_argument("--captura-en", type=float, default=600, help="s simulados antes de la captura")
    args = ap.parse_args(argv)
    cfg = config_from_args(args)
    kw = dict(size=(args.ancho, args.alto), velocidad=args.velocidad, ventana_km=args.ventana_km)
    if args.captura:
        captura(cfg, args.captura, frames=2, probe_v0_kmh=args.vel_sonda, seed=args.semilla,
                sim_segundos=args.captura_en, **kw)
        print(f"Captura en {args.captura}")
        return
    animar(cfg, args.vel_sonda, args.semilla, fullscreen=args.pantalla_completa, **kw)


def cmd_menu(argv=None):
    from .menu import cmd_menu as _menu

    _menu(argv)


COMANDOS = {"menu": cmd_menu, "corrida": cmd_corrida, "animar": cmd_animar, "campana": cmd_campana, "graficar": cmd_graficar}


def main(argv=None) -> None:
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        argv = ["menu"]
    if argv[0] in ("-h", "--help"):
        print(__doc__)
        return
    cmd, resto = argv[0], argv[1:]
    if cmd not in COMANDOS:
        print(f"comando desconocido: {cmd}\n{__doc__}")
        sys.exit(2)
    COMANDOS[cmd](resto)
