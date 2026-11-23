# Exploration: Simulador de tráfico `trafico` (estado tras la fase 3)

**Fecha**: 2026-11-22 | **Alcance**: Medium (todo el código) | **Estado**: ✅ Completo
**Commit**: `0accc59` (master, limpio, remote `origin` = github.com/SFBlackMambo/Simulacion)
Reemplaza la exploración del 2026-11-21, que describía el repo vacío.

## 1. Foundation
- **Stack**: Python ≥3.10 (venv con 3.14.4), numpy, matplotlib; extras `dev` (pytest, pytest-cov) y `anim` (pygame-ce). Opcional: PyPy 3.11 en `.venv-pypy` (`scripts/instalar_pypy.sh`, con SHA256) para `trafico campana --rapido`.
- **Arquitectura**: paquete de biblioteca + CLI (`trafico = trafico.cli:main`), simulación microscópica por pasos de tiempo (dt 0.2 s en `SimConfig`): IDM/HDM para seguir al de delante y una máquina de estados para rebasar por el carril contrario.
- **CLAUDE.md**: no existe (ni en la raíz, ni en `.claude/`, ni el global). Las convenciones salen del historial (ver §2).
- **Estado EPCC**: 27 features en `epcc-features.json` (INFRA-001, F001-F026), todas `verified`. Fases 1, 2 y 3 aprobadas y terminadas.

### Mapa de módulos (`src/trafico/`, ~4,300 líneas)
| Capa | Módulos | Papel |
|---|---|---|
| Modelo | `vehicle.py`, `idm.py`, `fleet.py`, `slopes.py`, `drivers.py` | Estado del vehículo, IDM + HDM, camiones (`TruckParams`), física de pendientes (`GradeResponse`), rasgos del conductor |
| Mundo | `geometry.py` (484), `arrivals.py` | Curvas, visibilidad, pendientes, límites, zonas de no rebase, tablas por celda; presets `PRESETS` (trazado) y `RELIEVES`; llegadas de Poisson |
| Motor | `road.py` (407), `overtaking.py` (336) | `Road.step()`: entradas → `overtaking.update` → aceleraciones por grupo (carril, sentido) → reacción y tope de frenado → avance → colisiones → salidas |
| Corrida | `simulation.py` (`SimConfig`, `run_simulation`, `free_time`, caché `_GEOMETRIAS`), `recorder.py`, `single.py` | Una corrida con sondas; registro opcional que solo lee |
| Experimentos | `experiments.py`, `campaign.py`, `stats.py`, `analysis.py` | Réplicas en paralelo, campañas reanudables (CSV crudos), IC 95 % pareado |
| Salida/UI | `plots.py`, `plots_explore.py`, `animation.py` (502), `menu.py`, `cli.py`, `config.py` | Gráficas Agg, animación pygame, menú, CLI `corrida/animar/campana/graficar`, alias de parámetros y `PRESET_REALISTA` |
| Scripts | `scripts/run_experiment.py`, `sensitivity.py`, `descomponer_realista.py` | Experimentos publicados en el README (`docs/*.csv/png`) |

## 2. Patterns
- **Config inmutable con nombres por puntos**: `SimConfig` y los anidados (`IDMParams`, `OvertakeParams`, `TruckParams`, `DriverModel`) son dataclasses congeladas. `config.set_param(cfg, "overtaking.t_guard", v)` + `ALIAS` en español (`flujo`, `camiones`, `reaccion`…) los usa el CLI (`--param`, `--barrer`), el menú y las campañas. Un parámetro nuevo necesita el campo en la dataclass, el alias (si es para el usuario) y, si es una tupla, el parseo en `set_param`/`from_dict`.
- **Todo apagado por defecto**: cada pieza de la fase 3 tiene un valor neutro (0, False, ()) y vive en `config.PRESET_REALISTA`. Invariante central: con los valores por defecto los resultados son **idénticos bit a bit** a los de las fases 1 y 2.
- **Números aleatorios comunes**: `SeedSequence(seed).spawn` da generadores separados para las llegadas de cada sentido, los conductores y los camiones (`simulation.build_road`). Un rasgo nuevo que sortee valores debe usar su propio generador y no consumir números cuando está apagado.
- **Rendimiento por tablas**: velocidad permitida por celda (`geo.vlim_list`, `mult_list`, `grade_list`) guardada en cada vehículo (`veh.vlim`, `veh.mult`), geometría en caché por proceso, descarte temprano en `overtaking._is_safe`. Cualquier cambio de rendimiento debe conservar los resultados bit a bit.
- **Seguridad del rebase**: `_is_safe` (hueco frente al contrario, visibilidad, vista tapada, zonas), `_threat` (abortar), `_try_return` (regreso con `return_closing`), frenado frontal de emergencia en `Road._head_on_brake`. Métricas de seguridad: `collisions` y `emergency_vehicles` (deben ser 0 o casi 0).
- **Código y documentación en español** (identificadores mezclados: API en inglés, internos en español), con comentarios que explican el porqué y citan las fuentes (NCHRP 505, TWOPAS, SCT, Treiber 2006).
- **Commits**: `feat(F0xx): ... - verificado`, `fix(...)`, `perf: ...`, `docs: ...`, en español.

### Tests
- pytest, 27 archivos y 159 funciones (168 casos con parametrize), **todos pasan en 91 s** (CPython 3.14).
- Estilo: escenarios mínimos armados a mano con `Road(...)` + `road.place(v0, x, v=..., lane=...)` + `road.step()`, y aserciones físicas (frenado ≤ 9 m/s², no rebasa si no cabe la salida…). Ejemplo: `tests/test_safety_realista.py`. Corridas cortas con `run_simulation` para la integración.
- No hay meta de cobertura configurada; en F001 fue del 100 %.

## 3. Constraints
- **Regresión "huella"**: los registros de progreso dicen "huella idéntica" en cada feature, pero **no existe una prueba automática** (grep de `huella|fingerprint` en `tests/` no da nada). Se revisa a mano. Es el principal hueco de calidad.
- **Paridad CPython/PyPy**: `--rapido` corre la simulación en `.venv-pypy` (o en `TRAFICO_PYPY`), así que el código del motor no puede depender de nada que PyPy no tenga (solo numpy).
- **Costo**: 20 km realista en montaña ≈ 20 s por corrida en CPython y 5 s en PyPy. Las campañas de fase 3 tienen cientos de corridas.
- **`.gitignore`** ignora `results/` y `*.png` salvo `docs/*.png`: lo que se publica va a `docs/`.
- Sin linter, formatter ni CI configurados (no hay ruff, black, mypy ni workflows).
- **Modelo sin calibrar**: el README avisa que la vista tapada (3 s detrás de un camión, 500 m detrás de un auto) es lo que más pesa en el resultado y no está calibrada.

## 4. Handoff
- **Para PLAN**: no hay features pendientes, así que el siguiente trabajo lo tiene que definir el usuario. Candidatos según lo explorado: (1) prueba automática de la huella (una corrida corta simple y una realista con valores fijados); (2) calibrar la vista tapada / "asomarse" para rebasar; (3) linter y CI opcionales. Cualquier feature nueva debe ir apagada por defecto, entrar en `PRESET_REALISTA` si aplica, tener su alias en `config.ALIAS` y usar su propio generador aleatorio.
- **Para CODE**: `.venv/bin/python -m pytest -q`; campañas con `trafico campana ... --nucleos 8 [--rapido]`; animación con `trafico animar --captura out.png` para revisar sin ventana.
- **Para COMMIT**: tests en verde, huella idéntica con todo apagado, 0 colisiones en las corridas de estrés, README y `docs/` al día.
- **Basura menor**: directorio vacío `./2` en la raíz (no está en git; parece un resto de un comando) y `scripts/__pycache__/`.

---

# Anexo (2026-11-22): datos de viajes y propuestas desde la literatura

## Estado actual de los datos de viajes
- `trafico campana --viajes` ya guarda `viajes.csv`: una fila por vehículo y corrida, con las columnas del barrido, `v_sonda`, `semilla` y los campos de `recorder.CAMPOS_VIAJE`. Viene **apagado por defecto**; en el menú la pregunta trae "no" como respuesta por defecto.
- Ninguna campaña publicada (`results/curvas`, `distancia`, `f3_*`) lo tiene: para obtenerlo hay que volver a correrlas.
- `campaign.run_campaign` trata `viajes` como parte fija de la campaña: si se reanuda una campaña ya existente con `--viajes`, sale el error "ya tiene otra campaña".
- Tamaño: unos 450 viajes por corrida (20 km a 200 veh/h); una campaña de 352 corridas daría unas 160 mil filas, ≈25 MB de CSV.
- Lo que no se guarda: el tiempo siguiendo a otro con headway < 2.5 o < 3 s, el tiempo en el carril contrario, el TTC mínimo de cada rebase, la potencia del camión (lb/hp), `limit_factor`, la velocidad media en el espacio, la energía y el CO2, y las trayectorias de las campañas.

## Propuestas (literatura; las citas no se verificaron en línea)
| # | Feature | Fuente principal | Dificultad |
|---|---|---|---|
| D1 | Viajes guardados siempre en las campañas, que se puedan añadir a una campaña ya hecha, y un diccionario de columnas | (propio) | baja |
| D2 | Columnas nuevas por viaje: t siguiendo (h ≤ 2.5 s / < 3 s), t en carril contrario, TTC mínimo con el contrario y con el líder, lb/hp, factor de límite, conductor | HCM; Gettman & Head 2003 (SSAM) | baja |
| D3 | Detectores virtuales (cada 1-2 km: paso, velocidad, headway) → PF, FD y LOS del HCM 7.ª ed., ATS, PTSF, tamaño de pelotones | NCHRP 17-65 / HCM 2022 cap. 15; Brilon & Weiser 2006 | baja |
| D4 | Rebases: demanda (alcances) frente a oferta (rebases), margen de seguridad al regresar, tipo lanzado o acelerativo | Polus et al. 2000; Llorca et al. 2013/2015 | baja-media |
| D5 | Combustible y CO2 por viaje con VSP/MOVES (y opcionalmente VT-Micro) | Jiménez-Palacios 1999; Rakha et al. 2004/2011 | media |
| D6 | Riesgo relativo con el modelo potencia (Nilsson/Elvik) y balance en dinero tiempo/combustible/riesgo/CO2 | Elvik 2009; USDOT VTT 2016 | baja |
| D7 | Trayectorias opcionales tipo NGSIM (submuestreadas a 1 s) | NGSIM | baja |
| B1 | Aceptación de hueco probabilística (logit de Farah) con heterogeneidad entre conductores | Farah et al. 2009; Farah & Toledo 2010 | media |
| B2 | "Asomarse" (desplazamiento lateral) en lugar de la vista tapada sin calibrar | Hegeman 2008 | media |
| B3 | Carriles de rebase / tramos 2+1 | HCM 2010; Tapani 2005 (RuTSim); Potts & Harwood 2003 | media-alta |
| V1 | Validación macro: curvas ATS/PTSF/FD contra flujo, comparadas con el HCM | HCM | baja (requiere D3) |

No se encontró ningún conjunto de datos público de trayectorias en carreteras rurales de dos carriles: highD, NGSIM y los de levelXdata son de autopista o de zona urbana, y SHRP2 NDS tiene acceso restringido.

## Decisión del usuario (2026-11-22)
- Para planear: **Datos de viajes** (D1, D2, D7) y **Comportamiento de rebase** (B1, B2, B3). Por ahora quedan fuera las medidas del HCM (D3, D4, V1) y el costo de ir más rápido (D5, D6).
- Formato de los datos: **CSV**.

## Nuevo enfoque del README (decisión del usuario, 2026-11-22)
- El README deja de comparar 120 contra 130. La pregunta pasa a ser: **¿qué velocidad deseada conviene más, si se pone en la balanza el tiempo que se gana contra el riesgo y el costo?** Y también: cuál llega antes y por cuánto.
- Por eso **D5 (combustible y CO2) y D6 (riesgo y balance en dinero) vuelven al plan**.
- Las campañas nuevas usan sondas de **90 a 150 km/h, de 10 en 10** (7 velocidades). Hay que volver a correr las campañas de las fases 1 a 3 con esas velocidades y con los viajes guardados, a ~3.5 veces el costo actual (conviene usar `--rapido`).
- Datos con los que ya contamos: la fase 1 midió de 100 a 140; las campañas de las fases 2 y 3 solo 120 y 130 (la de curvas, también 110). En este modelo, el tiempo de viaje baja siempre al subir la velocidad deseada, pero cada paso gana menos. Ejemplo a 200 veh/h: 767, 742, 725, 707 y 694 s. Así que "la que llega antes" siempre es la más alta. Lo que define la mejor es la comparación con el costo.
- Para PLAN, el riesgo se puede medir de tres formas, y hay que decidir cuál usar:
  1. Modelo potencia de Nilsson/Elvik. Es del flujo completo; para un vehículo solo no fue estimado así.
  2. Curva de riesgo individual de Kloeden et al., según cuánto se aleja de la velocidad media del flujo.
  3. Medidas que salen del propio simulador: TTC mínimo, sustos y margen al regresar.
  Lo más defendible es reportar las tres por separado y que el balance en dinero sea un escenario con parámetros que se puedan cambiar.
