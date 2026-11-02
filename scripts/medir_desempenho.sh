#!/usr/bin/env bash
# Mede o desempenho REAL deste computador (sem simulação) com o vídeo de teste.
# Testa 1 câmera e 3 câmeras simultâneas, com entrada 640 e 416.
# Uso, dentro da pasta do projeto:  scripts/medir_desempenho.sh
# Leva alguns minutos. O resultado fica em saidas/desempenho_<data>.txt

set -euo pipefail
cd "$(dirname "$0")/.."

VIDEO=videos/noturno_cctv_mixkit_31372.mp4
[ -f "$VIDEO" ] || { echo "ERRO: falta $VIDEO (veja o README)"; exit 1; }

NUCLEOS=$(nproc)
# Com 3 processos ao mesmo tempo, cada um usa um terço dos núcleos
THREADS_3=$(( NUCLEOS / 3 > 0 ? NUCLEOS / 3 : 1 ))
SAIDA="saidas/desempenho_$(date +%Y%m%d_%H%M%S).txt"
mkdir -p saidas

# Extrai do resumo do detector só os números que interessam
resumo() {
  grep -oP '(média \K[0-9]+ ms|fator tempo real: \K[0-9.]+x \([^)]*\)|CPU média: \K[0-9]+%|memória pico: \K[0-9]+ MB)' | paste -sd' '
}

{
  echo "===== Máquina ====="
  grep -m1 "model name" /proc/cpuinfo | cut -d: -f2 | sed 's/^ //'
  echo "Núcleos lógicos: $NUCLEOS | RAM: $(free -h | awk '/^Mem/ {print $2}')"
  grep PRETTY_NAME /etc/os-release | cut -d= -f2 | tr -d '"'
  echo "Data: $(date '+%d/%m/%Y %H:%M')"
  echo "Formato de cada linha: inferência média | fator tempo real | CPU | memória pico"

  for IMGSZ in 640 416; do
    echo
    echo "===== imgsz $IMGSZ ====="
    echo "1 câmera:   $(.venv/bin/python src/detectar_pessoas.py --fonte "$VIDEO" --sem-janela --imgsz "$IMGSZ" 2>&1 | resumo)"
    echo "3 câmeras ao mesmo tempo ($THREADS_3 threads cada, OMP_WAIT_POLICY=PASSIVE):"
    for i in 1 2 3; do
      # Os parênteses com & rodam cada câmera em paralelo de verdade.
      # OMP_WAIT_POLICY=PASSIVE: sem isso, em máquinas com muitos núcleos, as threads dos 3
      # processos ficam disputando CPU em espera ativa e tudo fica até 10x mais lento.
      ( export OMP_WAIT_POLICY=PASSIVE; echo "  câmera $i: $(.venv/bin/python src/detectar_pessoas.py --fonte "$VIDEO" --sem-janela --imgsz "$IMGSZ" --threads "$THREADS_3" 2>&1 | resumo)" ) &
    done
    wait
  done
} | tee "$SAIDA"

echo
echo "Resultado salvo em $SAIDA"
echo "Fator tempo real acima de 1.0 = acompanha a câmera ao vivo."
