#!/usr/bin/env bash
# Instala PyPy (Python con compilación al vuelo) en .venv-pypy para correr campañas más rápido.
# Uso: bash scripts/instalar_pypy.sh       Después: trafico campana ... --rapido
set -euo pipefail
VERSION="pypy3.11-v7.3.23-linux64"
SHA256="16f9f56e82d1f4ec95a324c1a8cacfd78afc7f0656c0a809a18725ef4391453a"  # de https://pypy.org/checksums.html
RAIZ="$(cd "$(dirname "$0")/.." && pwd)"
DESTINO="${HOME}/.local/opt"
DESCARGA="$(mktemp -d)"
mkdir -p "$DESTINO"
if [ ! -x "$DESTINO/$VERSION/bin/pypy3" ]; then
  echo "Descargando $VERSION..."
  curl -sL -o "$DESCARGA/$VERSION.tar.bz2" "https://downloads.python.org/pypy/$VERSION.tar.bz2"
  echo "$SHA256  $DESCARGA/$VERSION.tar.bz2" | sha256sum -c -
  python3 -c "import sys, tarfile; tarfile.open(sys.argv[1]).extractall(sys.argv[2], filter='tar')" \
    "$DESCARGA/$VERSION.tar.bz2" "$DESTINO"
fi
rm -rf "$DESCARGA"
"$DESTINO/$VERSION/bin/pypy3" -m venv "$RAIZ/.venv-pypy"
"$RAIZ/.venv-pypy/bin/pip" install -q numpy
"$RAIZ/.venv-pypy/bin/pip" install -q --no-deps -e "$RAIZ"
echo "Listo: $RAIZ/.venv-pypy. Usa 'trafico campana ... --rapido'."
