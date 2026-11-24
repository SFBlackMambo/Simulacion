#!/usr/bin/env bash
# Arma el sitio web (GitHub Pages) en _site/: la página, el paquete del simulador (para Pyodide) y las gráficas.
#
#   bash scripts/sitio.sh            # arma _site/
#   bash scripts/sitio.sh --servir   # y lo sirve en http://localhost:8000 para probarlo
set -euo pipefail
cd "$(dirname "$0")/.."
rm -rf _site
mkdir -p _site/trafico _site/img
cp site/*.html site/*.js site/*.css _site/
# El simulador corre en el navegador: solo hace falta el código Python (sin pruebas ni gráficas de matplotlib)
cp src/trafico/*.py _site/trafico/
python3 -c "import json, pathlib; print(json.dumps(sorted(p.name for p in pathlib.Path('_site/trafico').glob('*.py'))))" \
    > _site/trafico/archivos.json
cp docs/f4_*.png docs/animacion.png _site/img/
touch _site/.nojekyll
echo "Sitio en _site/ ($(du -sh _site | cut -f1))"
if [[ "${1:-}" == "--servir" ]]; then
    cd _site && python3 -m http.server 8000
fi
