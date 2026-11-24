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
| `litros` | L | Combustible gastado en el viaje (gasolina los autos, diésel los camiones; ver abajo) |
| `l_100km` | L/100 km | `litros` por cada 100 km; vacío si no hizo el viaje completo |
| `co2_kg` | kg | CO2 del escape: 2.348 kg/L de gasolina y 2.689 kg/L de diésel (EPA) |
| `choques` | — | Choques en que estuvo (cada par de vehículos cuenta una vez; después del choque los dos siguen: no se modela lo que pasa después) |

Notas: el headway y el TTC se miden respecto al vehículo de delante en el carril que se ocupa (mientras rebasa,
el de delante en el carril contrario). Estas medidas solo se registran: no cambian la simulación.

`corridas.csv` resume además, para el tráfico de fondo con viaje completo: `pct_siguiendo_fondo` (media de
`pct_tiempo_siguiendo`), `t_contrario_fondo` (s), y para todos los vehículos `conflictos_lider` y
`conflictos_contrario` (totales de la corrida), `l_100km_fondo` (media del fondo) y `litros_sondas` (media
por sonda). `sondas.csv` trae por sonda `litros`, `co2_kg`, `t_carril_contrario`, `ttc_min_contrario`,
`conflictos` (con el de delante y frente a frente), `frenado_emergencia` y `choques`. `corridas.csv` trae
`veh_km` (km recorridos por los vehículos con viaje completo) para calcular choques por millón de veh-km.

### Combustible (`src/trafico/fuel.py`)

En cada paso se calcula la potencia específica en la rueda (VSP de Jiménez-Palacios 1999, kW/t):
`VSP = v·(1.1·a + 9.81·i + 0.132) + 0.000302·v³`, con la aceleración aplicada `a` y la pendiente `i`. Los
camiones usan masa rotatoria 1.05, rodadura 0.0065 y aire con CdA = 6 m²; su masa sale de la relación
peso/potencia con un motor de 430 hp (vehículo de proyecto de la SCT). El consumo sigue la línea de Willans
(como los modelos de potencia de Akçelik y VT-CPFM): `potencia de combustible = P0 + max(VSP, 0)·m/η`, con
autos P0 = 8 kW y η = 0.36 (gasolina, 32 MJ/L) y camiones P0 = 20 kW y η = 0.40 (diésel, 35.8 MJ/L).
Frenando o en bajada gasta solo P0.

Revisión: un auto en llano a velocidad constante gasta 5.7, 6.8 y 7.5 L/100 km a 100, 120 y 130 km/h
(+33 % de 100 a 130) y un camión de 29 t a 90 km/h, 31 L/100 km. Son supuestos razonables (consumos típicos
publicados), no una calibración contra un vehículo en particular; los coeficientes se pueden cambiar en
`fuel.py`.

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

## Riesgo y costos (`src/trafico/costos.py`)

Se calculan después de simular, a partir de `sondas.csv` o `viajes.csv`: cambiar un precio no obliga a volver a
correr. El riesgo se reporta con tres medidas, por separado:

| Medida | Qué es | Fuente |
|---|---|---|
| Modelo potencia | `(v / 100)^k`, con k = 4.1 (muertos), 2.6 (heridos graves), 1.1 (heridos leves), con la velocidad media del viaje | Nilsson 2004; exponentes rurales de Elvik 2009 |
| Curva individual | `exp(0.07039·Δv + 0.0008617·Δv²)`, Δv = velocidad media del viaje − la del tráfico de fondo (km/h) | Kloeden, Ponte y McLean 2001 (rurales) |
| Simulador | TTC mínimo, conflictos (TTC < 1.5 s), frenado de emergencia, tiempo en el carril contrario, choques | columnas de este diccionario |

El modelo potencia se estimó para la velocidad media de todo el flujo; aplicado a un solo vehículo es una
aproximación ("si todos fueran así"). La curva de Kloeden se midió entre −10 y +30 km/h, más o menos.

Balance de un viaje (MXN) = horas × valor del tiempo + litros × precio + toneladas de CO2 × costo social +
km × costo de los accidentes por veh-km × riesgo relativo (el del modelo potencia, con la parte de cada
gravedad, o el de Kloeden). Precios por escenario:

| Precio | Bajo | Medio | Alto | Nota |
|---|---|---|---|---|
| Valor del tiempo (por vehículo y hora) | 50 | 100 | 200 | ≈1.5 ocupantes; supuesto |
| Gasolina (por L) | 22 | 24 | 27 | precio en México con tope de ~24 |
| Diésel (por L) | 24 | 26 | 29 | |
| CO2 (por t) | 1,000 | 2,000 | 3,800 | ≈ USD 51, 100 y 190 por t (IWG 2021, EPA 2023) a ~19 MXN/USD |
| Accidentes (por veh-km a 100 km/h) | 0.25 | 0.50 | 1.00 | orden de magnitud: ~1.5 muertos por 100 M veh-km × valor de una vida de ~15 M MXN, × ~2 por heridos y daños; supuesto |

Reparto del costo de los accidentes para el modelo potencia: 50 % muertos, 30 % heridos graves, 20 % leves.
Todos son supuestos sin verificar en una fuente oficial mexicana (IMT/SCT): se pueden cambiar con
`costos.con_precios("medio", valor_tiempo_h=150, riesgo="kloeden")`, o en `trafico graficar --mejor`.

## Aceptación de hueco con logit (`--param rebase_logit=1`)

En lugar del criterio fijo ("el contrario llega al menos 6 s después de terminar, suponiendo que acelera"), el
conductor acepta el hueco con probabilidad `P = 1 / (1 + e^-U)`, al estilo de Farah et al. (2009) y Farah y
Toledo (2010), con un término propio de cada conductor:

`U = b0 + b_spare·S + b_dv·Δv + b_wait·(minutos atrapado) + sigma·η`

- `S` (s): tiempo sobrante frente al contrario más cercano: lo que tarda en llegar al punto donde termina la
  maniobra, a la velocidad que lleva, menos la duración de la maniobra. También cuenta uno supuesto donde se
  acaba la visibilidad (a 30 m/s) y uno que podría entrar por el otro extremo. Los agresivos e impacientes
  suman `t_guard·(1 − factor)` (ven el hueco más grande).
- `Δv` (km/h): cuánto quiere ir por encima del de delante. `η ~ N(0, 1)`, distinto para cada conductor (0 para
  las sondas).
- Valores (supuestos; los de Farah no se pudieron verificar): `b0 = −3`, `b_spare = 1/s`, `b_dv = 0.05`,
  `b_wait = 0.3`, `sigma = 1`. Con ellos la mitad acepta un sobrante de 3 s (con Δv = 0) y casi nadie uno
  negativo. Se cambian con `--param overtaking.logit_b0=...`, etc.
- Cada conductor decide una sola vez ante cada hueco (el sorteo depende de la semilla, del vehículo y del
  contrario que limita), así que no "vuelve a tirar los dados" cada segundo.
- Sin piso de seguridad: si acepta un hueco malo, lo que lo salva es abortar y el frenado de emergencia.
  Con `--param piso_seguro=1` se exige además el criterio de siempre.

Estrés (15 km, 400 veh/h, 8 semillas, sondas a 130): sin piso, 0 choques. Los rebases suben de 0.39 a 0.46 por
vehículo (simple) y de 0.22 a 0.24 (realista), con 41 y 4 vehículos con frenado de emergencia. Con piso queda
igual al criterio de siempre.

## Asomarse para ver (`--param asomarse=1`)

Reemplaza la regla fija de la vista tapada ("a menos de 3 s de un camión no se ve nada; a menos de 2 s de un
auto se ven 500 m") por una línea de visión en planta (Hegeman 2008 observó que quien quiere rebasar se asoma
hacia la raya central). El ojo del conductor va 0.4 m a la izquierda del centro de su auto (0.6 en un camión)
más 0.6 m que se asoma. El vehículo de delante tapa hasta la mitad de su ancho (auto 1.8 m, camión 2.6 m) y el
contrario más cercano está a 3.5 − 0.9 = 2.6 m. Detrás de un vehículo a `g` m se ve hasta
`D = g·(2.6 − y_ojo)/(borde − y_ojo)`:

| Delante, a 20 m | Sin asomarse | Asomado 0.6 m |
|---|---|---|
| Auto | 88 m | todo (el ojo queda fuera del borde) |
| Camión | 49 m | 107 m (a 80 m: 427 m) |

Un camión ve por encima de un auto. Los que ya rebasan delante en el carril contrario siguen tapando con la
regla fija. En curvas se toma lo menor entre esto y la visibilidad del trazado.

Desde F033, el preset realista usa asomarse y la aceptación de hueco con logit (sin piso).

## Carriles de rebase / tramos 2+1 (`--param "carriles_rebase=2000:4000:1;6000:8000:-1"`)

Cada tramo `inicio:fin:sentido` (m, en coordenadas de la carretera) le da un segundo carril a un sentido. En
`carril` de trayectorias y fotos, el carril extra es el 2 (sentido +1) o el 3 (sentido -1).

- Dentro de su tramo, quien quiere rebasar se pasa al carril extra (con las mismas condiciones para querer
  rebasar). Solo hace falta hueco en ese carril: ahí no hay tráfico de frente. No entra si no alcanza a dejar
  atrás al de delante antes de los últimos 250 m, ni si el carril extra va igual de lento.
- Se queda en el carril extra mientras tenga delante, cerca, a otro más lento, y vuelve a la derecha cuando hay
  hueco (incluyendo lo que necesita para frenar hasta la velocidad del otro).
- Incorporación al final: en los últimos 250 m tiene que volver y los márgenes bajan a la mitad. Si no cabe,
  el fin del carril funciona como un obstáculo detenido: frena antes de llegar.
- El otro sentido no rebasa por el carril contrario a lo largo del tramo (con 100 m de margen en cada punta),
  como en una carretera 2+1 con doble raya.
- Rebases contados: los vehículos del carril derecho que dejó atrás. Aborto: llegar al final sin haber
  rebasado a nadie. `t_carril_contrario` no cuenta el carril extra.

Estrés (12 km con cuatro tramos de 1.5 km, realista con 20 % camiones, 4 semillas): 0 choques de 300 a
900 veh/h, en recta y en montaña. A 900 veh/h en montaña el carril extra se satura: muchos llegan al final sin
haber rebasado.

En el menú: "¿Con carriles de rebase?" pide cada cuántos km y el largo, y arma tramos que alternan el sentido
(`config.patron_2mas1`). En la animación, la vía tiene tres franjas: arriba el carril contrario, en medio el
carril extra y abajo el propio. Dentro de un tramo, la doble raya amarilla separa los sentidos y una
discontinua separa los dos carriles del mismo sentido.
