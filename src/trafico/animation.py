"""Animación en vivo de una corrida (pygame-ce), pensada para mostrar en pantalla grande.

Vista esquemática: arriba la carretera completa (mapa) y abajo un tramo ampliado
con los dos carriles. Cada coche tiene el color de su estado.

Controles:
    Espacio        pausa / continuar
    + / -          más o menos velocidad de simulación
    rueda / Z X    acercar / alejar
    ← →            mover la vista (desactiva el seguimiento)
    S              seguir a la sonda (Tab: siguiente sonda)
    clic en mapa   ir a ese punto
    R              reiniciar      F11  pantalla completa      Esc / Q  salir
"""

import math
import os

from .recorder import REBASE_ABORTO, REBASE_FIN
from .simulation import SimConfig, build_road, free_time, probe_times
from .vehicle import REBASANDO, REGRESANDO, kmh_a_ms, ms_a_kmh

# Paleta (modo oscuro). Los tres tonos validan todas las parejas (CVD y visión normal).
FONDO = (26, 26, 25)  # #1a1a19
ASFALTO = (56, 56, 53)  # #383835
BORDE = (82, 81, 78)
TEXTO = (240, 239, 236)  # #f0efec
TEXTO2 = (195, 194, 183)  # #c3c2b7
LINEA = (240, 239, 236)
AMARILLO = (201, 133, 0)  # línea central continua (no rebasar)
CURVA = (40, 40, 38)
C_LIBRE = (57, 135, 229)  # #3987e5 azul
C_SONDA = (217, 89, 38)  # #d95926 naranja
C_REBASE = (25, 158, 112)  # #199e70 aqua
C_ATRAPADO = (195, 194, 183)  # gris neutro: va por debajo de su velocidad deseada

VELOCIDADES = [1, 2, 5, 10, 20, 50, 100]
ESTADOS = [("Libre", C_LIBRE), ("Atrapado detrás de otro", C_ATRAPADO), ("Rebasando", C_REBASE),
           ("Sonda", C_SONDA)]


def color_de(veh) -> tuple:
    if veh.probe:
        return C_SONDA
    if veh.state in (REBASANDO, REGRESANDO):
        return C_REBASE
    if veh.slowed:
        return C_ATRAPADO
    return C_LIBRE


class Animacion:
    """Simulación + dibujo. Se puede usar sin ventana (tests) con SDL_VIDEODRIVER=dummy."""

    def __init__(self, cfg: SimConfig, probe_v0_kmh: float = 130.0, seed: int = 1,
                 size: tuple[int, int] = (1600, 900), fullscreen: bool = False, fps: int = 30,
                 velocidad: int = 5, ventana_km: float = 0.8):
        import pygame

        self.pg = pygame
        self.cfg, self.probe_v0, self.seed = cfg, probe_v0_kmh, seed
        self.fps = fps
        self.i_vel = VELOCIDADES.index(velocidad) if velocidad in VELOCIDADES else 2
        self.ventana = ventana_km * 1000.0
        pygame.init()
        flags = pygame.FULLSCREEN if fullscreen else pygame.RESIZABLE
        self.screen = pygame.display.set_mode((0, 0) if fullscreen else size, flags)
        pygame.display.set_caption("Simulación de tráfico: rebases en carretera de dos carriles")
        self.clock = pygame.time.Clock()
        self.f_titulo = _fuente(pygame, 30, negrita=True)
        self.f = _fuente(pygame, 22)
        self.f_peq = _fuente(pygame, 15)
        self.flechas = pygame.font.match_font(_FUENTES) is not None
        self.reiniciar()

    # ------------------------------------------------------------------
    def reiniciar(self) -> None:
        self.road = build_road(self.cfg, self.seed)
        self.road.recorder = _Contador()
        self.pendientes = list(probe_times(self.cfg))
        self.sondas = []
        self.centro = self.cfg.length / 2
        self.seguir = True
        self.i_sonda = 0
        self.pausa = False
        self._acum = 0.0

    @property
    def velocidad(self) -> int:
        return VELOCIDADES[self.i_vel]

    def avanzar(self, dt_real: float) -> None:
        """Avanza la simulación lo que corresponda a `dt_real` segundos reales."""
        if self.pausa:
            return
        self._acum += dt_real * self.velocidad
        road = self.road
        while self._acum >= road.dt:
            while self.pendientes and road.t >= self.pendientes[0]:
                self.pendientes.pop(0)
                self.sondas.append(road.inject(kmh_a_ms(self.probe_v0), direction=1, probe=True))
            road.step()
            self._acum -= road.dt

    def sonda_activa(self):
        en_via = [s for s in self.sondas if s.t_exit is None and s in self.road.vehicles]
        if not en_via:
            return None
        return en_via[self.i_sonda % len(en_via)]

    # ------------------------------------------------------------------
    def manejar(self, ev) -> bool:
        """Procesa un evento; devuelve False si hay que salir."""
        pg = self.pg
        if ev.type == pg.QUIT:
            return False
        if ev.type == pg.KEYDOWN:
            k = ev.key
            if k in (pg.K_ESCAPE, pg.K_q):
                return False
            if k == pg.K_SPACE:
                self.pausa = not self.pausa
            elif k in (pg.K_PLUS, pg.K_EQUALS, pg.K_KP_PLUS):
                self.i_vel = min(len(VELOCIDADES) - 1, self.i_vel + 1)
            elif k in (pg.K_MINUS, pg.K_KP_MINUS):
                self.i_vel = max(0, self.i_vel - 1)
            elif k == pg.K_z:
                self.zoom(1 / 1.4)
            elif k == pg.K_x:
                self.zoom(1.4)
            elif k == pg.K_LEFT:
                self.mover(-0.25 * self.ventana)
            elif k == pg.K_RIGHT:
                self.mover(0.25 * self.ventana)
            elif k == pg.K_s:
                self.seguir = not self.seguir
            elif k == pg.K_TAB:
                self.i_sonda += 1
                self.seguir = True
            elif k == pg.K_r:
                self.reiniciar()
            elif k == pg.K_F11:
                pg.display.toggle_fullscreen()
        elif ev.type == pg.MOUSEWHEEL:
            self.zoom(1 / 1.2 if ev.y > 0 else 1.2)
        elif ev.type == pg.MOUSEBUTTONDOWN and ev.button == 1:
            x0, y0, ancho, alto = self._rect_mapa()
            if y0 - 10 <= ev.pos[1] <= y0 + alto + 10 and x0 <= ev.pos[0] <= x0 + ancho:
                self.centro = (ev.pos[0] - x0) / ancho * self.cfg.length
                self.seguir = False
        return True

    def zoom(self, f: float) -> None:
        self.ventana = min(self.cfg.length, max(150.0, self.ventana * f))

    def mover(self, d: float) -> None:
        self.seguir = False
        self.centro = min(self.cfg.length, max(0.0, self.centro + d))

    # ------------------------------------------------------------------
    def _rect_mapa(self):
        w, h = self.screen.get_size()
        return 40, 150, w - 80, 26

    def dibujar(self) -> None:
        pg, scr, road = self.pg, self.screen, self.road
        w, h = scr.get_size()
        scr.fill(FONDO)
        sonda = self.sonda_activa()
        if self.seguir and sonda is not None:
            self.centro = road.position(sonda)
        geo = getattr(road, "geometry", None)

        # --- título y panel ---
        scr.blit(self.f_titulo.render("¿Vale la pena ir más rápido? Rebases en carretera de dos carriles",
                                      True, TEXTO), (40, 24))
        estado = "PAUSA" if self.pausa else f"×{self.velocidad}"
        cont = road.recorder
        linea = (f"Tiempo {_hms(road.t)}   Velocidad {estado}   En la carretera {len(road.vehicles)}   "
                 f"Rebases {cont.fin}   Abortados {cont.aborto}   Colisiones {road.collisions}")
        scr.blit(self.f.render(linea, True, TEXTO2), (40, 72))
        scr.blit(self.f_peq.render(
            f"{self.cfg.length / 1000:g} km   modo {self.cfg.mode}   "
            + (f"{self.cfg.n_vehicles} vehículos por sentido" if self.cfg.mode != "flujo"
               else f"{self.cfg.flow_per_hour:g} veh/h por sentido")
            + f"   velocidad deseada media {self.cfg.v0_mean_kmh:g} km/h"
            + (f"   trazado: {len(geo.curves)} curvas" if geo is not None and geo.curves else "   trazado: recta")
            + (f"   relieve: {self.cfg.relieve}" if geo is not None and geo.grades else ""),
            True, TEXTO2), (40, 102))

        # --- mapa de la carretera completa ---
        x0, y0, ancho, alto = self._rect_mapa()
        L = self.cfg.length
        pg.draw.rect(scr, ASFALTO, (x0, y0, ancho, alto), border_radius=4)
        if geo is not None:
            for a, b in geo.curve_spans():
                pg.draw.rect(scr, CURVA, (x0 + a / L * ancho, y0, max(1, (b - a) / L * ancho), alto))
        for d, tramos in road.passing.items():  # carriles de rebase en el mapa
            for a_, b_ in tramos:
                ra, rb = (a_, b_) if d == 1 else (L - b_, L - a_)
                pg.draw.rect(scr, LINEA, (x0 + ra / L * ancho, y0 + alto * 0.45, max(1, (rb - ra) / L * ancho), 2))
        for v in road.vehicles:
            px = x0 + road.position(v) / L * ancho
            py = y0 + (alto * 0.3 if v.lane == 1 else alto * 0.5 if v.lane >= 2 else alto * 0.7)
            pg.draw.circle(scr, color_de(v), (px, py), 4 if v.probe else 2)
        a = max(0.0, self.centro - self.ventana / 2)
        b = min(L, self.centro + self.ventana / 2)
        pg.draw.rect(scr, TEXTO, (x0 + a / L * ancho, y0 - 5, max(2, (b - a) / L * ancho), alto + 10), 2,
                     border_radius=3)
        for km in range(0, int(L / 1000) + 1, max(1, int(L / 1000) // 10)):
            scr.blit(self.f_peq.render(f"{km} km", True, TEXTO2), (x0 + km * 1000 / L * ancho - 12, y0 + alto + 8))

        # --- perfil de alturas (si hay pendientes) ---
        top = 250
        if geo is not None and geo.grades:
            self._perfil(geo, x0, y0 + alto + 58, ancho, 36, a, b)
            top = 330
        tres = road.has_passing  # con carriles de rebase: tres franjas (contrario, extra, propio)
        alto_via = (120 if h >= 800 else 96) * (1.5 if tres else 1.0)
        carril = alto_via / (3 if tres else 2)
        izq = self.centro - self.ventana / 2
        esc = (w - 80) / self.ventana  # px por metro

        def X(s):
            return 40 + (s - izq) * esc

        pg.draw.rect(scr, ASFALTO, (40, top, w - 80, alto_via))
        scr.set_clip(pg.Rect(40, top - 30, w - 80, alto_via + 60))
        if geo is not None:
            for a, b, r in geo.curves:
                if b > izq and a < izq + self.ventana:
                    xa, xb = max(40, X(a)), min(w - 40, X(b))
                    pg.draw.rect(scr, CURVA, (xa, top, xb - xa, alto_via))
                    txt = f"curva R = {r:.0f} m · máx {ms_a_kmh(geo.curve_speed(r)):.0f} km/h"
                    scr.blit(self.f_peq.render(txt, True, TEXTO2), (xa + 6, top + alto_via + 6))
            for a_, b_, g in geo.grades:  # rótulos de pendiente (vistos desde el sentido →)
                if b_ > izq and a_ < izq + self.ventana:
                    xa = max(40, X(a_))
                    txt = f"{'sube' if g > 0 else 'baja'} {abs(100 * g):.1f} %"
                    scr.blit(self.f_peq.render(txt, True, TEXTO2), (xa + 220, top - 22))
            for a_, b_, lim in geo.limits:  # señales de límite de velocidad
                if izq <= a_ < izq + self.ventana:
                    self._senal(X(a_) + 16, top - 16, lim)
        # línea central: discontinua, o continua donde no se puede rebasar
        paso = 12.0 if self.ventana < 3000 else 60.0
        s = math.floor(izq / paso) * paso

        def doble(y):
            pg.draw.line(scr, AMARILLO, (X(s), y - 3), (X(s + paso), y - 3), 2)
            pg.draw.line(scr, AMARILLO, (X(s), y + 3), (X(s + paso), y + 3), 2)

        def discontinua(y):
            if int(round(s / paso)) % 2 == 0:
                pg.draw.line(scr, LINEA, (X(s), y), (X(s + paso * 0.6), y), 2)

        while s < izq + self.ventana:
            zona = 0
            if tres:
                zona = 1 if road.passing_end(1, s) is not None else (-1 if road.passing_end(-1, L - s) is not None
                                                                      else 0)
            if zona == 1:  # carril extra del sentido →: doble raya arriba, discontinua entre los dos →
                doble(top + carril)
                discontinua(top + 2 * carril)
            elif zona == -1:
                discontinua(top + carril)
                doble(top + 2 * carril)
            else:
                ymid = top + (1.5 * carril if tres else carril)
                if geo is not None and geo.marked_no_pass(s):
                    doble(ymid)
                else:
                    discontinua(ymid)
            s += paso
        pg.draw.line(scr, BORDE, (40, top), (w - 40, top), 2)
        pg.draw.line(scr, BORDE, (40, top + alto_via), (w - 40, top + alto_via), 2)
        izq_txt, der_txt = ("←", "→") if self.flechas else ("<-", "->")
        scr.blit(self.f_peq.render(f"{izq_txt} sentido contrario", True, TEXTO2), (40, top - 22))
        scr.blit(self.f_peq.render(f"sentido {der_txt}", True, TEXTO2), (w - 40 - 80, top + alto_via + 6))

        scr.set_clip(pg.Rect(40, top, w - 80, alto_via))
        alto_coche = carril * 0.36
        largo_min = alto_coche * 1.8  # los coches se dibujan más largos de lo real para que se vean
        for v in road.vehicles:
            frente = road.position(v)
            atras = frente - v.length * v.direction
            xa, xb = sorted((X(frente), X(atras)))
            if xb < 40 or xa > w - 40:
                continue
            es_camion = v.kind == "camion"
            largo = max(xb - xa, largo_min * (2.4 if es_camion else 1.0))
            if v.direction == -1:
                xa = xb - largo  # el frente queda a la izquierda
            if tres:
                yc = lambda ln: top + (carril * 0.5 if ln == 1 else carril * 1.5 if ln >= 2 else carril * 2.5)  # noqa: E731
            else:
                yc = lambda ln: top + (carril * 0.5 if ln == 1 else carril * 1.5)  # noqa: E731
            yv = yc(v.lane) if v.lc >= 1.0 else yc(v.lane_prev) + (yc(v.lane) - yc(v.lane_prev)) * v.lc
            y = yv - alto_coche / 2
            rect = pg.Rect(xa, y, largo, alto_coche)
            pg.draw.rect(scr, color_de(v), rect, border_radius=3)
            if es_camion:  # cabina: franja oscura en el frente
                cab = largo * 0.22
                cx = xa + largo - cab if v.direction == 1 else xa
                pg.draw.rect(scr, FONDO, (cx + (2 if v.direction == 1 else 0), y, 2, alto_coche))
            if v.probe:
                pg.draw.rect(scr, TEXTO, rect.inflate(6, 6), 2, border_radius=5)
                ety = y + alto_coche + 5 if v.lane == 0 else y - 22  # hacia el borde, no sobre la línea
                scr.blit(self.f_peq.render(f"SONDA {ms_a_kmh(v.v0):.0f} km/h", True, TEXTO), (xa, ety))
            if largo >= 34:
                t = self.f_peq.render(f"{ms_a_kmh(v.v):.0f}", True, FONDO if not v.probe else TEXTO)
                scr.blit(t, (xa + (largo - t.get_width()) / 2, y + (alto_coche - t.get_height()) / 2))
        scr.set_clip(None)
        # regla de distancia
        yreg = top + alto_via + 30
        paso_m = _paso_regla(self.ventana)
        m = math.ceil(izq / paso_m) * paso_m
        while m <= izq + self.ventana:
            pg.draw.line(scr, BORDE, (X(m), yreg), (X(m), yreg + 6), 1)
            etiqueta = f"{m / 1000:.2f}".rstrip("0").rstrip(".")
            scr.blit(self.f_peq.render(f"{etiqueta} km", True, TEXTO2), (X(m) - 18, yreg + 8))
            m += paso_m

        # --- panel de la sonda y leyenda ---
        ypan = yreg + 44
        self._panel_sonda(sonda, 40, ypan)
        self._leyenda(w - 440, ypan)
        self._tabla_sondas(40, ypan + 140, h - 60)
        ayuda = ("Espacio pausa   +/- velocidad   rueda/Z/X zoom   flechas mover   S seguir sonda   "
                 "Tab otra sonda   R reiniciar   F11 pantalla completa   Esc salir")
        scr.blit(self.f_peq.render(ayuda, True, TEXTO2), (40, h - 32))

    def _panel_sonda(self, sonda, x, y) -> None:
        scr, road = self.screen, self.road
        if sonda is None:
            hechas = [s for s in self.sondas if s.t_exit is not None]
            if self.pendientes:
                txt = f"La próxima sonda ({self.probe_v0:g} km/h) entra en {_hms(self.pendientes[0] - road.t)}"
            elif hechas:
                s = hechas[-1]
                libre = self._libre(s)
                txt = (f"Última sonda: tardó {_hms(s.travel_time)}; en vía libre habría tardado "
                       f"{_hms(libre)}  (perdió {s.travel_time - libre:.0f} s, rebasó {s.overtakes})")
            else:
                txt = "Sin sondas en esta corrida"
            scr.blit(self.f.render(txt, True, TEXTO), (x, y))
            return
        recorrido = sonda.x
        t = road.t - sonda.t_entry
        libre = self._libre(sonda) * recorrido / self.cfg.length  # aproximado a mitad de camino
        filas = [
            f"Sonda: quiere ir a {ms_a_kmh(sonda.v0):.0f} km/h, va a {ms_a_kmh(sonda.v):.0f} km/h",
            f"Recorrido {recorrido / 1000:.1f} de {self.cfg.length / 1000:g} km en {_hms(t)}",
            f"Tiempo perdido por el tráfico: {t - libre:.0f} s",
            f"Vehículos rebasados: {sonda.overtakes}   Veces que tuvo que frenar por otro: {sonda.catchups}",
        ]
        for i, f in enumerate(filas):
            scr.blit((self.f if i else self.f).render(f, True, TEXTO if i == 0 else TEXTO2), (x, y + i * 28))

    def _tabla_sondas(self, x, y, y_max) -> None:
        """Sondas que ya terminaron: cuánto tardaron y cuánto perdieron por el tráfico."""
        hechas = [s for s in self.sondas if s.t_exit is not None]
        if not hechas:
            return
        scr = self.screen
        scr.blit(self.f.render(f"Sondas que ya llegaron (quieren ir a {self.probe_v0:g} km/h)", True, TEXTO), (x, y))
        cols = ["", "Tardó", "En vía libre", "Perdió", "Rebasó", "Frenó por otro"]
        xs = [x, x + 90, x + 220, x + 380, x + 500, x + 620]
        y += 34
        for c, cx in zip(cols, xs):
            scr.blit(self.f_peq.render(c, True, TEXTO2), (cx, y))
        filas_max = max(0, int((y_max - y - 26) // 24))
        perdidas = []
        for i, s in enumerate(hechas):
            libre = self._libre(s)
            perdidas.append(s.travel_time - libre)
            if i >= len(hechas) - filas_max:
                y += 24
                vals = [f"#{i + 1}", _hms(s.travel_time), _hms(libre), f"{s.travel_time - libre:.0f} s",
                        str(s.overtakes), str(s.catchups)]
                for v, cx in zip(vals, xs):
                    scr.blit(self.f_peq.render(v, True, TEXTO), (cx, y))
        if len(perdidas) > 1 and filas_max:
            y += 28
            scr.blit(self.f_peq.render(f"Promedio perdido: {sum(perdidas) / len(perdidas):.0f} s", True, TEXTO),
                     (xs[3] - 130, y))

    def _libre(self, veh) -> float:
        """Tiempo en vía libre del recorrido completo (con las curvas del trazado)."""
        return free_time(self.cfg, veh.v0, veh.direction, seed=self.seed)

    def _leyenda(self, x, y) -> None:
        for i, (nombre, c) in enumerate(ESTADOS):
            r = self.pg.Rect(x, y + i * 28 + 4, 30, 14)
            self.pg.draw.rect(self.screen, c, r, border_radius=3)
            self.screen.blit(self.f.render(nombre, True, TEXTO2), (x + 42, y + i * 28))
        yy = y + len(ESTADOS) * 28
        if self.cfg.trucks.share > 0:
            r = self.pg.Rect(x - 14, yy + 4, 44, 14)
            self.pg.draw.rect(self.screen, C_LIBRE, r, border_radius=3)
            self.pg.draw.rect(self.screen, FONDO, (x + 20, yy + 4, 2, 14))
            self.screen.blit(self.f.render("Camión (largo, con cabina)", True, TEXTO2), (x + 42, yy))
            yy += 28
        partes = self._texto_modelo()
        if partes:
            yy += 12
            self.screen.blit(self.f_peq.render("Modelo:", True, TEXTO), (x - 14, yy))
            for p in partes:
                yy += 22
                self.screen.blit(self.f_peq.render("· " + p, True, TEXTO2), (x - 14, yy))

    def _texto_modelo(self) -> list[str]:
        """Qué comportamiento extra está activado (fase 3)."""
        c, o, d = self.cfg, self.cfg.overtaking, self.cfg.drivers
        partes = []
        if c.trucks.share > 0:
            partes.append(f"{100 * c.trucks.share:g} % camiones")
        if o is not None and o.t_lane_change > 0:
            partes.append(f"cambio de carril {o.t_lane_change:g} s")
        if o is not None and o.convoy:
            partes.append("rebase en cadena")
        if o is not None and o.peek:
            partes.append("se asoma para ver")
        elif o is not None and o.blocked_view:
            partes.append("vista tapada")
        if c.passing_lanes:
            partes.append(f"{len(c.passing_lanes)} tramos con carril de rebase (2+1)")
        if o is not None and o.gap_logit:
            partes.append("acepta huecos al azar (logit)" + (" con piso" if o.gap_floor else ""))
        if d.share_cautious or d.share_aggressive:
            partes.append(f"{100 * d.share_cautious:g} % prudentes, {100 * d.share_aggressive:g} % agresivos")
        if d.impatience_after > 0:
            partes.append(f"impaciencia tras {d.impatience_after:g} s atrapado")
        if c.reaction_time > 0:
            partes.append(f"reacción {c.reaction_time:g} s")
        if c.speed_limit_kmh > 0 or c.speed_limits:
            partes.append(f"límites (respeta {100 * d.limit_compliance:g} %)")
        return partes

    def _perfil(self, geo, x0, y0, ancho, alto, a_vis, b_vis) -> None:
        """Perfil de alturas de toda la carretera, con la ventana visible marcada."""
        pg, scr, L = self.pg, self.screen, self.cfg.length
        n = 300
        hs = [geo.elevation(L * i / n) for i in range(n + 1)]
        h_min, h_max = min(hs), max(hs)
        rango = max(h_max - h_min, 20.0)
        pts = [(x0 + ancho * i / n, y0 + alto - (hh - h_min) / rango * alto) for i, hh in enumerate(hs)]
        pg.draw.rect(scr, (34, 34, 33), (x0 + a_vis / L * ancho, y0 - 2, max(2, (b_vis - a_vis) / L * ancho),
                                          alto + 4))
        pg.draw.lines(scr, TEXTO2, False, pts, 2)
        scr.blit(self.f_peq.render(f"perfil de alturas ({rango:.0f} m de desnivel)", True, TEXTO2),
                 (x0, y0 - 20))

    def _senal(self, x, y, kmh) -> None:
        """Señal circular de límite de velocidad."""
        pg = self.pg
        pg.draw.circle(self.screen, (240, 239, 236), (x, y), 14)
        pg.draw.circle(self.screen, (208, 59, 59), (x, y), 14, 3)
        t = self.f_peq.render(f"{kmh:.0f}", True, FONDO)
        self.screen.blit(t, (x - t.get_width() / 2, y - t.get_height() / 2))

    # ------------------------------------------------------------------
    def run(self, max_frames: int | None = None, screenshot: str | None = None) -> None:
        pg = self.pg
        frames = 0
        seguir = True
        while seguir:
            for ev in pg.event.get():
                seguir = self.manejar(ev) and seguir
            dt = self.clock.tick(self.fps) / 1000.0 if max_frames is None else 1.0 / self.fps
            self.avanzar(min(dt, 0.1))
            self.dibujar()
            pg.display.flip()
            frames += 1
            if max_frames is not None and frames >= max_frames:
                break
        if screenshot:
            pg.image.save(self.screen, screenshot)
        pg.quit()


class _Contador:
    """Registro mínimo para la animación: solo cuenta rebases (sin fotos)."""

    def __init__(self):
        self.fin = 0
        self.aborto = 0

    def event(self, road, kind, veh, n=0, cadena=False):
        if kind == REBASE_FIN:
            self.fin += 1
        elif kind == REBASE_ABORTO:
            self.aborto += 1

    def on_step(self, road):
        pass


_FUENTES = "dejavusans,arial,liberationsans,notosans,helvetica"


def _fuente(pygame, size: int, negrita: bool = False):
    """Fuente del sistema con flechas y acentos; si no hay, la de pygame."""
    ruta = pygame.font.match_font(_FUENTES, bold=negrita)
    if ruta is None:
        return pygame.font.Font(None, int(size * 1.3))
    return pygame.font.Font(ruta, size)


def _hms(seg: float) -> str:
    seg = max(0, int(seg))
    h, r = divmod(seg, 3600)
    m, s = divmod(r, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _paso_regla(ventana: float) -> float:
    for p in (50, 100, 250, 500, 1000, 2000, 5000):
        if ventana / p <= 12:
            return p
    return 10000


def animar(cfg: SimConfig, probe_v0_kmh: float = 130.0, seed: int = 1, **kw) -> None:
    """Abre la ventana de animación."""
    Animacion(cfg, probe_v0_kmh, seed, **kw).run()


def captura(cfg: SimConfig, path: str, frames: int = 60, probe_v0_kmh: float = 130.0, seed: int = 1,
            sim_segundos: float = 0.0, **kw) -> "Animacion":
    """Dibuja sin ventana (SDL dummy) y guarda una captura; para tests y para el README."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    a = Animacion(cfg, probe_v0_kmh, seed, **kw)
    if sim_segundos:
        a._acum = sim_segundos
        a.avanzar(0.0)
    a.run(max_frames=frames, screenshot=path)
    return a
