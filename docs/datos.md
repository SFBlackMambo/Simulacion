# Diccionario de datos

Unidades: metros, segundos y km/h, salvo que se diga otra cosa. Las posiciones `x` se miden en el sistema
de la carretera (las del sentido +1): 0 es la entrada del sentido +1 y `longitud` su salida.

## Campaña (`trafico campana ... --salida DIR`)

| Archivo | Una fila por | Contenido |
|---|---|---|
| `campana.json` | — | Configuración base, parámetros barridos, velocidades de sonda y semillas |
| `corridas.csv` | corrida | Resumen del tráfico de fondo (medias de los vehículos que hicieron el viaje completo) |
| `sondas.csv` | sonda | Tiempo de viaje de cada sonda |
| `viajes.csv` | vehículo de cada corrida | Todo lo de abajo (se guarda por defecto; `--sin-viajes` lo apaga) |
| `trayectorias/` | — | Opcional (`--trayectorias S`): un CSV por corrida, ver más abajo |

Todas las filas de `corridas.csv`, `sondas.csv` y `viajes.csv` empiezan con la **clave de la corrida**:

| Columna | Significado |
|---|---|
| `combo` | Número de combinación de parámetros barridos (0, 1, ...) |
| *(un nombre por parámetro barrido)* | Valor del parámetro en esa combinación, p. ej. `flow_per_hour`, `trazado` |
| `v_sonda` | Velocidad deseada de las sondas de esa corrida, km/h |
| `semilla` | Semilla del tráfico de fondo. Con la misma semilla y distinta `v_sonda` el tráfico de fondo es el mismo (números aleatorios comunes) |

**Ojo:** cada corrida repite el mismo tráfico de fondo para cada `v_sonda`. Para estudiar el tráfico de fondo
sin duplicarlo, filtra una sola `v_sonda`. Para comparar velocidades usa las sondas (`sonda = 1`).

`corridas.csv` tiene además `con_viajes` (1 si esa corrida guardó sus viajes; las campañas reanudadas pueden
tener corridas viejas sin viajes).

## `viajes.csv`

Un renglón por vehículo que salió de la carretera. En la corrida única (`trafico corrida`) es el mismo archivo,
sin la clave de la corrida.

| Columna | Unidad | Significado |
|---|---|---|
| `id` | — | Identificador del vehículo dentro de la corrida |
| `sentido` | — | 1 o -1 |
| `v0_kmh` | km/h | Velocidad deseada |
| `sonda` | 0/1 | 1 si es un vehículo sonda (velocidad fija, entra a intervalos regulares) |
| `viaje_completo` | 0/1 | 0 si empezó a mitad de la carretera (modo `lleno`): no uses su tiempo de viaje |
| `t_entrada`, `t_salida` | s | Instantes de entrada y salida (tiempo simulado) |
| `tiempo_viaje` | s | `t_salida - t_entrada` |
| `tiempo_libre` | s | Lo que tardaría solo en la carretera (con curvas, pendientes y límites) |
| `retraso` | s | `tiempo_viaje - tiempo_libre`: lo que le costó el tráfico |
| `rebases` | — | Vehículos que rebasó |
| `abortos` | — | Rebases abortados |
| `veces_rebasado` | — | Veces que otro lo rebasó |
| `alcances` | — | Veces que tuvo que bajar de su velocidad deseada por alguien delante |
| `t_lento` | s | Tiempo yendo más de 1 m/s por debajo de la velocidad que busca |
| `t_espera_entrada` | s | Tiempo esperando hueco para entrar |
| `frenado_emergencia` | 0/1 | Usó el frenado de emergencia (choque frontal inminente) |
| `clase` | — | `auto` o `camion` |
| `rebases_en_cadena` | — | Rebases empezados siguiendo a otro que ya rebasaba |
| `conductor` | — | `prudente`, `normal` o `agresivo` |
