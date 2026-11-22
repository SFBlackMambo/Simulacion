# Simulación de tráfico en carretera de dos carriles

¿Cuánto tiempo se ahorra de verdad al ir a 130 km/h en vez de 120 km/h?

Simulación por pasos de tiempo de una carretera recta con **un carril por sentido**.
Cada vehículo tiene una **velocidad deseada fija** y busca mantenerla. Si alcanza a uno
más lento, frena y lo sigue; solo puede **rebasar invadiendo el carril contrario** cuando
hay un hueco seguro frente al tráfico que viene de frente. Ahí se pierde el tiempo.

## Resultados (20 km, tráfico aleatorio, 8 réplicas)

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
- **Tráfico**: llegadas de Poisson por cada extremo, con velocidades deseadas Normal(100, 10) km/h truncada a 60-140.
- **Experimento**: vehículos *sonda* con velocidad deseada fija entran a intervalos regulares tras un periodo de
  calentamiento. Se usan **números aleatorios comunes**: la misma semilla da el mismo tráfico de fondo y las
  mismas horas de entrada, y solo cambia la velocidad de la sonda. Así la diferencia 120 vs 130 se mide sonda
  con sonda (emparejada) y no se pierde en el ruido.

## Supuestos y límites

Carretera recta y plana, sin intersecciones ni clima; vehículos idénticos salvo la velocidad deseada; los conductores
no cambian su velocidad deseada; cambio de carril instantáneo; sin límites de velocidad ni camiones.
Los parámetros no están calibrados con datos reales, así que los resultados son cualitativos.

## Instalación (en cualquier PC)

```bash
git clone git@github.com:SFBlackMambo/<repo>.git
cd <repo>
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pytest
```

## Reproducir los resultados

```bash
python scripts/run_experiment.py --flows 100 200 300 450 --seeds 8 --workers 8 --probes 20 --out results/main
python scripts/sensitivity.py --flow 200 --seeds 6 --workers 8
```

Tarda unos 10 minutos con 8 a 12 núcleos. Genera CSV y PNG en `results/` (ignorada por git).

## Estructura

```
src/trafico/  vehicle, idm, road, arrivals, overtaking, simulation, experiments, stats, plots
tests/        pruebas con pytest
scripts/      run_experiment.py, sensitivity.py
docs/         gráficas y tablas de resultados
```

El plan y el seguimiento están en `EPCC_PLAN.md`, `epcc-features.json` y `epcc-progress.md`.
