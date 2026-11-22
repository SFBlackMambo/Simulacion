# Simulación de tráfico

Simulación de vehículos con velocidad deseada fija en una carretera de un carril
por sentido. Para rebasar hay que invadir el carril contrario cuando esté libre.
El objetivo es medir cuánto tiempo se gana al ir a 130 km/h en vez de 120 km/h.

Ver `EPCC_PLAN.md` para el plan completo.

## Instalación (en cualquier PC)

```bash
git clone git@github.com:SFBlackMambo/<repo>.git
cd <repo>
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Pruebas

```bash
pytest
```

## Estructura

```
src/trafico/   código de la simulación
tests/         pruebas con pytest
scripts/       scripts para ejecutar experimentos y graficar
```
