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

---

# Plan fase 2: más datos, animación y curvas

**Creado**: 2026-11-22 | **Esfuerzo**: ~27h | **Estado**: COMPLETADO (2026-11-22)

## 1. Objetivo
- Dejar de medir solo "120 vs 130 en 20 km": guardar datos de **todos** los vehículos y poder barrer cualquier parámetro.
- Dos modos: **corrida única** (explorar y mostrar, con animación para una expo) y **campaña** (muchas simulaciones para obtener datos).
- Añadir **curvas**: límite de velocidad por radio y visibilidad que impide rebasar, para comparar carreteras rectas y con curvas.

## 2. Enfoque
- **Registro** (`recorder.py`): viajes de todos los vehículos, eventos de rebase y fotos periódicas; se puede apagar para las campañas.
- **Cantidad fija** (`Road.fill`): (a) carretera llena con N vehículos por sentido y entrada que mantiene la densidad; (b) exactamente N vehículos y fin cuando salen todos.
- **Campañas**: parámetros en la línea de comandos o en JSON, réplicas en paralelo, CSV crudos + `config.json`, reanudables; graficar es un comando aparte.
- **Animación**: pygame (dependencia opcional `[anim]`), vista esquemática en franja con curvas sombreadas, controles de pausa, velocidad y zoom.
- **Curvas**: geometría por tramos (recta o curva con radio). Velocidad máxima en curva √(a_lat·R) con frenado anticipado. La visibilidad en curva, d = 2·√(2·R·m) con despeje lateral m, limita los rebases: solo se rebasa si la maniobra completa cabe en lo que se ve.

## 3. Tareas
**Fase A: Datos** (~11h): F009 registro completo, F010 cantidad fija, F011 corrida única con gráficas, F012 campañas.
**Fase B: Animación** (~6h): F013 animación pygame, F014 menú interactivo.
**Fase C: Curvas** (~10h): F015 geometría y velocidad en curva, F016 visibilidad y zonas de no rebase, F017 generador de carreteras y campaña recta vs curvas.
**Fase D: Carreteras reales**: fuera de esta fase (importar GPX/OSM y calibrar con datos reales); otro EPCC.

## 4. Riesgos
| Riesgo | Mitigación |
|---|---|
| El registro hace lentas las campañas | Registro opcional; en campañas solo resúmenes por vehículo |
| Las curvas rompen la lógica de rebase (choques) | La regla de visibilidad solo restringe; se mantienen las pruebas de cero colisiones |
| pygame no está disponible en todas las PCs | Dependencia opcional; todo lo demás funciona sin ella |

---

# Plan fase 3: comportamiento más realista

**Creado**: 2026-11-22 | **Esfuerzo**: ~31h | **Estado**: COMPLETADO (2026-11-22)

## 1. Objetivo
Añadir camiones, cambio de carril gradual, rebase en cadena con visión tapada, pendientes, límites de velocidad y zonas de no rebase señalizadas, tipos de conductor con impaciencia y tiempo de reacción.

## 2. Decisiones
- Todo lo nuevo viene **apagado por defecto**: con los valores por defecto los resultados son idénticos bit a bit a los de las fases 1 y 2. Un preset `--realista` lo enciende con valores razonables.
- Camiones: 16.5 m, a = 0.5 m/s². Velocidad deseada: normal asimétrica (a = -3, loc 108.5, escala 6.5 km/h): moda ~105, 96 % entre 90 y 110, 0.5 % bajo 90, 3.5 % sobre 110; más 2 % de anomalías (1.5 % entre 60 y 90, 0.5 % entre 110 y 125). Tope 125 km/h.
- Los camiones se distinguen por forma (más largos, con cabina), no por color: la paleta ya está al límite de tonos distinguibles.
- Rebase en cadena: se puede seguir a otro que rebasa si el rebase propio es seguro. Detrás de un camión no se ve el carril contrario salvo a más de ~3 s; detrás de un coche se ve, pero menos lejos.
- Pendientes con modelo de potencia específica (W/kg): limita velocidad y aceleración en subida.
- Reacción: la aceleración responde con retraso; el frenado de emergencia sigue siendo inmediato.

## 3. Tareas
F018 camiones (4h), F019 cambio de carril gradual (4h, riesgo A), F020 rebase en cadena (4h, A), F021 pendientes (4h), F022 límites y zonas de no rebase (3h), F023 tipos de conductor e impaciencia (3h), F024 tiempo de reacción (3h, A), F025 animación y menú (3h), F026 campañas y README (3h).

## 4. Riesgos
| Riesgo | Mitigación |
|---|---|
| Choques al combinar cambio lento, cadena y reacción | Escenarios por feature; 0 colisiones en todas las campañas |
| Cambiar resultados previos sin querer | Cada feature apagada = resultados idénticos bit a bit (prueba de regresión) |
| Rendimiento con parámetros por vehículo | Medir; mantener O(n) por paso |

---

# Plan fase 4: datos de viajes, rebase calibrado y la mejor velocidad

**Creado**: 2026-11-22 | **Esfuerzo**: ~45h | **Complejidad**: Compleja | **Estado**: APROBADO (2026-11-22)

## 1. Objetivo
**Meta**: responder qué velocidad deseada conviene más en una carretera de dos carriles, poniendo en la balanza el tiempo que se gana contra el combustible, el CO2 y el riesgo. Además, guardar los datos completos de cada viaje para que el usuario los analice por su cuenta.
**Éxito**:
- Cada campaña deja `viajes.csv` (todos los vehículos de todas las corridas) junto con un diccionario de columnas.
- Para cada escenario, el README muestra la curva tiempo–velocidad (90 a 150 km/h), cuál llega antes y por cuánto, y la velocidad con el menor costo total según precios que se pueden cambiar.
- Con todo lo nuevo apagado, los resultados son idénticos bit a bit (prueba automática). Sin B1 hay 0 colisiones en las campañas; con B1 las colisiones se miden y se reportan.

## 2. Enfoque y decisiones
- **Se mantienen los patrones de la fase 3**: todo apagado por defecto, alias en `config.ALIAS`, un generador aleatorio propio para cada rasgo nuevo y paridad entre CPython y PyPy (sin dependencias nuevas, solo numpy).
- **Las medidas nuevas solo leen el estado.** Se acumulan por vehículo en `Road.step` sin tocar la dinámica, y se guardan como columnas de `viajes.csv`. Así encenderlas no cambia ninguna trayectoria.
- **Los costos se calculan después de simular.** La simulación guarda litros, CO2, tiempo y medidas de riesgo. Los precios (valor del tiempo, combustible, costo de un accidente, CO2) se aplican en `graficar` o `analysis`, en un módulo `costos.py` con valores que se pueden cambiar. Cambiar un precio no obliga a volver a simular.
- **Riesgo**: se reportan tres medidas por separado y ninguna se mezcla con otra:
  1. modelo potencia de Nilsson/Elvik, con la velocidad media del flujo;
  2. curva individual de Kloeden, según cuánto se aleja del flujo;
  3. medidas del propio simulador: TTC mínimo, sustos y margen al regresar.
- **Combustible**: VSP de Jiménez-Palacios con tasas por intervalo al estilo MOVES, con coeficientes distintos para autos y camiones. Se revisa contra consumos de referencia a velocidad constante.
- **Rebase calibrado (B1)**: un modelo logit de aceptación de hueco con un término aleatorio por conductor (Farah). **Decisión del usuario: sin piso de seguridad.** El logit decide libremente y la seguridad depende de abortar el rebase (`_threat`). Puede haber choques: se cuentan, se reportan como resultado (choques por cada millón de veh-km, por velocidad deseada) y forman parte del riesgo "del simulador". Hay que definir qué pasa después de un choque (hoy solo se cuentan y los vehículos siguen).
- **Asomarse (B2)**: una línea de visión geométrica (ancho del vehículo de delante, distancia y desplazamiento lateral) reemplaza la regla fija de 3 s / 500 m, como un modo nuevo de `blocked_view`.
- **Carril de rebase / 2+1 (B3)**: tramos donde un sentido tiene un segundo carril, con la regla de ir por la derecha y una incorporación al final. Es lo más arriesgado (toca grupos de carriles, entrada y salida y la animación), así que va al final del comportamiento y partido en dos.
- **Preset**: B1 y B2 entran en `PRESET_REALISTA` solo después de validarlos. El modelo simple queda bit a bit igual; el realista cambia, y se vuelven a correr sus campañas de todos modos.
- **Datos**: CSV. Trayectorias opcionales, un archivo por corrida en `trayectorias/`, a 1 s (para una corrida de 20 km son ~0.5 M filas).

## 3. Tareas
**Base** (~2h)
- INFRA-002 Prueba automática de la huella: corridas cortas, una del modelo simple y una del realista, comparadas con valores guardados (2h) | Deps: ninguna | Riesgo: B

**Datos de viajes** (~10.5h)
- F027 Viajes siempre en las campañas: activados por defecto, `--sin-viajes` para apagarlos, se pueden añadir al reanudar, y `docs/datos.md` con el diccionario de columnas (2.5h) | Deps: INFRA-002 | B
- F028 Columnas nuevas por viaje: t con headway ≤ 2.5 s y < 3 s, t en el carril contrario, TTC mínimo con el contrario y con el líder, número de sustos, lb/hp, factor de límite, velocidad media espacial (3h) | Deps: F027 | M (no debe tocar la dinámica)
- F029 Trayectorias opcionales tipo NGSIM: `--trayectorias S`, en la corrida única y en las campañas, con la opción de guardar solo las sondas (2h) | Deps: F027 | B
- F030 Combustible y CO2 por viaje con VSP, para autos y camiones, y revisión contra referencias (3.5h) | Deps: F028 | M (coeficientes)

**Costo y riesgo** (~3.5h)
- F031 Riesgo (Nilsson, Kloeden, sustitutos) y `costos.py` con el balance en dinero y precios que se pueden cambiar (3.5h) | Deps: F028, F030 | M (valores de referencia)

**Comportamiento de rebase** (~15.5h)
- F032 Aceptación de hueco logit (Farah) con heterogeneidad, sobre el piso de seguridad (4h) | Deps: INFRA-002 | A (coeficientes sin verificar)
- F033 Asomarse: visión geométrica detrás del vehículo de delante (3.5h) | Deps: INFRA-002 | M
- F034 Carril de rebase / 2+1, parte 1: geometría, carriles extra y cambio de carril (4h) | Deps: F033 | A
- F035 Carril de rebase / 2+1, parte 2: incorporación al final, animación, menú y estrés sin choques (4h) | Deps: F034 | A

**La mejor velocidad** (~10h)
- F036 Barrido de sondas de 90 a 150 y análisis: curva tiempo–velocidad, ganancia contra 100 km/h y por cada +10, costo por velocidad y velocidad óptima según los precios (`graficar --mejor`) (3.5h) | Deps: F031 | M
- F037 Volver a correr las campañas de las fases 1 a 3 (más una de B1–B3) con 90 a 150, viajes guardados y `--rapido` (3h, casi todo es tiempo de cómputo) | Deps: F032–F036 | M (tiempo)
- F038 README con el nuevo enfoque: la mejor velocidad, por cuánto llega antes y a qué costo. Los resultados 120 contra 130 pasan a un anexo (3.5h) | Deps: F037 | B

**Total**: ~41.5h + ~3h de margen ≈ 45h

## 4. Calidad
- La prueba de la huella corre en cada feature. Las medidas nuevas tienen pruebas con escenarios armados a mano: por ejemplo, un vehículo a velocidad constante consume lo de referencia, y un rebase con un contrario a una distancia conocida da el TTC esperado.
- B2–B3: estrés en montaña, con camiones y con todo activado, con 0 colisiones. B1: se reportan choques, sustos y abortos; la opción de piso (`gap_floor=1`) debe dar 0 colisiones.
- Combustible: un auto a 100/120/130 km/h en llano queda dentro de ±15 % de las referencias publicadas.

## 5. Riesgos
| Riesgo | Impacto | Mitigación |
|---|---|---|
| Coeficientes de la literatura sin verificar (Farah, Elvik, VSP) | A | Verificar en la fuente al implementar; si no se puede, documentar el valor usado como supuesto y dejarlo como parámetro |
| El logit acepta huecos peligrosos y hay choques (el usuario lo aceptó) | A | Abortar mejor; reportar los choques por veh-km; se puede comparar con y sin piso usando `overtaking.gap_floor` |
| El 2+1 rompe supuestos de dos carriles físicos (0/1) en todo el código | A | Va al final, partido en dos; se puede dejar fuera sin afectar lo demás |
| Volver a correr las campañas tarda mucho (×3.5) | M | `--rapido` (PyPy), campañas que se reanudan, primero la de la fase 1 |
| Las columnas nuevas cambian la dinámica sin querer | M | Solo leen el estado; la huella lo prueba |
| El balance en dinero depende de los precios | M | Presentarlo como escenarios (bajo/medio/alto) y no como una sola respuesta |

**Supuestos**: el usuario está en México (lo confirmó: MXN). El dinero va en MXN, con valores de referencia de IMT/SCT si se encuentran y, si no, convertidos desde USDOT/HEATCO y marcados así.
**Fuera de alcance**: medidas del HCM con detectores virtuales (FD, PF, LOS), validación contra las curvas del HCM y Parquet.
