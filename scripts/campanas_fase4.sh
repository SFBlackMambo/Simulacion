#!/usr/bin/env bash
# Campañas de la fase 4: las de las fases 1 a 3 otra vez, con sondas de 90 a 150 km/h (de 10 en 10),
# viajes guardados y medidas nuevas (combustible, CO2, riesgo), más dos campañas del rebase calibrado.
# Se pueden interrumpir y reanudar: cada campaña retoma las corridas que faltan.
#
#   bash scripts/campanas_fase4.sh            # todas (unas 3,250 corridas; ~1 h con 15 núcleos y PyPy)
#   NUCLEOS=8 bash scripts/campanas_fase4.sh
set -euo pipefail
N=${NUCLEOS:-15}
C="trafico campana --semillas 8 --sondas 20 --nucleos $N --rapido"
V="--velocidades 90 100 110 120 130 140 150"

# Fase 1: recta de 20 km, modelo simple
$C $V --barrer flujo=100,200,300,450 --salida results/f4_flujo
# Fase 2: tipo de carretera y distancia
$C $V --barrer trazado=recta,pocas,muchas,montana --barrer flujo=100,200,300 --salida results/f4_curvas
$C $V --barrer longitud=5000,10000,20000,40000 --barrer flujo=100,200,300 --salida results/f4_distancia
# Fase 3: modelo realista (desde la fase 4 incluye asomarse y la aceptación de hueco con logit)
$C $V --realista --barrer camiones=0,0.1,0.25 --barrer relieve=plano,lomerio,montanoso --flujo 200 \
    --salida results/f4_camiones_relieve
$C $V --realista --barrer flujo=100,200,300 --barrer trazado=recta,pocas,muchas --salida results/f4_realista
$C $V --realista --barrer overtaking.convoy=0,1 --barrer flujo=200,350 --salida results/f4_cadena
# Fase 4: rebase calibrado (B1 logit, B2 asomarse) y carriles de rebase 2+1 (B3)
$C $V --realista --barrer rebase_logit=0,1 --barrer asomarse=0,1 --flujo 200 --salida results/f4_rebase
$C $V --realista --barrer cada_2mas1=0,5000 --barrer flujo=200,350 --salida results/f4_2mas1

for d in results/f4_*; do
    trafico graficar "$d" --mejor > "$d/mejor.txt"
done
echo "Listo."
