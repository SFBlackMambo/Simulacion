# Progreso: Simulación de tráfico

## Sesión 1: Explore y Plan - 2026-11-21
- EXPLORE: proyecto greenfield, Python 3.13, SSH a GitHub pendiente de configurar.
- PLAN: aprobado. Ver EPCC_PLAN.md (~26 h, 9 features en epcc-features.json).
- Pendiente del usuario: generar clave SSH, añadirla a GitHub y crear el repo vacío.
- Siguiente: `/epcc-code INFRA-001`

---

## Sesión 2: INFRA-001 - 2026-11-21
- Creados: pyproject.toml, .gitignore, README.md, src/trafico/, tests/test_smoke.py, .venv local.
- Verificado: clon limpio + venv + `pip install -e ".[dev]"` + pytest OK.
- Commit: 6c9665b
- Sin remote todavía (falta SSH y repo en GitHub), así que no se hizo push.
- Siguiente: `/epcc-code F001` (Vehículo e IDM)

---

## Sesión 3: F001 Vehículo e IDM - 2026-11-21
- Creados: src/trafico/vehicle.py (Vehicle, conversiones km/h<->m/s), src/trafico/idm.py (IDMParams, idm_acceleration, step), tests/test_idm.py.
- Decisiones: unidades SI; integración balística con dt=0.1 s; `x` es la posición del frente; el atributo de sentido se añade en F004.
- Parámetros IDM por defecto: a=1.0 m/s², b=1.5, T=1.5 s, s0=2 m, delta=4.
- Verificado: 9 tests pasan, cobertura 100 %.
- Siguiente: `/epcc-code F002` (Carretera de un carril)

---

## F002 - 2026-11-22
- road.py: Road (un carril por sentido, entrada con hueco, salida, registro de tiempos, conteo de colisiones). vehicle.py ampliado (dirección, carril, métricas). idm.advance extraído.
- Verificado: 15 tests pasan. Siguiente: F003.

---

## F003 - 2026-11-22
- arrivals.py: PoissonArrivals (tasa, v0 Normal truncada, semilla propia). Road.add_source.
- Verificado: 21 tests pasan (tasa, rango, semilla, integración sin colisiones). Siguiente: F004.

---

## F004 - 2026-11-22
- road.py: carril por sentido, choque frontal contrario con frenado de emergencia (t_emergency=4 s, b=5 m/s², d_min=30 m), bloqueo de entrada, conteo de colisiones frontales.
- Verificado: 27 tests pasan. Siguiente: F005 (rebase).

---

## F005 - 2026-11-22
- overtaking.py: criterio de hueco seguro (plan con perfil de aceleración IDM, cotas pesimistas para los demás, margen de 6 s con el contrario, vehículo virtual en la entrada), máquina SIGUIENDO/REBASANDO/REGRESANDO, aborto por amenaza frontal, cadena de hasta 4 vehículos.
- Hallazgo: el primer diseño (margen fijo de velocidad) provocó bloqueos frente a frente que paralizaban la carretera. Se corrigió con cotas físicas (a_max), margen en tiempo y detección de contrario detenido.
- Verificado: 38 tests, cobertura 99 %; en 4 semillas de 1 h: 0 colisiones, 0 frenados de emergencia, 0 abortos, sin cola creciente.
- Siguiente: F006 (sondas y réplicas).

---

## F006 - 2026-11-22
- simulation.py: SimConfig, run_simulation (números aleatorios comunes, sondas con instantes de entrada fijos), RunResult. experiments.py: run_replicas (serie o procesos), con_flujo.
- Verificado: sin tráfico la sonda tarda L/v0; reproducible; misma semilla => mismo fondo y mismas entradas; paralelo == serie.
- Siguiente: F007 (estadística y gráficas).

---

## F007 - 2026-11-22
- stats.py (media, IC95 con t de Student, diferencia pareada, ganancia ideal), plots.py (3 gráficas validadas con la paleta: azul/naranja, etiquetas directas y leyenda), scripts/run_experiment.py (CSV + PNG).
- Verificado: 6+1 tests nuevos; sin tráfico la ganancia pareada es la ideal; con tráfico es menor. Prueba corta revisada visualmente.
- Siguiente: F008 (experimento completo, sensibilidad, README, push).

---

## F008 - 2026-11-22
- Experimento principal (20 km, 4 flujos, 8 semillas) y sensibilidad (10 variantes, 6 semillas): 0 colisiones.
- Resultados en README.md y docs/. Ganancia 120->130: 32.9 s (100 veh/h), 18.0 (200), 6.9 (300), 5.1 (450); ideal 46.2 s. Sin rebases: 0.1 s.
- 53 tests pasan. Pendiente (usuario): push a GitHub desde su consola.

---

## Fase 2 planeada - 2026-11-22
- Plan fase 2 aprobado (F009-F017): más datos, cantidad fija, corrida única, campañas, animación, menú, curvas y visibilidad. Ver EPCC_PLAN.md.
- Entorno: Python 3.14; pygame no tiene wheel para 3.14, se usa pygame-ce (mismo `import pygame`).

---

## F009 - 2026-11-22
- recorder.py: viajes de todos los vehículos (RunResult.trips), eventos de rebase (inicio/fin/aborto) y fotos periódicas; Recorder opcional.
- Vehicle: veces_rebasado, alcances (episodios por debajo de v0, con histéresis), full_trip. Road.position() en coordenadas de la carretera.
- Verificado: 58 tests; el registro no cambia los resultados; eventos cuadran con contadores.

---

## F010 - 2026-11-22
- SimConfig.mode: "flujo" (Poisson, como antes), "lleno" (N por sentido repartidos al inicio y reposición al salir) y "total" (exactamente N por sentido, termina cuando salen todos). SimConfig.duration para corridas sin sondas.
- simulation.build_road() separa la construcción de la carretera (la usará la animación). Road.fill / keep_count; PoissonArrivals.max_count / sample_v0.
- Verificado: 65 tests; resultados del modo flujo sin cambios (mismas semillas).

---

## F011 - 2026-11-22
- CLI `trafico corrida` (también `python -m trafico corrida`): una simulación con viajes.csv, eventos.csv, fotos.csv, config.json, resumen.json y 5 gráficas (espacio-tiempo, histograma de retraso, retraso vs v0, pelotones, rebases por km).
- config.py: guardar/leer SimConfig en JSON y cambiar parámetros por nombre (`idm.T`, `overtaking.t_guard`, alias en español).
- Verificado: 69 tests; gráficas revisadas visualmente (modos flujo y lleno). 20 km a 200 veh/h tarda ~3 s.

---

## F012 - 2026-11-22
- campaign.py: `trafico campana --barrer nombre=v1,v2 ...` (producto cartesiano × velocidades × semillas), en paralelo, guarda campana.json, corridas.csv, sondas.csv y opcionalmente viajes.csv. Reanudable (limpia filas de corridas a medias) y ampliable con más semillas o velocidades.
- analysis.py: `trafico graficar carpeta [--x] [--serie] [--comparar]`: resúmenes con IC95, ganancia emparejada (y % de la ideal, calculada con los tiempos libres medidos) y gráficas por sondas y tráfico de fondo. Parámetros extra separan archivos.
- Verificado: 75 tests; campaña de prueba (3 flujos × 2 longitudes) reproduce las ganancias del README (32/17/7 s a 20 km).

---

## F013 - 2026-11-22
- animation.py + `trafico animar`: ventana pygame-ce (modo oscuro) con mapa de la carretera completa, tramo ampliado con los dos carriles, panel de la sonda en vivo y tabla de sondas que ya llegaron. Colores por estado: libre (azul), rebasando (aqua), sonda (naranja, con contorno y etiqueta), atrapado (gris neutro). Los 3 tonos pasan el validador en todas las parejas; 4 tonos fallaban (amarillo/naranja).
- Controles: pausa, ×1..×100, zoom, mover, seguir sonda, clic en el mapa, reiniciar, pantalla completa. `--captura` guarda un PNG sin abrir ventana.
- Verificado: 78 tests (SDL dummy); ×100 usa <10 % de un núcleo; dibujo ~1 ms por cuadro.

---

## F014 - 2026-11-22
- menu.py: `trafico` (sin argumentos) o `trafico menu` abre un menú: corrida única, animación, campaña (elige parámetros a barrer y valores) o graficar. Enter acepta los valores por defecto; valida entradas; al final muestra el comando equivalente para repetirlo y lo ejecuta.
- Verificado: 83 tests (menú con entradas simuladas, incluida una corrida real).

---

## F015 - 2026-11-22
- geometry.py: Geometry con curvas (inicio, fin, radio). Velocidad permitida √(a_lat·R) (a_lat = 2 m/s²) con envolvente de frenado anticipado (b = 1 m/s²) en rejilla de 10 m por sentido; seguimiento con ganancia 4/s. Tiempo libre con curvas integrando las mismas ecuaciones (exacto para sondas, interpolado cada 1 km/h para el fondo).
- SimConfig: trazado, geometry_seed, curves, curve_a_lat, sight_clearance. Vehicle.v_des. Los "alcances" solo cuentan si hay un líder cerca (frenar por curva no cuenta).
- Verificado: 91 tests; con carretera recta los resultados son idénticos bit a bit a los anteriores; en curva nadie supera el límite.
- Hallazgo: con curvas aparecen frenados de emergencia (10-23 por corrida, 0 en recta) porque la predicción del rebase supone aceleración libre hasta v0. Se resuelve en F016.

---

## F016 - 2026-11-22
- Visibilidad: dentro de una curva se ve √(8·R·m) (despeje lateral m = 10 m); antes de ella, la recta hasta la curva más ese trozo. Para rebasar se supone un vehículo de frente invisible a 108 km/h (v_unseen) justo donde acaba la visibilidad, con 2 s de margen: en curva solo se rebasa si la maniobra cabe en lo visible. Primer intento con los márgenes del extremo de la carretera (144 km/h, 6 s) exigía ~1.6 km de visibilidad y anulaba todos los rebases; se separaron los parámetros.
- La predicción del rebase respeta la velocidad de curva del que rebasa. Con esto los frenados de emergencia con curvas pasan de 10-23 por corrida a 0.
- Animación: curvas sombreadas con radio y velocidad máxima, línea central amarilla continua donde no hay visibilidad de rebase. `--param curves=inicio:fin:radio;...`.
- Verificado: 97 tests; recta idéntica bit a bit; 0 colisiones y 0 emergencias con curvas y tráfico.

---

## F017 - 2026-11-22
- geometry.PRESETS + build_trazado: recta, pocas (0.3 curvas/km, R 300-900), muchas (1.2/km, R 150-450), montana (2.5/km, R 60-200); reproducibles por semilla. `--trazado` y `--semilla-trazado` (0 = trazado distinto en cada réplica). describe(): curvas, % en curva, % sin visibilidad para rebasar.
- Espacio-tiempo coloreado por velocidad perdida por el tráfico (respecto a la permitida por la curva); curvas sombreadas en las gráficas. Menú pregunta el tipo de carretera y permite barrerlo.
- Campañas: trazado × flujo (288 corridas) y longitud × flujo (192). Recta reproduce exactamente la fase 1. Ganancia 120→130 a 200 veh/h: recta 18.0 s, pocas 12.3, muchas 1.5, montaña 0.2. Con distancia, a 200 veh/h la ganancia pasa de 23 % de la ideal (5 km) a 51 % (40 km). 0 colisiones.
- README reescrito (uso, menú, modos, trazados, animación, campañas, resultados fase 1 y 2).
- Verificado: 109 tests.

---

## Fase 3 planeada - 2026-11-22
- Plan fase 3 aprobado (F018-F026): camiones, cambio de carril gradual, rebase en cadena, pendientes, señales, conductores, reacción. Todo apagado por defecto; preset --realista.

---

## F018 - 2026-11-22
- fleet.py: TruckParams (16.5 m, a = 0.5 m/s², velocidad normal asimétrica con moda ~105 km/h y 2 % de anomalías). SimConfig.trucks; `--param camiones=0.2` (alias de trucks.share). Cada vehículo tiene `kind` e `idm` propios; los viajes y fotos guardan la clase.
- Sin camiones no se consume ningún número aleatorio extra: huella de regresión idéntica.
- Hallazgo: con camiones a ~104 km/h y autos a 100 de media, casi nadie los rebasa en plano; su peso vendrá de las pendientes (F021).
- Verificado: 116 tests; 0 colisiones y 0 emergencias con 10-50 % de camiones.

---

## F019 - 2026-11-22
- Cambio de carril gradual: `overtaking.t_lane_change` (s, 0 = instantáneo). Durante el cambio el vehículo ocupa los dos carriles (aparece en ambos grupos; se aplica la aceleración más restrictiva); el cálculo de seguridad suma el regreso. Vehicle.change_lane / occupies / lc; la animación interpola la posición lateral.
- Hallazgo: con 3 s, un rebase que esperaba hueco para volver provocaba sustos (frenado de emergencia del contrario). Solución: la amenaza se detecta t_lane_change antes y, si viene alguien de frente, se acepta volver en un hueco de la mitad.
- Verificado: 120 tests; huella idéntica con duración 0; estrés 24 corridas con 3 s y 20 % camiones: 0 colisiones, 0 emergencias.

---

## F020 - 2026-11-22
- Rebase en cadena (`overtaking.convoy`): se puede empezar a rebasar siguiendo a otro que ya va en el carril contrario, si el rebase propio es seguro suponiendo que no se irá más rápido que el de delante. Siguen prohibidos si hay alguien detrás en el carril contrario o uno que está volviendo.
- Visión tapada (`overtaking.blocked_view`): detrás de un camión a menos de 3 s no se ve el carril contrario; detrás de un auto (o del que rebasa delante) a menos de 2 s se ven 500 m. Lo no visible se trata como en las curvas (vehículo supuesto donde acaba la vista).
- Eventos con `en_cadena`; viajes con `rebases_en_cadena`; campañas con rebases en cadena, camiones y retraso de camiones (el análisis tolera campañas viejas).
- Hallazgo (10 km, 3 semillas, cambio de carril 3 s, 15 % camiones): en cadena sin visión tapada hay más rebases (106 vs 95 a 350 veh/h) pero aparecen sustos (4-6 frenados de emergencia, 0 choques); con visión tapada, 0 sustos y menos rebases (78).
- Verificado: 125 tests; huella idéntica con todo apagado.

---

## F021 - 2026-11-22
- slopes.py: subida por potencia específica (camión 7.5 W/kg, auto 60): v_max = P/(g·(i+c_r)) y aceleración limitada; camión 3/6/8 % → 69/39/31 km/h. Bajada con freno de motor para camiones: sin efecto hasta 3 %, luego -6 km/h por punto desde 90 (5/7/9 % → 78/66/54), mínimo 40. Autos sin cambio.
- Geometry.grades (por tramo, + = sube en sentido +1), tablas por sentido, altura. Relieves generados: plano, lomerio (1.5-4 %), montanoso (3-7 %), con altura acotada. `--relieve`, `--camiones`, `--param "pendientes=a:b:pct;..."`. Tiempo libre y predicción del rebase con pendientes.
- Verificado: 137 tests; huella idéntica; estrés montañoso con 20 % camiones, cambio 3 s, cadena y vista tapada: 0 colisiones, 0 emergencias.
