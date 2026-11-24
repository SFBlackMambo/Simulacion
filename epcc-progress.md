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

---

## F022 - 2026-11-22
- Límites de velocidad: general (`--param limite=90`) o por tramo (`limites=a:b:kmh;...`), anticipados 100 m. Zonas de no rebase señalizadas a mano (`zonas_no_rebase=a:b;...`) o automáticas donde falta visibilidad (`no_rebase_sin_visibilidad=1`).
- drivers.py: DriverModel con rasgos por conductor sorteados con un generador propio (no cambia el tráfico): % que respeta límites (los demás se pasan 10-30 %) y % que respeta zonas de no rebase. Las sondas siempre respetan.
- Tiempo libre y predicción del rebase consideran el límite (con el exceso propio). Hallazgo: sin eso, con límite 90 aparecían 5-7 sustos; ahora 0.
- Hallazgo: en curvas, las zonas automáticas por visibilidad no cambian nada: la regla física de visibilidad ya impedía esos rebases. En recta con zonas de 2-5 y 6-9 km, los rebases bajan de 46 a 20 (a 32 si la mitad no respeta).
- Verificado: 146 tests; huella idéntica.

---

## F023 - 2026-11-22
- Tipos de conductor (`prudentes`, `agresivos` = fracciones): multiplican el margen con el contrario (×1.5 / ×0.5), el intervalo IDM T (×1.3 / ×0.7) y la diferencia de velocidad para decidir rebasar (×1.5 / ×0.5). Impaciencia (`impaciencia` = s atrapado): el margen baja linealmente hasta 50 % en 120 s más. Vehicle.t_stuck; viajes con `conductor`.
- Corrección: el modelo de conductores no se activaba solo con impaciencia (active no la incluía).
- Resultado (10 km, 300 veh/h, 3 semillas): rebases por viaje agresivo 0.21-0.22, normal 0.14-0.15, prudente 0.09; 0 colisiones y 0 emergencias. La impaciencia sola casi no cambia (0.15 → 0.16): coherente con la sensibilidad de la fase 1, el margen no es lo que más limita.
- Verificado: 151 tests; huella idéntica.

---

## F024 - 2026-11-22
- Tiempo de reacción (`--param reaccion=1.0`): la aceleración se aplica con retraso; el frenado frontal de emergencia y los "sustos" (choque con el de delante en < 2 s o hueco crítico) son inmediatos. La predicción del rebase suma el tiempo de reacción.
- Hallazgo 1: con retraso puro de 1 s el IDM es inestable: un frenón del líder crece por el pelotón hasta detener al décimo coche. Se usó el Human Driver Model (Treiber 2006): estimación del hueco al momento de actuar + multi-anticipación (3 de delante, pesos 1/j²). Con eso el pelotón es estable hasta 1.2 s y el hueco de equilibrio no cambia (~39 m).
- Hallazgo 2: al cambiar de carril se aplicaban frenazos decididos en el carril anterior (bajaba de 120 a 38 km/h y provocaba sustos). Ahora el cambio de carril descarta las decisiones pendientes. Resultado: 0 emergencias.
- Verificado: 157 tests; huella idéntica; estrés con todo activado: 0 colisiones, 0 emergencias.

---

## F025 - 2026-11-22
- Preset `--realista` (config.PRESET_REALISTA): 10 % camiones, cambio de carril 3 s, cadena + vista tapada, 20 % prudentes / 15 % agresivos, impaciencia 60 s, reacción 1 s, no rebase donde no se ve (90 % respeta), límites respetados por el 80 %. `--param` lo sobreescribe; `--camiones` en la CLI.
- Animación: perfil de alturas con la ventana visible, rótulos "sube/baja x %", señales circulares de límite, camiones largos con cabina, cambio de carril visible, lista del modelo activo en la columna de la leyenda.
- Menú: relieve, % de camiones y modelo realista; se pueden barrer relieve y camiones.
- Verificado: 160 tests; capturas revisadas.

---

## F026 - 2026-11-22
- Campañas realistas (352 corridas, 0 colisiones): camiones × relieve, flujo × trazado, cadena sí/no. scripts/descomponer_realista.py: quita/añade cada pieza del preset.
- Hallazgos que obligaron a corregir el modelo antes de publicar:
  1. Sustos en montaña con camiones: se salía a rebasar a un pelotón que frenaba en seco y, durante el cambio de carril de 3 s, se frenaba con él (42 → 6 km/h). Nuevo (solo realista): no salir si uno o el pelotón frena fuerte; durante la salida el líder del carril propio solo cuenta si está muy cerca; solo salir si cabe la salida sin alcanzar al de delante.
  2. El IDM llegaba a pedir -2000 m/s² al reaparecer el líder. Tope físico de frenado 9 m/s² (solo realista; en el simple nunca se pasaba de 9 y la huella no cambia). Con el tope aparecieron choques al volver de un rebase detrás de un camión lento; el regreso ahora exige cubrir la distancia de frenado por la diferencia de velocidad (solo realista).
  3. Cadena sin visión tapada chocaba: el que se sumaba no revisaba la distancia con el que rebasaba delante. Ahora debe ir a distancia segura. (Con visión tapada la regla nunca se activaba: campaña de cadena idéntica bit a bit.)
- Resultado principal: la visión tapada es lo que más pesa (simple + solo visión tapada: 18 → 1 s de ganancia). En montaña con 10 % camiones el retraso medio pasa de 65 s a ~300 s.
- Sustos residuales sin choque: 0.1 por corrida (0.7 en montaña).
- Verificado: 165 tests; huella idéntica bit a bit con todo apagado.

---

## Calibración de pendientes y velocidad - 2026-11-22
- El usuario notó que en subida los camiones bajaban demasiado rápido. Era un error: la velocidad mínima de subida se usaba como velocidad deseada y el vehículo "frenaba" (105 → 39 km/h en 4 s). Ahora en subida solo limita el motor (pérdida gradual).
- Investigación (NCHRP 505, FHWA-RD-99-171/TWOPAS, SCT Manual de Proyecto Geométrico 2018, Bester y Oncke 2013, GSRS): potencia por camión sorteada (log-normal, mediana 150 lb/hp, 87 % a la rueda) + 15 % de fulles 330-410 lb/hp; arrastre del aire; autos 22 W/kg; bajadas con gravedad (autos +10 %, camiones +5 % SCT); freno de motor solo con >4 % y >2 km (St John, V = 0.9/G) para camiones pesados; montañoso 3-6 % (a veces 7 %) en tramos de 300-800 m. Física de motor también para camiones en llano (un full no sostiene 100 km/h).
- Correcciones de seguridad: la predicción del rebase de un camión usa su física de motor; un camión solo rebasa si lo que puede sostener supera al de delante.
- Velocidad: tablas por vehículo, descarte temprano por tráfico de frente (cota segura) y `--rapido` con PyPy (scripts/instalar_pypy.sh). Mismos resultados bit a bit (huellas simple y realista). 20 km realista en montaña: 56.6 s → 20 s (CPython) → 5 s (PyPy).
- Campañas de la fase 3 recalculadas: 0 colisiones; montaña con 10 % camiones: retraso medio 178 s (antes 298 con el error).

---

## Session: EXPLORE - 2026-11-22
- Objetivo: todo el código (sin argumentos), alcance medio. Reemplaza el EPCC_EXPLORE.md del 2026-11-21 (repo vacío).
- Hallazgos: 27 features verificadas; 168 tests pasan (91 s); la regresión "huella bit a bit" no está automatizada; sin CLAUDE.md, linter ni CI; directorio vacío `./2` en la raíz.
- Archivos revisados: ~20 en src/, tests/, scripts/ y docs de EPCC.
- Siguiente: el usuario define el trabajo nuevo; candidato recomendado: prueba automática de la huella.
- Git: 0accc59, master, limpio.
- Anexo: estado de los datos de viajes y propuestas tomadas de la literatura (agente de búsqueda; las citas no se verificaron en línea). El usuario eligió D1, D2 y D7 (datos de viajes) y B1, B2 y B3 (comportamiento de rebase), con CSV. Siguiente: /epcc-plan.
- README con nuevo enfoque: la mejor velocidad deseada pesando tiempo contra riesgo y costo. Se suman D5 y D6. Las campañas se vuelven a correr con sondas de 90 a 150 km/h, de 10 en 10, y con los viajes guardados.

---

## Plan fase 4 aprobado - 2026-11-22
- 13 features (INFRA-002, F027-F038), ~45 h. Orden: huella → datos de viajes → costo y riesgo → rebase (logit de Farah, asomarse, 2+1) → barrido 90-150, volver a correr las campañas y README.
- Decisiones: CSV; dinero en MXN; el logit de Farah va sin piso de seguridad (puede haber choques, se reportan; `gap_floor` es opcional); riesgo con tres medidas por separado; precios aplicados después de simular.
- Siguiente: `/epcc-code INFRA-002`.

---

## INFRA-002 - 2026-11-23
- tests/test_huella.py + tests/data/huella.json: 5 escenarios cortos (recta, curvas, sin rebases, realista en recta, realista en montaña con 20 % camiones). Hash SHA-256 de los campos de la dinámica de cada viaje (las columnas nuevas no cuentan), tiempos de sonda, colisiones. 7 s.
- Idéntica en CPython 3.14 y PyPy 3.11. Regenerar solo si el cambio es intencional: `python tests/test_huella.py --actualizar`.

---

## F027 - 2026-11-23
- Las campañas guardan viajes.csv por defecto; `--sin-viajes` lo apaga (`--viajes` se sigue aceptando). Al reanudar se puede encender: las corridas nuevas guardan viajes y `corridas.csv` marca `con_viajes`. Al reanudar, un CSV existente conserva sus columnas.
- Menú: "¿Guardar el viaje de cada vehículo?" ahora trae "sí" por defecto.
- docs/datos.md: diccionario de columnas.
- Verificado: 175 tests; huella idéntica.

---

## F028 - 2026-11-23
- Columnas nuevas en viajes.csv (ver docs/datos.md): v_media_kmh, t_headway_2_5 (seguidor HCM 7.ª ed.), t_headway_3 (PTSF HCM 2010), pct_tiempo_siguiendo, t_carril_contrario, ttc_min_lider, ttc_min_contrario, conflictos_lider/contrario (episodios con TTC < 1.5 s, SSAM), factor_limite, potencia_w_kg y lb_hp. corridas.csv suma pct_siguiendo_fondo, t_contrario_fondo y los conflictos.
- Solo se registran (función road._medir); la huella no cambia. Costo: ~5 % (realista de 20 km en montaña: 10.9 → 11.4 s).
- Verificado: 179 tests.

---

## F029 - 2026-11-23
- Trayectorias tipo NGSIM, apagadas por defecto: `--trayectorias S` en `corrida` (trayectorias.csv) y en `campana` (trayectorias/combo<k>_v<v>_s<semilla>.csv, un archivo por corrida); `--solo-sondas` guarda solo las sondas. Se escriben al vuelo (no llenan la memoria).
- Columnas (docs/datos.md): t, id, sentido, x, x_propio, carril, v_kmh, a, largo, clase, sonda, estado, id_lider, hueco_m, headway_s, id_seguidor.
- La sesión anterior se cortó con todo hecho salvo `id_seguidor` (pedido en los criterios); se agregó y se prueba que el seguidor tiene al vehículo como líder.
- Verificado: 181 tests; huella idéntica. Siguiente: `/epcc-code F030`.

---

## F030 - 2026-11-23
- `src/trafico/fuel.py`: VSP de Jiménez-Palacios (autos; camiones con masa rotatoria 1.05, rodadura 0.0065, CdA 6 m² y masa por lb/hp con motor de 430 hp) y línea de Willans (P0 + VSP·m/η). Gasolina 32 MJ/L, diésel 35.8 MJ/L; CO2 de la EPA.
- viajes.csv: `litros`, `l_100km`, `co2_kg`. sondas.csv: `litros`, `co2_kg`, `t_carril_contrario`, `ttc_min_contrario`, `conflictos`, `frenado_emergencia`. corridas.csv: `l_100km_fondo`, `litros_sondas`.
- Revisión: auto en llano 5.7 / 6.8 / 7.5 L/100 km a 100 / 120 / 130 (±15 % de los típicos 5.8 / 7.0 / 7.6); camión de 29 t a 90 km/h: 31 L/100 km. Supuestos documentados en docs/datos.md (sin verificar en línea).
- Solo se registra; costo ~6 %. Verificado: 190 tests; huella idéntica.

---

## F031 - 2026-11-23
- `src/trafico/costos.py`: riesgo con el modelo potencia (exponentes de Elvik 2009: 4.1 / 2.6 / 1.1) y la curva de Kloeden 2001 (rural), por separado; las medidas del simulador quedan en los CSV. `Precios` en MXN con escenarios bajo / medio / alto y `con_precios(...)` para cambiar cualquiera; `balance(...)` da tiempo, combustible, CO2, accidentes y total.
- sondas.csv suma `v_media_kmh`; corridas.csv, `v_media_fondo` (para Kloeden).
- Precios documentados como supuestos en docs/datos.md.
- Verificado: 196 tests; huella idéntica.

---

## F032 - 2026-11-23
- `overtaking.gap_logit` (alias `rebase_logit`): logit de aceptación de hueco con término propio de cada conductor (al estilo de Farah 2009/2010). U = −3 + 1·S + 0.05·Δv + 0.3·min atrapado + η. S = tiempo sobrante frente al contrario más cercano (o el supuesto al final de la visibilidad o el que podría entrar por el otro extremo). Coeficientes supuestos, documentados en docs/datos.md.
- Sin piso por defecto (decisión del usuario); `piso_seguro=1` exige además el criterio de siempre.
- Sorteos por hash splitmix64 de (semilla, vehículo, hueco): no consumen números aleatorios, cada conductor decide una vez por hueco, mismo resultado en CPython y PyPy.
- Choques: ahora cada par cuenta una vez (antes cada paso encimados); columna `choques` en viajes y sondas, `veh_km` en corridas. Después del choque los dos siguen.
- Estrés (15 km, 400 veh/h, 8 semillas, simple / realista / realista con curvas y montañoso): 0 choques sin piso; rebases +18 % (simple) y +11 % (realista); 41 / 4 / 6 vehículos con frenado de emergencia. Con piso, igual al criterio de siempre.
- Todavía no entra en el preset realista (se decide junto con F033).
- Verificado: 203 tests; huella idéntica (también en PyPy).

---

## F033 - 2026-11-23
- `overtaking.peek` (alias `asomarse`): línea de visión en planta detrás de los vehículos a rebasar (ojo 0.4 m a la izquierda en autos / 0.6 en camiones, + 0.6 m que se asoma; anchos 1.8 / 2.6 m; carril 3.5 m). D = g·(2.6 − y_ojo)/(borde − y_ojo). Un camión ve por encima de un auto. Los que ya rebasan delante siguen con la regla fija.
- Estrés realista con 20 % camiones (15 km, 400 veh/h, 8 semillas): rebases 0.19 → 0.28 por vehículo en recta y 0.13 → 0.22 en curvas y montañoso; 0 choques; 2-5 vehículos con frenado de emergencia (con logit: 11-24).
- Decisión (según el plan, tras validarlos): B1 (logit) y B2 (asomarse) entran en PRESET_REALISTA. Cambia la huella realista (regenerada a propósito; la del simple sigue idéntica; PyPy igual). descomponer_realista.py, animación y menú actualizados.
- Verificado: 208 tests.

---

## F034 - 2026-11-23
- `passing_lanes` (alias `carriles_rebase`, "inicio:fin:sentido;..."): carril extra 2 (+1) / 3 (−1). Road: `passing_end`, `passing_blocked` (el otro sentido no rebasa en el tramo ± 100 m; dentro del tramo propio se usa el carril extra). overtaking: `_start_carril` (hueco en el carril extra, que alcance para rebasar antes de la incorporación y que el carril extra no vaya igual de lento) y `_volver_de_carril` (se queda si hay otro lento cerca; obligado en los últimos 250 m con márgenes a la mitad). El fin del carril es un obstáculo detenido en los últimos 250 m.
- Hallazgos al validar: (1) si el de delante también se pasaba al carril extra, el auto nunca lo "rebasaba" y abortaba al final → ahora cuenta como rebasado; (2) el obstáculo del fin frenaba desde 500 m → solo en la zona de incorporación; (3) regresar sin rebasar porque el objetivo se fue al carril extra no es aborto.
- Estrés (12 km, 4 tramos de 1.5 km, realista con 20 % camiones, 300/600/900 veh/h, recta y montaña, 4 semillas): 0 choques; rebases 0.57-0.82 por vehículo (sin tramos: 0.17-0.27).
- `t_carril_contrario` ya no cuenta el carril extra. Verificado: 214 tests; huella idéntica (CPython y PyPy).

---

## F035 - 2026-11-23
- Animación: con carriles de rebase la vía tiene tres franjas (contrario, extra, propio), doble raya amarilla del lado del sentido de un solo carril, discontinua entre los dos carriles del mismo sentido; tramos marcados en el mapa; "N tramos con carril de rebase" en la lista del modelo. Capturas revisadas (fuera de tramo y con un vehículo del sentido ← rebasando por el carril extra).
- Menú: pregunta por tramos 2+1 (cada cuántos km y largo); `config.patron_2mas1` los genera alternando el sentido.
- Incorporación al final y estrés: ver F034 (0 choques; test_passing_lane incluye estrés realista en montaña con 20 % camiones a 600 veh/h).
- Verificado: 215 tests.

---

## F036 - 2026-11-23
- `src/trafico/mejor.py` + `trafico graficar DIR --mejor [--precios ...] [--precio k=v]`: tablas `mejor_por_velocidad.csv` y `mejor_velocidad.csv` (velocidad de menor costo por escenario y rango que no se distingue del mínimo, con diferencia emparejada por semilla) y gráficas de tiempo, ganancia contra 100 y por cada +10, combustible, riesgo de Kloeden, costo por escenario y partes del costo (barras apiladas). Paleta categórica del proyecto, un solo eje, leyenda arriba y etiquetas directas (skill dataviz).
- Escenarios: bajo / medio / alto (modelo potencia) y medio_kloeden.
- Campañas: velocidades por defecto 90-150 de 10 en 10 (CLI y menú). Menú → graficar pregunta por la mejor velocidad.
- Prueba con una campaña chica (8 km, 100 y 300 veh/h): con precios medios la mejor es 90 km/h; a 300 veh/h, de 90 a 120 no se distingue (el tráfico no deja ir más rápido: la velocidad media solo pasa de 89 a 100 km/h).
- Verificado: 219 tests.

---

## Corrección al correr las campañas de F037 - 2026-11-23
- Con sondas a 150 km/h aparecieron choques en el realista, incluso con el criterio fijo. Causa: al planear el rebase, el pelotón a rebasar se armaba con huecos de 44.5 m, pero con `return_closing` el regreso exige además la distancia para frenar desde la velocidad del rebase (a 150 contra 83 km/h, +57 m). La sonda no podía volver, seguía de largo por el carril contrario rebasando a un pelotón que nunca evaluó y terminaba en frenado de emergencia (en un caso, la alcanzaron por detrás al volver casi detenida).
- Corrección (`overtaking._frenar_al_volver`, solo con `return_closing`): el plan usa el mismo hueco que el regreso. Realista recta 200 veh/h, 8 semillas, sonda a 150: choques 1 → 0; sustos por corrida 2.9 → 1.5 (criterio fijo) y 12.2 → 9.8 (logit). El modelo simple no cambia; la huella tampoco (sus corridas cortas no caen en el caso).
- Se vuelven a correr las cinco campañas realistas de la fase 4.
