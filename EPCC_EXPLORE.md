# Exploration: Proyecto de simulación de tráfico vial

**Fecha**: 2026-11-21 | **Alcance**: Quick | **Estado**: ✅ Completo (proyecto greenfield)

## 1. Foundation
- **Estado del repo**: `/home/luis/simulacion`, `git init` hecho, rama `master`, sin commits, sin remote, vacío.
- **CLAUDE.md**: no existe (ni raíz, ni `.claude/`, ni global).
- **Stack elegido**: Python (3.13.5 instalado). Node v26 también disponible.
- **Dominio**: simulación de tráfico en carreteras. El tipo de modelo aún no está decidido.

## 2. Constraints
- `gh` CLI no instalado.
- SSH a GitHub no configurado (falló la verificación de host key). Método elegido: configurar SSH.
- Usuario git: `SFBlackMambo`.
- El proyecto debe poder clonarse en otra PC, así que debe ser reproducible: `requirements.txt` o `pyproject.toml`, un `.gitignore` y un README con instrucciones.

## 3. Gaps (decisiones para PLAN)
- Tipo de modelo, con tres opciones:
  - Microscópico, por vehículo: Nagel-Schreckenberg (autómata celular) o IDM (car-following).
  - Macroscópico: modelo de flujo/densidad (LWR).
  - Basado en agentes: carriles, adelantamientos, semáforos.
- Salida deseada: gráficas con matplotlib, animación o interfaz web.
- Alcance: carretera de un carril, varios carriles o red de calles.
- Librerías candidatas: numpy, matplotlib, pytest. SimPy y Mesa son opcionales.

## 4. Handoff
- **PLAN**: definir el modelo y el MVP. Recomendación: Nagel-Schreckenberg en carretera circular, con gráfica de diagrama fundamental (flujo vs densidad).
- **CODE**: estructura `src/`, `tests/`, `pyproject.toml`, venv local y pytest.
- **COMMIT**: primer commit, remote SSH y push a GitHub.
