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
| `v_media_kmh` | km/h | Velocidad media del viaje (longitud / tiempo de viaje); vacío si no hizo el viaje completo |
| `t_headway_2_5` | s | Tiempo con headway ≤ 2.5 s respecto al de delante (frente a frente de los dos, en tiempo). Es la definición de "seguidor" del HCM 7.ª ed. |
| `t_headway_3` | s | Tiempo con headway < 3 s (definición del HCM 2010 para el PTSF) |
| `pct_tiempo_siguiendo` | % | `100 · t_headway_3 / tiempo_viaje`: porcentaje del tiempo de viaje siguiendo a otro |
| `t_carril_contrario` | s | Tiempo en el carril del otro sentido (rebasando) |
| `ttc_min_lider` | s | Mínimo tiempo a colisión con el de delante (hueco / diferencia de velocidad, cuando se acerca). Vacío si nunca se acercó |
| `ttc_min_contrario` | s | Mínimo tiempo a colisión frente a frente con un vehículo del otro sentido en su mismo carril (hueco / suma de velocidades). Para quien rebasa y para quien viene de frente. Vacío si nunca hubo |
| `conflictos_lider` | — | Episodios con TTC < 1.5 s con el de delante (umbral de SSAM, Gettman y Head 2003) |
| `conflictos_contrario` | — | Episodios con TTC < 1.5 s frente a frente |
| `factor_limite` | × | Cuánto se pasa del límite de velocidad (1 = lo respeta; 1.2 = va 20 % arriba) |
| `potencia_w_kg` | W/kg | Potencia específica en la rueda (autos 22; camiones según su relación peso/potencia) |
| `lb_hp` | lb/hp | Relación peso/potencia del camión (solo camiones; redondeada al 0.5 W/kg) |

Notas: el headway y el TTC se miden respecto al vehículo de delante en el carril que se ocupa (mientras rebasa,
el de delante en el carril contrario). Estas medidas solo se registran: no cambian la simulación.

`corridas.csv` resume además, para el tráfico de fondo con viaje completo: `pct_siguiendo_fondo` (media de
`pct_tiempo_siguiendo`), `t_contrario_fondo` (s), y para todos los vehículos `conflictos_lider` y
`conflictos_contrario` (totales de la corrida).

## Trayectorias (`--trayectorias S`, opcional)

Una fila por vehículo cada `S` segundos, al estilo NGSIM. En la corrida única es `trayectorias.csv`. En una
campaña es `trayectorias/combo<k>_v<v_sonda>_s<semilla>.csv`, un archivo por corrida. Con `--solo-sondas`
solo se guardan las sondas. Son archivos grandes: una corrida de 20 km a 200 veh/h con `S = 1` tiene ~1 millón
de filas (~60 MB).

| Columna | Unidad | Significado |
|---|---|---|
| `t` | s | Instante |
| `id`, `sentido`, `clase`, `sonda` | — | Como en `viajes.csv` (`id` coincide) |
| `x` | m | Posición del frente en el sistema de la carretera |
| `x_propio` | m | Posición del frente medida desde la entrada de su sentido (0 a `longitud`) |
| `carril` | — | 0 = carril del sentido +1, 1 = carril del sentido -1 (si no coincide con su sentido, va rebasando) |
| `v_kmh` | km/h | Velocidad |
| `a` | m/s² | Aceleración aplicada en el último paso |
| `largo` | m | Longitud del vehículo |
| `estado` | — | `SIGUIENDO`, `REBASANDO` o `REGRESANDO` |
| `id_lider` | — | Vehículo de delante en su carril y sentido (vacío si no hay) |
| `hueco_m` | m | Distancia libre hasta el de delante (parachoques a parachoques) |
| `headway_s` | s | Headway frente a frente con el de delante |
| `id_seguidor` | — | Vehículo de detrás en su carril y sentido (vacío si no hay) |
