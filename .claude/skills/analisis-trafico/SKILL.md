---
name: analisis-trafico
description: Analiza los datos del simulador de tráfico (campañas en results/, viajes.csv, sondas.csv, corridas.csv, trayectorias) para responder preguntas, hacer gráficas y sacar conclusiones defendibles. Úsala cuando el usuario pida analizar, comparar, graficar, explicar o sacar conclusiones de resultados de simulación, o preguntar "qué pasa si" con datos ya corridos.
---

# Análisis de datos del simulador de tráfico

Guía para responder preguntas con los datos que ya existen, sin volver a simular salvo que haga falta, y con
conclusiones que aguanten la incertidumbre. El método va primero; las herramientas después.

## 1. Ubica los datos

Cada campaña (`results/<nombre>/`) tiene:

| Archivo | Una fila por | Para qué |
|---|---|---|
| `campana.json` | — | configuración base, `barridos` (parámetros y valores), velocidades, semillas |
| `corridas.csv` | corrida (combo × v_sonda × semilla) | resumen del tráfico de fondo, choques, `veh_km`, `v_media_fondo` |
| `sondas.csv` | sonda | tiempo, retraso, litros, CO2, riesgo del simulador de cada sonda |
| `viajes.csv` | vehículo de cada corrida | todo el detalle (clase, conductor, headway, TTC, litros...) |
| `trayectorias/` (opcional) | vehículo × instante | posición, carril, líder, seguidor, hueco (tipo NGSIM) |
| `graficas/mejor_*.csv` | combo × velocidad | lo que calcula `trafico graficar DIR --mejor` (ganancias, costos, riesgo) |

Las columnas están en `docs/datos.md`, que es la fuente de verdad: léelo antes de usar una columna que no
conozcas. Las campañas de la fase 4 son `results/f4_*`, y sus resúmenes están en `docs/f4_*_resumen.csv`. Las
claves de unión son `combo`, `v_sonda` y `semilla`; las columnas de los parámetros barridos llevan su nombre
interno (`flow_per_hour`, `trucks.share`...).

## 2. Reglas de estadística (no negociables)

1. **La réplica es la semilla, no el vehículo ni la sonda.** Los vehículos de una misma corrida comparten
   tráfico y no son independientes. Promedia primero por (combo, v_sonda, semilla) y calcula el IC 95 % entre
   esas medias (`trafico.stats.mean_ci`, t de Student). Con 8 semillas, los IC son anchos: repórtalos siempre.
2. **Compara velocidades emparejando por semilla.** Hay números aleatorios comunes: misma semilla = mismo
   tráfico de fondo y mismas horas de entrada. La diferencia entre dos velocidades se calcula semilla por
   semilla (`scripts/comparar.py`). Es mucho más precisa que restar dos medias.
3. **Filtra lo que corresponde.** El fondo con `sonda=0` y `viaje_completo=1` (en el modo `lleno` hay viajes
   parciales); las sondas con `sonda=1`. `v_media_kmh` y `l_100km` vienen vacíos si el viaje fue parcial.
4. **Los eventos raros van por exposición.** Choques y sustos: tasa por millón de veh-km (`veh_km` en
   corridas.csv) y cuántos eventos hay. Con 3 choques no hay curva: dilo así.
5. **Separa lo simulado de lo supuesto.** Tiempo, velocidades, rebases, TTC y litros salen del modelo. Los
   precios (MXN), los exponentes de riesgo, Kloeden y el logit son supuestos (`docs/datos.md`). Si una
   conclusión depende de un precio, muestra cómo cambia con otro (`--precio valor_tiempo_h=...`) o usa el
   valor de la hora de equilibrio (`vtt_equilibrio`), que no depende del valor del tiempo.
6. **No sobreinterpretes diferencias dentro del IC.** "No se distingue" es un resultado válido.
7. **El modelo no está calibrado con datos reales**: las conclusiones son cualitativas (orden de magnitud,
   tendencias, qué pesa más). Dilo al final de cada análisis.

## 3. Herramientas (de la más directa a la más flexible)

- **Lo que ya está calculado**: `trafico graficar DIR --mejor` (tablas `mejor_*.csv` y gráficas),
  `trafico graficar DIR --x ... --serie ... --comparar 120 130`, `python scripts/resumen_fase4.py`.
- **Comparar dos velocidades emparejadas**:
  `python .claude/skills/analisis-trafico/scripts/comparar.py results/f4_flujo --a 100 --b 130 --campos tiempo_viaje litros`
- **Resumir viajes.csv por grupos** (con la semilla como réplica, en streaming):
  `python .claude/skills/analisis-trafico/scripts/resumir_viajes.py results/f4_camiones_relieve --campo retraso --por clase relieve --filtro sonda=0 viaje_completo=1 v_sonda=130`
- **En Python**: `from trafico.analysis import Campaign` (combos, sondas, corridas ya leídos);
  `from trafico.mejor import tablas` (filas por velocidad con riesgo y costos); `from trafico import costos`
  (`balance`, `con_precios`, `riesgo_nilsson`, `riesgo_kloeden`).
- **Con DuckDB** (si el usuario instaló duckdb-skills o el CLI `duckdb`), para preguntas ad hoc sobre los CSV
  grandes sin cargarlos en memoria:
  ```sql
  -- retraso medio del fondo por clase y conductor, primero por corrida
  WITH c AS (
    SELECT combo, v_sonda, semilla, clase, conductor, avg(retraso) AS r
    FROM 'results/f4_realista/viajes.csv'
    WHERE sonda = 0 AND viaje_completo = 1
    GROUP BY ALL)
  SELECT clase, conductor, avg(r) AS media, stddev_samp(r) / sqrt(count(*)) * 2.36 AS ic95, count(*) AS corridas
  FROM c GROUP BY ALL ORDER BY ALL;
  ```
  (2.36 = t de Student con 7 grados de libertad; ajústalo si hay otro número de semillas.) Las mismas reglas
  de la sección 2 aplican también en SQL.
- **Si falta un dato**, propón la campaña mínima que lo responde (pocas combinaciones, `--rapido`, se reanuda)
  y di cuánto tardaría antes de correrla.

## 4. Gráficas

Antes de la primera línea de código de una gráfica, carga la skill `dataviz` y sigue su procedimiento. En
este proyecto ya están resueltas sus decisiones:

- Estilo y paleta: `trafico.plots._ax` (superficie, tinta, rejilla) y `trafico.analysis.SERIES8` (categórica
  validada, en orden fijo, sin repetir colores). Guardar con `trafico.analysis._guardar_arriba`, que pone la
  leyenda arriba.
- Un solo eje y. Con más de ~4 series, gráficas pequeñas (una por valor de otro parámetro), como hace
  `graficar --mejor`. Barras de error = IC 95 %. Etiquetas directas al final de la línea con ≤ 4 series.
- Siempre una tabla (CSV) al lado de cada gráfica. Mira la imagen antes de darla por buena (títulos cortados,
  leyendas que tapan datos).
- Lo publicable va a `docs/` (los PNG de `results/` los ignora git).

## 5. Cómo entregar un análisis

1. **La pregunta**, en una línea.
2. **Datos usados**: campaña, filtros, cuántas corridas y semillas.
3. **Resultado**: números con IC 95 % (y emparejados si se comparan velocidades), con su gráfica o tabla.
4. **Qué significa**, en lenguaje llano, y qué decisión apoya.
5. **Límites**: qué supuestos lo mueven y qué no se puede concluir.
