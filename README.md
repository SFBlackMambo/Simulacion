# Simulación de tráfico en carretera de dos carriles

¿Cuánto tiempo se ahorra de verdad al ir más rápido en una carretera de un carril por sentido?

Simulación por pasos de tiempo de una carretera con **un carril por sentido**. Cada vehículo tiene
una **velocidad deseada fija** y busca mantenerla. Si alcanza a uno más lento, frena y lo sigue; solo
puede **rebasar invadiendo el carril contrario** cuando hay un hueco seguro frente al tráfico que viene
de frente y, en curvas, cuando **ve** lo suficiente. Ahí se pierde el tiempo.

![Animación](docs/animacion.png)

## Uso rápido

```bash
trafico                 # menú interactivo (recomendado)
trafico corrida ...     # una simulación con todos los datos y gráficas
trafico animar ...      # animación en vivo (para mostrar en una expo)
trafico campana ...     # muchas simulaciones barriendo parámetros
trafico graficar DIR    # gráficas de una campaña ya corrida
```

`python -m trafico ...` funciona igual. Cada comando acepta `-h` para ver todas sus opciones.

### Menú

`trafico` sin argumentos abre un menú que pregunta paso a paso (Enter acepta el valor por defecto):
corrida única, animación, campaña o graficar. Al final muestra el **comando equivalente**, para poder
repetir exactamente la misma corrida.

### Tráfico: tres formas de definirlo

| Modo | Qué significa | Opciones |
|---|---|---|
| `flujo` | Llegan vehículos al azar (Poisson), tantos por hora y sentido | `--flujo 200` |
| `lleno` | La carretera arranca con N vehículos por sentido y cada uno que sale se repone | `--modo lleno --vehiculos 70` |
| `total` | Entran exactamente N vehículos por sentido y la corrida termina cuando salen todos | `--modo total --vehiculos 200 --flujo 300` |

Velocidades deseadas Normal(`--v-media` 100, `--sigma` 10) km/h truncada a 60-140.
Las **sondas** son vehículos con velocidad deseada fija (`--vel-sonda 130`) que entran a intervalos
regulares y se miden aparte.

### Tipo de carretera

| `--trazado` | Descripción |
|---|---|
| `recta` | Sin curvas (por defecto) |
| `pocas` | 0.3 curvas por km, radio 300-900 m |
| `muchas` | 1.2 curvas por km, radio 150-450 m |
| `montana` | 2.5 curvas por km, radio 60-200 m |

Los trazados se generan al azar: con `--semilla-trazado 0` (por defecto) cada réplica tiene una carretera
distinta del mismo tipo, y con otro número el trazado queda fijo. También se pueden dar curvas a mano
(por ejemplo, de una carretera real): `--param "curves=1500:2500:200;6000:6400:350"` (inicio:fin:radio en m).

### Corrida única

```bash
trafico corrida --flujo 200 --longitud 20000 --vel-sonda 130 --sondas 5 --trazado pocas --salida results/r1
```

Guarda en la carpeta de salida:

- `viajes.csv`: un renglón por vehículo, con su velocidad deseada, tiempo de viaje, tiempo libre, retraso,
  rebases hechos, veces que lo rebasaron, **alcances** (veces que tuvo que frenar por alguien), tiempo lento
  y espera para entrar.
- `eventos.csv`: cada rebase iniciado, completado o abortado (instante y posición).
- `fotos.csv`: posición y velocidad de todos los vehículos cada 5 s (`--fotos`).
- `config.json` (para repetirla) y `resumen.json`.
- Gráficas: diagrama espacio-tiempo, histograma de retrasos, retraso contra velocidad deseada,
  % de vehículos en pelotón y rebases por kilómetro.

![Espacio-tiempo](docs/espacio_tiempo.png)

### Animación

```bash
pip install -e ".[anim]"   # una vez (instala pygame-ce)
trafico animar --modo lleno --vehiculos 70 --trazado pocas --pantalla-completa
```

Arriba se ve la carretera completa y abajo un tramo ampliado que sigue a la sonda. Colores:
**azul** libre, **gris** atrapado detrás de otro, **verde** rebasando y **naranja** la sonda.
Las curvas aparecen sombreadas con su radio y velocidad máxima, y la línea central es amarilla
continua donde no hay visibilidad para rebasar. Abajo, una tabla muestra cuánto tardó cada sonda
y cuánto perdió por el tráfico.

Controles: `Espacio` pausa, `+`/`-` velocidad (×1 a ×100), rueda o `Z`/`X` zoom, flechas para moverse,
`S` seguir a la sonda, `Tab` otra sonda, clic en el mapa para ir a un punto, `R` reiniciar,
`F11` pantalla completa, `Esc` salir.

### Comportamiento realista (fase 3)

Todo esto viene **apagado por defecto** (así los resultados de las fases 1 y 2 se reproducen exactamente).
`--realista` lo enciende con valores razonables, y cada pieza se puede ajustar o barrer por separado:

| Qué | Cómo se activa | Qué hace |
|---|---|---|
| Camiones | `--camiones 0.15` | 16.5 m, aceleran 0.5 m/s². Velocidad deseada con moda en 105 km/h (96 % entre 90 y 110) y 2 % de casos raros: muy lentos (60-90) o con exceso (110-125). |
| Pendientes | `--relieve lomerio` / `montanoso`, o `--param "pendientes=1000:3000:6;..."` (%) | Física con potencia del motor y aire, calibrada con datos (ver abajo). En subida se pierde velocidad poco a poco; en bajada la gravedad empuja y se gana velocidad (autos hasta +10 %, camiones +5 %); los camiones muy cargados usan freno de motor solo en bajadas fuertes (>4 %) y largas (>2 km). |
| Cambio de carril gradual | `--param overtaking.t_lane_change=3` | Cambiar de carril tarda 3 s y mientras tanto ocupa los dos carriles. |
| Rebase en cadena | `--param overtaking.convoy=1` | Se puede seguir a otro que ya rebasa, si el rebase propio es seguro. |
| Visión tapada | `--param overtaking.blocked_view=1` | Detrás de un camión a menos de 3 s no se ve el carril contrario; detrás de un auto a menos de 2 s se ven 500 m. |
| Límites de velocidad | `--param limite=90` o `--param "limites=5000:8000:70"` | Se frena antes de la señal. Con `respetan_limite=0.8`, el 20 % se pasa entre 10 y 30 %. |
| Zonas de no rebase | `--param "zonas_no_rebase=2000:5000"` o `no_rebase_sin_visibilidad=1` | Quien respeta (`respetan_no_rebase`) no empieza un rebase que invada la zona. |
| Tipos de conductor | `--param prudentes=0.2 --param agresivos=0.15` | Prudentes: más margen, más distancia y más diferencia de velocidad para decidir rebasar. Agresivos: lo contrario. |
| Impaciencia | `--param impaciencia=60` | Tras 60 s atrapado, el margen que exige baja poco a poco hasta la mitad. |
| Tiempo de reacción | `--param reaccion=1.0` | Responde con 1 s de retraso, pero se anticipa como en el *Human Driver Model* (estima el hueco y mira a los 3 de delante). Los sustos y el frenado de emergencia son inmediatos. |

En la animación los camiones se ven más largos y con cabina, el cambio de carril se ve, hay un perfil de alturas
arriba, rótulos de "sube/baja x %" y señales circulares de límite de velocidad.

### Campañas

**Más rápido con PyPy**: `bash scripts/instalar_pypy.sh` (una vez) y añade `--rapido` a `trafico campana`. La
simulación corre con PyPy y las gráficas con el Python normal. Da exactamente los mismos resultados y es de 5 a
11 veces más rápido (20 km realista en montaña: 57 s → 5 s por corrida).

```bash
trafico campana --barrer trazado=recta,pocas,muchas --barrer flujo=100,200,300 \
    --velocidades 110 120 130 --semillas 8 --sondas 20 --nucleos 8 --salida results/curvas
trafico graficar results/curvas --x flujo --serie trazado --comparar 120 130
```

- Se puede barrer **cualquier parámetro** (`--barrer nombre=v1,v2,...`, repetible: se combinan todos). Nombres
  cortos: `flujo`, `longitud`, `vehiculos`, `modo`, `trazado`, `relieve`, `camiones`, `sigma`, `v_media`,
  `despeje`, `a_lateral`, `limite`, `prudentes`, `agresivos`, `impaciencia`, `reaccion`, o internos como `idm.T`,
  `overtaking.t_guard` y `overtaking.convoy`. `--realista` también vale para campañas.
- Cada corrida se guarda en cuanto termina: si se corta, el mismo comando **reanuda**. Con más `--semillas`
  o `--velocidades` se amplía una campaña existente sin repetir lo hecho.
- Datos crudos: `corridas.csv` (resumen del tráfico de fondo por corrida), `sondas.csv` (cada sonda) y,
  con `--viajes`, `viajes.csv` (cada vehículo de cada corrida).
- `graficar` genera tablas con media ± IC 95 % y gráficas sin volver a simular.

## Resultados fase 3: modelo realista (20 km, 8 réplicas)

Con `--realista` se suman camiones, cambio de carril de 3 s, rebase en cadena, visión tapada, conductores
distintos con impaciencia y 1 s de reacción. En las 352 corridas de estas campañas hubo **0 colisiones**.

### ¿Qué pieza pesa más? (recta, 200 veh/h, ganancia 120 → 130 km/h)

![Descomposición](docs/descomposicion_realista.png)

| Variante | Ganancia |
|---|---:|
| Modelo simple | 18.0 ± 5.4 s |
| Modelo realista | 8.1 ± 5.0 s |
| Realista **sin visión tapada** | 17.0 ± 2.6 s |
| Simple **+ solo visión tapada** | 1.1 ± 4.6 s |
| Simple + solo cambio de carril de 3 s | 12.0 ± 4.6 s |
| Simple + solo camiones / conductores / reacción / cadena | 17 a 23 s (sin diferencia clara) |

**La visión tapada es la que manda.** Si quien va pegado a otro vehículo no ve lo suficiente del carril
contrario, casi nunca encuentra cuándo rebasar, y la ventaja de ir más rápido desaparece. El cambio de carril
lento le quita una parte (los rebases necesitan más espacio). Las demás piezas mueven el resultado menos que el
margen de error. **Ojo:** la visión tapada usa supuestos sin calibrar (detrás de un camión a menos de 3 s no se
ve nada; detrás de un auto a menos de 2 s se ven 500 m), y en la realidad los conductores se abren un poco para
asomarse. Es el parámetro que más conviene medir con datos reales.
Tabla completa en `docs/descomposicion_realista.csv` (`python scripts/descomponer_realista.py`).

### Camiones y pendientes (modelo realista, 200 veh/h)

Retraso medio de cada vehículo en 20 km:

| Camiones | Plano | Lomerío | Montañoso |
|---:|---:|---:|---:|
| 0 % | 66 s | 68 s | 66 s |
| 10 % | 69 s | 96 s | **178 s** |
| 25 % | 77 s | 126 s | **251 s** |

![Retraso por camiones y relieve](docs/f3_retraso_camiones_relieve.png)

- **En plano los camiones casi no estorban**: el típico va a ~104 km/h, más rápido que el auto promedio.
- **En pendiente sí**: en montaña con 10 % de camiones, cada vehículo pierde en promedio 3 minutos en 20 km.
  En las subidas los camiones pesados se quedan atrás y se forman pelotones que, con tráfico de frente y
  visibilidad limitada, casi no pueden rebasar. En las bajadas recuperan velocidad.
- Sin camiones, el relieve casi no cambia nada: los autos apenas lo notan.
- La ganancia de ir a 130 en vez de 120 sigue siendo pequeña (de −3 a 10 s en 20 km, con intervalos de ±2 a
  ±9 s): estar atrás de un camión en subida cuesta casi lo mismo vayas a la velocidad que vayas. Con relieve,
  además, la ganancia ideal baja de 46 a ~34 s porque en las subidas fuertes un auto no sostiene 130.

### Rebase en cadena (modelo realista, recta)

| Flujo | Uno a uno | En cadena |
|---:|---:|---:|
| 200 veh/h | 6.0 ± 5.1 s | 8.1 ± 5.0 s |
| 350 veh/h | 1.9 ± 1.5 s | 2.8 ± 2.3 s |

Dejar que se vayan varios a la vez ayuda un poco, pero la diferencia no es concluyente. Con visión tapada, el
segundo de la fila pocas veces ve lo suficiente para seguir al primero: el 8 % de los rebases fueron en cadena
a 200 veh/h y el 19 % a 350 veh/h (con más tráfico hay más filas largas esperando el mismo hueco).

### Sustos

En el modelo realista aparecen algunos frenados de emergencia sin choque: de 0.2 a 0.5 por corrida en promedio
(0.15 en plano, 0.5 en lomerío, 0.8 en montaña; 0 con muchas curvas, porque casi no se rebasa). Casi siempre es
alguien que termina un rebase largo y, al volver a su carril, el que viene de frente tiene que frenar: casos
realistas de "se metió justo". En el modelo simple no hay.

## Resultados fase 2: tipo de carretera y distancia

### ¿Y si la carretera tiene curvas? (20 km, 8 réplicas, cada una con un trazado distinto)

Tiempo que se gana al ir a 130 en vez de 120 km/h (media ± IC 95 %; entre paréntesis, lo que se ganaría en vía libre):

| Flujo por sentido | Recta | Pocas curvas | Muchas curvas | Montaña |
|---:|---:|---:|---:|---:|
| 100 veh/h | 32.9 ± 4.8 s (46.2) | 26.1 ± 6.8 s (38.0) | 4.4 ± 1.8 s (7.1) | 0.3 ± 0.1 s (0.3) |
| 200 veh/h | 18.0 ± 5.4 s | 12.3 ± 3.6 s | 1.5 ± 1.2 s | 0.2 ± 0.1 s |
| 300 veh/h | 6.9 ± 3.3 s | 6.2 ± 3.8 s | 0.5 ± 0.5 s | 0.2 ± 0.1 s |
| % de la carretera sin visibilidad para rebasar | 0 % | 19 % | 68 % | 93 % |

![Ganancia por tipo de carretera](docs/ganancia_por_trazado.png)
![Rebases por tipo de carretera](docs/rebases_por_trazado.png)

**Conclusiones**
- **Las curvas quitan la ganancia por dos lados.** Primero, bajan el techo: con muchas curvas casi nunca se llega
  a 120 km/h entre una y otra, así que incluso en vía libre ir a 130 solo ahorra 7 s en 20 km (0.3 s en montaña).
  Segundo, quitan los rebases: a 200 veh/h cada vehículo rebasa en promedio 0.48 veces en recta, 0.32 con pocas
  curvas, 0.01 con muchas y nunca en montaña.
- Con **pocas curvas** suaves la carretera se parece a la recta: se pierde algo de ganancia (12 s frente a 18 s a
  200 veh/h), pero sigue valiendo la pena en tráfico ligero.
- Con **muchas curvas**, ir a 130 en lugar de 120 ahorra 1 o 2 segundos en 20 km: no compensa el riesgo.
- Curioso: con muchas curvas el **tráfico de fondo pierde menos tiempo** (28 s de retraso medio a 200 veh/h,
  frente a 48 s en recta). En las curvas todos van a la misma velocidad, así que importa menos que unos
  quieran ir más rápido que otros.

### ¿Importa la distancia? (carretera recta, 8 réplicas)

| Longitud | 100 veh/h | 200 veh/h | 300 veh/h | Ideal |
|---:|---:|---:|---:|---:|
| 5 km | 7.6 ± 1.1 s | 2.6 ± 1.1 s | 1.3 ± 0.6 s | 11.5 s |
| 10 km | 16.4 ± 2.3 s | 7.7 ± 2.1 s | 3.9 ± 3.5 s | 23.1 s |
| 20 km | 32.9 ± 4.8 s | 18.0 ± 5.4 s | 6.9 ± 3.3 s | 46.2 s |
| 40 km | 66.8 ± 7.9 s | 47.4 ± 5.5 s | 23.0 ± 14.5 s | 92.3 s |

![Ganancia por distancia](docs/ganancia_por_distancia.png)
![Ganancia como % de la ideal](docs/ganancia_pct_por_distancia.png)

**Conclusiones**
- Con tráfico ligero (100 veh/h) se obtiene ~70 % de la ganancia ideal sin importar la distancia.
- Con tráfico moderado (200 veh/h), **en trayectos largos se aprovecha mejor ir rápido**: 23 % de la ganancia
  ideal en 5 km, 39 % en 20 km y 51 % en 40 km. Probablemente porque quedar atrapado detrás de un lento cuesta
  un tiempo parecido en cualquier trayecto, y en uno largo se reparte entre más kilómetros.
- En recorridos cortos con tráfico, ir a 130 en vez de 120 ahorra menos de 10 s.

Tablas completas en `docs/ganancia_trazado.csv` y `docs/ganancia_distancia.csv`.
En las 480 corridas de la fase 2 hubo 0 colisiones (2 vehículos usaron el frenado de emergencia).

## Resultados fase 1: carretera recta de 20 km (8 réplicas)

Tiempo que se gana al ir a 130 km/h en lugar de 120 km/h (media ± IC 95 %):

| Flujo por sentido | Tiempo ganado | Ideal en vía libre |
|---:|---:|---:|
| 100 veh/h | 32.9 ± 4.8 s | 46.2 s |
| 200 veh/h | 18.0 ± 5.4 s | 46.2 s |
| 300 veh/h | 6.9 ± 3.3 s | 46.2 s |
| 450 veh/h | 5.1 ± 4.1 s | 46.2 s |

![Tiempo ganado](docs/ganancia_vs_flujo.png)
![Retraso por tráfico](docs/retraso_vs_flujo.png)
![Tiempo de viaje](docs/tiempo_vs_velocidad.png)

**Conclusiones**
- En vía libre, 130 en vez de 120 ahorra 46 s en 20 km. Con tráfico moderado (200 veh/h por sentido) se ahorran
  unos 18 s, y con 300 veh/h o más, menos de 10 s.
- Quien va más rápido acumula más retraso respecto a su ideal: a 130 se pierde más tiempo que a 120 porque
  alcanza a más vehículos.
- **Sin poder rebasar, la ventaja desaparece** (0.1 s a 200 veh/h): quedas atrapado detrás del más lento.
  Todo el beneficio de ir más rápido viene de los rebases.

### Sensibilidad (200 veh/h por sentido, 6 réplicas)

Ganancia 120 → 130 km/h según el parámetro modificado (ver `docs/sensibilidad.csv`):

| Variante | Ganancia |
|---|---:|
| Base | 18.1 ± 8.0 s |
| Sin rebases | 0.1 s |
| Margen con el contrario 3 s / 10 s (base 6 s) | 19.8 / 16.2 s |
| Solo rebasa si el líder va ≥ 5 m/s más lento | 29.2 s |
| Decide cada 3 s (base 1 s) | 16.0 s |
| Intervalo IDM T = 1.0 s / 2.0 s (base 1.5 s) | 17.5 / 12.0 s |
| Aceleración máxima 1.5 m/s² (base 1.0) | 24.2 s |
| Dispersión de velocidades σ = 15 km/h (base 10) | 6.6 s |

Los intervalos de confianza son anchos (±4 a ±9 s), así que las diferencias pequeñas entre variantes no son
concluyentes. Lo robusto: el orden de magnitud, que la ganancia baja con el flujo y que sin rebases no hay ganancia.
La dispersión de velocidades, el umbral para rebasar y la aceleración son los parámetros que más mueven el resultado.


## Cómo funciona

- **Seguimiento**: modelo IDM (Intelligent Driver Model). Con vía libre el vehículo converge a su velocidad deseada.
- **Rebase**: máquina de estados `SIGUIENDO → REBASANDO → REGRESANDO`. Solo se inicia si, con estimaciones
  pesimistas para todos los demás, el rebase termina al menos 6 s antes de que llegue cualquier vehículo contrario.
  Puede rebasar pelotones de hasta 4 vehículos y abortar si aparece una amenaza. Hay frenado de emergencia como
  red de seguridad. El cambio de carril es instantáneo.
- **Curvas**: en una curva de radio R nadie va a más de √(a_lat·R), con a_lat = 2 m/s² (R = 150 m → 62 km/h;
  R = 400 m → 102 km/h). Se frena antes de entrar (1 m/s²).
- **Visibilidad**: dentro de una curva se ve √(8·R·m) metros del carril contrario, con un despeje lateral
  m = 10 m (R = 300 m → 155 m). Para rebasar, el conductor supone que justo donde se le acaba la visibilidad
  viene un coche de frente a 108 km/h; si la maniobra no cabe, no rebasa. En recta no cambia nada.
- **Pendientes** (solo con relieve, y siempre para camiones): la aceleración no puede pasar de lo que da el
  motor, P/v − g·(i + 0.01) − k·v², con P la potencia en la rueda y k el arrastre del aire. Cada camión sortea su
  relación peso/potencia: mediana 150 lb/hp (unos 9 W/kg en la rueda), calibrada con NCHRP 505 (carreteras de
  dos carriles), más un 15 % de "fulles" muy cargados (330-410 lb/hp, como el vehículo de proyecto de la SCT:
  75.5 t y 430 hp). Así, en una subida de 6 % un camión típico baja poco a poco hasta ~46 km/h (uno ligero
  ~67, un full ~23), y en 500 m de subida todavía va arriba de 70 km/h. Los autos (22 W/kg) casi no lo notan
  hasta 4 %. En bajada, la gravedad empuja y el conductor se deja llevar hasta +10 % (autos) o +5 % (camiones,
  dato de la SCT) de su velocidad deseada, así que se llega "con vuelo" a la siguiente subida. Los camiones muy
  cargados usan freno de motor en bajadas de más de 4 % y más de 2 km: V = 0.9/G m/s (regla de St John:
  65 km/h en 5 %, 46 en 7 %).
  Fuentes: NCHRP Report 505 (TRB, 2003); FHWA-RD-99-171 (TWOPAS); SCT, *Manual de Proyecto Geométrico de
  Carreteras* (2018); Bester y Oncke (2013). El preset montañoso usa tramos de 3 a 6 % (a veces 7 %) de 300 a
  800 m, dentro de las pendientes máximas de la SCT para terreno montañoso.
- **Experimento**: vehículos *sonda* con velocidad deseada fija entran a intervalos regulares tras un periodo de
  calentamiento. Se usan **números aleatorios comunes**: la misma semilla da el mismo tráfico de fondo (y la
  misma carretera) y las mismas horas de entrada, y solo cambia la velocidad de la sonda. Así la diferencia
  entre velocidades se mide sonda con sonda (emparejada) y no se pierde en el ruido.
- **Retraso** = tiempo de viaje − tiempo en vía libre. Con curvas, el tiempo libre es el de un vehículo solo
  por esa misma carretera (frenando en las curvas), así que el retraso mide solo lo que cuesta el tráfico.

## Supuestos y límites

Sin intersecciones ni clima; los conductores no cambian su velocidad deseada durante el viaje; las curvas se
modelan por su radio y la visibilidad con un despeje lateral fijo; las crestas de las lomas no tapan la vista
(solo las curvas y los vehículos de delante); no hay carriles de ascenso para camiones. En el modelo simple
(por defecto) todos los vehículos son autos iguales salvo la velocidad deseada, el cambio de carril es
instantáneo y no hay pendientes ni señales; `--realista` añade camiones, conductores distintos, cambio de carril
lento, rebase en cadena y tiempo de reacción. Los parámetros no están calibrados con datos reales, así que los
resultados son cualitativos. El siguiente paso es importar trazados reales (GPX/OpenStreetMap, con curvas y
pendientes) y calibrar con aforos y velocidades medidas.

## Instalación (en cualquier PC)

```bash
git clone git@github.com:SFBlackMambo/<repo>.git
cd <repo>
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev,anim]"
pytest
```

En Ubuntu/WSL con Python 3.14 puede hacer falta `sudo apt install python3.14-venv` antes de crear el venv.
Para la animación se usa `pygame-ce` (el `pygame` clásico aún no tiene versión para Python 3.14).

## Reproducir los resultados

```bash
# Resultados de la fase 1 (recta, 20 km)
python scripts/run_experiment.py --flows 100 200 300 450 --seeds 8 --workers 8 --probes 20 --out results/main
python scripts/sensitivity.py --flow 200 --seeds 6 --workers 8
# Fase 2: tipo de carretera y distancia
trafico campana --barrer trazado=recta,pocas,muchas,montana --barrer flujo=100,200,300 \
    --velocidades 110 120 130 --semillas 8 --sondas 20 --nucleos 15 --salida results/curvas
trafico campana --barrer longitud=5000,10000,20000,40000 --barrer flujo=100,200,300 \
    --velocidades 120 130 --semillas 8 --sondas 20 --nucleos 15 --salida results/distancia
```

Las campañas de la fase 2 tardan unos 12 minutos con 15 núcleos (unas 5 veces menos con `--rapido`). Todo se guarda en `results/` (ignorada por git).

```bash
# Fase 3: modelo realista
trafico campana --realista --barrer camiones=0,0.1,0.25 --barrer relieve=plano,lomerio,montanoso --flujo 200 \
    --velocidades 120 130 --semillas 8 --sondas 20 --nucleos 15 --salida results/f3_camiones_relieve
trafico campana --realista --barrer flujo=100,200,300 --barrer trazado=recta,pocas,muchas \
    --velocidades 120 130 --semillas 8 --sondas 20 --nucleos 15 --salida results/f3_realista
trafico campana --realista --barrer overtaking.convoy=0,1 --barrer flujo=200,350 \
    --velocidades 120 130 --semillas 8 --sondas 20 --nucleos 15 --salida results/f3_cadena
```

## Estructura

```
src/trafico/  vehicle, fleet (camiones), drivers (conductores), idm (IDM y HDM), road, arrivals,
              overtaking, geometry (curvas, visibilidad, pendientes, señales), slopes, simulation,
              recorder, single, campaign, analysis, plots, plots_explore, animation, menu, cli, config
tests/        pruebas con pytest
scripts/      run_experiment.py, sensitivity.py (fase 1)
docs/         gráficas y tablas de resultados
```

El plan y el seguimiento están en `EPCC_PLAN.md`, `epcc-features.json` y `epcc-progress.md`.
