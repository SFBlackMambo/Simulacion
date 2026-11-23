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
