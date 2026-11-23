"""Menú interactivo en la terminal.

Hace preguntas con valores por defecto (Enter acepta) y al final muestra el
comando equivalente, para poder repetir exactamente la misma corrida.
"""

import os
import shlex
import time

PARAMS_BARRIDO = [
    ("trazado", "Tipo de carretera (recta, pocas, muchas, montana)", "recta,pocas,muchas"),
    ("relieve", "Relieve (plano, lomerio, montanoso)", "plano,lomerio,montanoso"),
    ("camiones", "Fracción de camiones (0 a 1)", "0,0.1,0.25"),
    ("flujo", "Flujo por sentido (veh/h)", "100,200,300,450"),
    ("longitud", "Longitud de la carretera (m)", "10000,20000,40000"),
    ("vehiculos", "Vehículos por sentido (modos lleno/total)", "40,80,120"),
    ("sigma", "Dispersión de velocidades deseadas (km/h)", "5,10,15"),
    ("v_media", "Velocidad deseada media (km/h)", "90,100,110"),
    ("overtaking.t_guard", "Margen con el tráfico contrario (s)", "3,6,10"),
    ("idm.T", "Intervalo con el de delante (s)", "1.0,1.5,2.0"),
]


class Menu:
    def __init__(self, entrada=input, salida=print, ejecutar=True):
        self.entrada = entrada
        self.out = salida
        self.ejecutar = ejecutar
        self.ultimo: list[str] | None = None  # último comando armado

    # --- preguntas ---------------------------------------------------------
    def preguntar(self, texto: str, defecto=None, tipo=str, opciones=None):
        sufijo = f" [{defecto}]" if defecto is not None else ""
        while True:
            r = self.entrada(f"{texto}{sufijo}: ").strip()
            if not r and defecto is not None:
                r = str(defecto)
            if opciones and r not in opciones:
                self.out(f"  Opciones: {', '.join(opciones)}")
                continue
            try:
                return tipo(r)
            except ValueError:
                self.out("  Valor no válido, intenta de nuevo.")

    def elegir(self, titulo: str, opciones: list[tuple[str, str]]) -> str:
        self.out(f"\n{titulo}")
        for clave, texto in opciones:
            self.out(f"  {clave}) {texto}")
        return self.preguntar("Opción", opciones[0][0], opciones=[c for c, _ in opciones])

    def si_no(self, texto: str, defecto: bool = False) -> bool:
        r = self.preguntar(texto + " (s/n)", "s" if defecto else "n", opciones=["s", "n", "si", "no", "S", "N"])
        return r.lower().startswith("s")

    # --- bloques comunes ---------------------------------------------------
    def trafico(self, defecto_modo="flujo", flujo=200, vehiculos=70, longitud_km=20.0) -> list[str]:
        modo = self.elegir("¿Cómo se genera el tráfico?", [
            ("1", "Por flujo: llegan vehículos al azar, tantos por hora"),
            ("2", "Carretera llena: siempre hay N vehículos por sentido"),
            ("3", "Cantidad total: entran exactamente N por sentido y termina"),
        ] if defecto_modo == "flujo" else [
            ("2", "Carretera llena: siempre hay N vehículos por sentido"),
            ("1", "Por flujo: llegan vehículos al azar, tantos por hora"),
            ("3", "Cantidad total: entran exactamente N por sentido y termina"),
        ])
        args = ["--modo", {"1": "flujo", "2": "lleno", "3": "total"}[modo]]
        if modo in ("1", "3"):
            args += ["--flujo", _fmt(self.preguntar("Vehículos por hora en cada sentido", flujo, float))]
        if modo in ("2", "3"):
            args += ["--vehiculos", str(self.preguntar("Vehículos por sentido", vehiculos, int))]
        km = self.preguntar("Longitud de la carretera (km)", longitud_km, float)
        args += ["--longitud", _fmt(km * 1000)]
        args += self.trazado()
        args += self.relieve_y_modelo()
        return args

    def relieve_y_modelo(self) -> list[str]:
        """Relieve, camiones y comportamiento realista (fase 3)."""
        from .geometry import RELIEVES

        nombres = list(RELIEVES)
        op = self.elegir("¿Qué relieve tiene?", [(str(i + 1), RELIEVES[n].descripcion) for i, n in enumerate(nombres)])
        args = [] if nombres[int(op) - 1] == "plano" else ["--relieve", nombres[int(op) - 1]]
        realista = self.si_no("¿Comportamiento realista? (camiones, cambio de carril de 3 s, rebase en cadena, "
                              "conductores distintos, reacción de 1 s)", False)
        cam = self.preguntar("Porcentaje de camiones", 10 if realista else 0, float)
        if realista:
            args.append("--realista")
        if cam or realista:
            args += ["--camiones", _fmt(cam / 100.0)]
        return args

    def trazado(self) -> list[str]:
        """Pregunta por las curvas (si el modelo de curvas está disponible)."""
        try:
            from .geometry import PRESETS
        except ImportError:
            return []
        nombres = list(PRESETS)
        op = self.elegir("¿Cómo es la carretera?", [(str(i + 1), PRESETS[n].descripcion) for i, n in enumerate(nombres)])
        nombre = nombres[int(op) - 1]
        if nombre == "recta":
            return []
        args = ["--trazado", nombre]
        sem = self.preguntar("Semilla del trazado (0 = uno distinto en cada réplica)", 0, int)
        if sem:
            args += ["--semilla-trazado", str(sem)]
        return args

    # --- modos -------------------------------------------------------------
    def corrida(self) -> list[str]:
        args = self.trafico()
        args += ["--vel-sonda", _fmt(self.preguntar("Velocidad deseada de las sondas (km/h)", 130, float))]
        args += ["--sondas", str(self.preguntar("¿Cuántas sondas?", 5, int))]
        args += ["--semilla", str(self.preguntar("Semilla (mismo número = mismo tráfico)", 1, int))]
        args += ["--salida", self.preguntar("Carpeta de salida", f"results/corrida_{time.strftime('%Y%m%d_%H%M%S')}")]
        return ["corrida", *args]

    def animacion(self) -> list[str]:
        args = self.trafico(defecto_modo="lleno")
        args += ["--vel-sonda", _fmt(self.preguntar("Velocidad deseada de las sondas (km/h)", 130, float))]
        args += ["--sondas", str(self.preguntar("¿Cuántas sondas?", 5, int))]
        args += ["--semilla", str(self.preguntar("Semilla", 1, int))]
        if self.si_no("¿Pantalla completa?", False):
            args.append("--pantalla-completa")
        return ["animar", *args]

    def campana(self) -> list[str]:
        self.out("\nUna campaña combina todos los valores de los parámetros que elijas.")
        args = self.trafico()
        barridos = []
        while True:
            opciones = [(str(i + 1), f"{t}  (p. ej. {ej})") for i, (_, t, ej) in enumerate(PARAMS_BARRIDO)]
            opciones.append(("0", "Listo, no barrer más" if barridos else "Ninguno (solo réplicas)"))
            op = self.elegir("¿Qué parámetro quieres barrer?", opciones)
            if op == "0":
                break
            nombre, _, ejemplo = PARAMS_BARRIDO[int(op) - 1]
            valores = self.preguntar("Valores separados por comas", ejemplo)
            barridos += ["--barrer", f"{nombre}={valores.replace(' ', '')}"]
        vel = self.preguntar("Velocidades de sonda a comparar (km/h, separadas por espacios)", "120 130")
        args += barridos + ["--velocidades", *vel.split()]
        args += ["--sondas", str(self.preguntar("Sondas por corrida", 20, int))]
        args += ["--semillas", str(self.preguntar("Réplicas (semillas) por combinación", 8, int))]
        args += ["--nucleos", str(self.preguntar("Núcleos a usar", max(1, (os.cpu_count() or 2) - 1), int))]
        args += ["--salida", self.preguntar("Carpeta de la campaña", f"results/campana_{time.strftime('%Y%m%d_%H%M%S')}")]
        if self.si_no("¿Guardar también el viaje de cada vehículo? (archivos grandes)", False):
            args.append("--viajes")
        return ["campana", *args]

    def graficar(self) -> list[str]:
        carpeta = self.preguntar("Carpeta de la campaña", "results/campana")
        args = ["graficar", carpeta]
        x = self.preguntar("Parámetro del eje x (Enter: el primero barrido)", "")
        if x:
            args += ["--x", x]
        return args

    # --- bucle principal ---------------------------------------------------
    def run(self) -> None:
        from .cli import COMANDOS

        while True:
            op = self.elegir("=== Simulación de tráfico en carretera de dos carriles ===", [
                ("1", "Corrida única: una simulación con todos los datos y gráficas"),
                ("2", "Animación: ver la carretera en vivo (para mostrar)"),
                ("3", "Campaña: muchas simulaciones para obtener datos"),
                ("4", "Graficar una campaña ya corrida"),
                ("0", "Salir"),
            ])
            if op == "0":
                return
            argv = {"1": self.corrida, "2": self.animacion, "3": self.campana, "4": self.graficar}[op]()
            self.ultimo = argv
            self.out("\nComando equivalente (para repetirlo):\n  trafico " + shlex.join(argv) + "\n")
            if self.ejecutar:
                try:
                    COMANDOS[argv[0]](argv[1:])
                except SystemExit:
                    pass
                except Exception as e:  # el menú sigue aunque una corrida falle
                    self.out(f"Error: {e}")
            if not self.si_no("¿Hacer otra cosa?", True):
                return


def _fmt(x: float) -> str:
    return f"{x:g}"


def cmd_menu(argv=None) -> None:
    try:
        Menu().run()
    except (KeyboardInterrupt, EOFError):
        print()
