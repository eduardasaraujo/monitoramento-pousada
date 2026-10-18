#!/usr/bin/env bash
# Executa o detector limitando CPU e memória para APROXIMAR o notebook da pousada
# (Intel Core i7 de 4ª geração, 8 GB de RAM, sem GPU) numa máquina mais potente.
#
# Uso:  scripts/simular_notebook_pousada.sh [argumentos do detectar_pessoas.py]
#
# Perfil conservador, equivalente a um i7-4500U/4510U (2 núcleos / 4 threads),
# o i7 de 4ª geração mais fraco comum em notebooks. Se o da pousada for um
# i7-4700HQ/MQ (4 núcleos), o desempenho real tende a ser melhor que o simulado.
#
# Como funciona (Linux com systemd, sem sudo):
#   - taskset prende o processo a 4 núcleos lógicos (2 físicos);
#   - CPUQuota=200% limita o tempo de CPU, compensando que cada núcleo desta
#     máquina é mais rápido que um núcleo Haswell (proporção estimada pelo PassMark);
#   - MemoryMax=3G limita a RAM, já que o Windows do notebook ocupa parte dos 8 GB.
# É uma APROXIMAÇÃO. O teste definitivo deve ser feito no notebook real.

set -euo pipefail

PASTA="$(cd "$(dirname "$0")/.." && pwd)"
echo ">> Simulando notebook da pousada: 4 núcleos lógicos, CPUQuota=200%, MemoryMax=3G"

exec systemd-run --user --scope --quiet -p CPUQuota=200% -p MemoryMax=3G \
  taskset -c 0-3 \
  "$PASTA/.venv/bin/python" "$PASTA/src/detectar_pessoas.py" "$@"
