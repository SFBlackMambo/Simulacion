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
