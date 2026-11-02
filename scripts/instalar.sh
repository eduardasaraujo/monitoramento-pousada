#!/usr/bin/env bash
# Instala o projeto num computador Linux novo (ex.: o notebook da pousada).
# Uso, dentro da pasta do projeto:  scripts/instalar.sh
#
# Não usa sudo. Se faltar algo do sistema, mostra o comando para você rodar.

set -euo pipefail
cd "$(dirname "$0")/.."

echo ">> Verificando o Python"
if ! command -v python3 >/dev/null; then
  echo "ERRO: python3 não encontrado. Rode: sudo apt install python3"; exit 1
fi
python3 -c 'import sys; assert sys.version_info >= (3, 10), sys.version' \
  || { echo "ERRO: é preciso Python 3.10 ou mais novo"; exit 1; }
python3 --version

# No Ubuntu/Pop!_OS o módulo venv vem num pacote separado
if ! python3 -c 'import venv, ensurepip' 2>/dev/null; then
  echo "ERRO: falta o pacote do ambiente virtual. Rode:"
  echo "  sudo apt install python3-venv"
  exit 1
fi

echo ">> Criando o ambiente virtual (.venv)"
[ -d .venv ] || python3 -m venv .venv
.venv/bin/python -m pip install --quiet --upgrade pip

echo ">> Instalando as dependências (pode levar alguns minutos)"
.venv/bin/python -m pip install --quiet -r requirements.txt

echo ">> Configurando a Ultralytics dentro do projeto e desativando o envio de estatísticas"
export YOLO_CONFIG_DIR="$PWD/config/ultralytics"
.venv/bin/python -c "from ultralytics import settings; settings.update({'sync': False})" >/dev/null

echo ">> Baixando o modelo YOLO (se ainda não existir)"
mkdir -p modelos videos saidas
.venv/bin/python -c "from ultralytics import YOLO; YOLO('modelos/yolo11n.pt')" >/dev/null

if [ ! -f config/.env ]; then
  cp config/.env.example config/.env
  chmod 600 config/.env  # só o seu usuário consegue ler a senha do DVR
  echo ">> Criado config/.env: PREENCHA com o IP, usuário e senha do DVR"
fi

echo ">> Conferindo a instalação"
.venv/bin/python -c "import torch, cv2, ultralytics; print('torch', torch.__version__, '| opencv', cv2.__version__, '| ultralytics', ultralytics.__version__)"

echo
echo "Instalação concluída."
[ -f videos/noturno_cctv_mixkit_31372.mp4 ] || echo "Vídeo de teste ausente. Baixe com:
  curl -L -o videos/noturno_cctv_mixkit_31372.mp4 https://assets.mixkit.co/videos/31372/31372-720.mp4"
