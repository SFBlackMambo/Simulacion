# Plan: Simulación de tráfico en carretera de 2 carriles (rebase con velocidad deseada)

**Creado**: 2026-11-21 | **Esfuerzo**: ~26h | **Complejidad**: Media | **Estado**: APROBADO (2026-11-21)

## 1. Objetivo
**Meta**: simular vehículos con velocidad deseada fija en una carretera de un carril por sentido, con rebase por el carril contrario, y medir el tiempo de viaje en función de la velocidad deseada.
**Por qué**: cuantificar cuánto tiempo se gana de verdad al ir a 130 en vez de 120 km/h cuando hay vehículos lentos delante y el rebase está limitado por el tráfico contrario.
**Éxito**:
- Sin tráfico, el tiempo de viaje es L / v0 (prueba de validación).
- Un vehículo rápido se queda detrás de uno lento y solo rebasa cuando el carril contrario está libre.
- Se obtiene la diferencia de tiempo promedio (con intervalo de confianza) entre 120 y 130 km/h, para varias densidades de tráfico.

## 2. Enfoque
**Motor**: pasos de tiempo, dt = 0.1 s. Es el más simple y robusto para seguimiento y rebase.

**Modelo de vehículo** (Python con `dataclass`):
- Atributos: posición, velocidad, velocidad deseada v0, longitud y sentido.
- Seguimiento: IDM (Intelligent Driver Model). Con vía libre el vehículo converge a su v0. Al alcanzar a uno más lento, frena y se mantiene detrás.

**Carretera**:
- Longitud L configurable (por defecto 20 km) y dos carriles, uno por sentido.
- Los vehículos entran por su extremo con llegadas de Poisson (tasa por sentido) y velocidades deseadas aleatorias, por ejemplo Normal(100, 10) recortada a un rango.
- Al llegar al final salen de la simulación y se registra su tiempo de viaje.

**Máquina de estados del rebase**: `SIGUIENDO → REBASANDO → REGRESANDO`
- Se considera rebasar si el líder es más lento que v0 por más de un umbral y la distancia es menor a un valor dado.
- Se inicia solo si el carril contrario está libre en la distancia que se recorrería durante la maniobra, considerando la velocidad de cierre del vehículo contrario más un margen de seguridad.
- Se regresa al carril propio cuando hay un hueco suficiente delante del vehículo rebasado.
- El MVP no incluye abortar el rebase. El margen de seguridad lo cubre y se registra si algún vehículo contrario tuviera que frenar.

**Diseño del experimento** (clave para la pregunta del usuario):
- Vehículos etiquetados ("sonda") con v0 = 100, 110, 120, 130, etc., que cruzan toda la vía.
- Números aleatorios comunes: se usa la misma semilla de tráfico de fondo y solo se cambia la v0 de la sonda. Así la diferencia entre 120 y 130 no se pierde en el ruido.
- Muchas réplicas con distintas semillas y reporte de media ± IC 95 %.
- Métricas: tiempo de viaje, retraso respecto al tiempo libre (L / v0) y número de rebases.

**Stack**: Python 3.13, numpy, matplotlib, pytest, `pyproject.toml` y venv local. Sin frameworks de simulación, para controlar el modelo.

**Estructura propuesta**:
```
src/trafico/  vehicle.py, idm.py, overtaking.py, road.py, arrivals.py, simulation.py, experiments.py
tests/
scripts/      run_experiment.py (gráficas)
```

**Trade-offs**:
| Decisión | Elegido | Alternativas |
|---|---|---|
| Motor | Pasos de tiempo | Eventos discretos (más difícil el rebase) |
| Seguimiento | IDM | Nagel-Schreckenberg (celdas discretas, menos preciso en km/h) |
| Tráfico | Poisson + v0 aleatoria | Flota fija (puede añadirse como escenario de prueba) |

## 3. Tareas (cada una <4h)

**Fase 1: Base** (~5h)
1. Estructura del proyecto, `pyproject.toml`, venv, `.gitignore`, README: 1.5h | Deps: ninguna | Riesgo: B
2. Vehículo e IDM con tests (un vehículo solo llega a su v0; frena detrás de uno lento): 2.5h | Deps: 1 | Riesgo: M
3. Carretera de un carril con entrada/salida de vehículos y registro de tiempos: 2h | Deps: 2 | Riesgo: B

**Fase 2: Tráfico y rebase** (~10h)
4. Generador de llegadas Poisson y velocidades deseadas, con semilla: 1.5h | Deps: 3 | Riesgo: B
5. Segundo carril en sentido contrario e interacción entre carriles: 2.5h | Deps: 3 | Riesgo: M
6. Criterio de rebase (hueco seguro con el tráfico contrario): 3.5h | Deps: 5 | Riesgo: **A**
7. Máquina de estados del rebase (invadir, adelantar, regresar), con tests de escenarios: 3.5h | Deps: 6 | Riesgo: **A**

**Fase 3: Experimentos** (~7h)
8. Vehículos sonda, números aleatorios comunes y réplicas: 3h | Deps: 7 | Riesgo: M
9. Estadística (media, IC 95 %, diferencia pareada 120 vs 130): 2h | Deps: 8 | Riesgo: B
10. Gráficas: tiempo vs v0, retraso vs densidad, diferencia 130-120: 2h | Deps: 9 | Riesgo: B

**Fase 4: Cierre** (~4h)
11. Calibración y análisis de sensibilidad (densidad, umbral de rebase, margen): 2.5h | Deps: 10 | Riesgo: M
12. README con resultados, primer push a GitHub: 1.5h | Deps: 11 | Riesgo: B

**Total**: ~26h

## 4. Calidad
- **Tests (pytest)**:
  - Unitarios: IDM, criterio de rebase, generación de llegadas.
  - Escenarios deterministas: vía libre (tiempo = L/v0), lento adelante con carril contrario libre, y con carril contrario ocupado.
  - Propiedades: nunca hay dos vehículos solapados en el mismo carril, ni colisiones frontales.
- **Validación**: ver los criterios de éxito (§1). Además, comparar el comportamiento cualitativo con el diagrama fundamental de IDM.
- Cobertura objetivo: 80 % en `src/`.

## 5. Riesgos
| Riesgo | Impacto | Mitigación |
|---|---|---|
| La lógica de rebase genera colisiones o bloqueos | A | Tests de escenarios y aserciones de no solape en cada paso |
| Resultados dominados por la elección de parámetros | M | Análisis de sensibilidad (tarea 11) y parámetros expuestos en un config |
| Ruido enorme al comparar 120 vs 130 | M | Números aleatorios comunes y muchas réplicas |
| Rendimiento lento en Python con muchos vehículos y pasos | M | Solo se evalúan vecinos cercanos; si hace falta, vectorizar con numpy |

**Supuestos**:
- Carretera recta y plana, sin intersecciones ni semáforos.
- Condiciones ideales: sin clima ni pendientes.
- Vehículos homogéneos (misma longitud y aceleración).
- Los conductores no cambian su v0 durante el viaje.

**Fuera de alcance (MVP)**: camiones o clases de vehículo, abortar un rebase, límites de velocidad, animación en vivo, interfaz web.

## 6. Preguntas que podemos investigar después
- ¿Cuánto cambia el beneficio de ir más rápido al aumentar la densidad del tráfico?
- ¿A partir de qué densidad deja de valer la pena ir a 130?
- ¿Cuántos rebases se hacen y cuánto tiempo se espera de media detrás de un lento?
- ¿Qué efecto tiene el porcentaje de vehículos lentos?
- ¿Cuánto cuesta en frenadas del tráfico contrario cada rebase?
