#!/usr/bin/env bash
# Gera um pacote do projeto para copiar para outro computador (ex.: o notebook da pousada).
# Uso, dentro da pasta do projeto:  scripts/empacotar.sh
#
# Inclui os arquivos do projeto (mesmo os ainda sem commit), o modelo e o vídeo de teste.
# Deixa de fora tudo o que está no .gitignore: .venv, config/.env (senha), saidas/, CLAUDE.md.

set -euo pipefail
cd "$(dirname "$0")/.."

PACOTE="saidas/pacote_pousada.tar.gz"
mkdir -p saidas

{
  # Arquivos do projeto, com e sem commit, exceto os ignorados pelo .gitignore
  git ls-files --cached --others --exclude-standard
  ls modelos/yolo11n.pt videos/noturno_cctv_mixkit_31372.mp4 2>/dev/null || true
} | sort -u | while read -r arquivo; do [ -f "$arquivo" ] && echo "$arquivo"; done \
  | tar -czf "$PACOTE" --transform 's|^|monitoramento-pousada/|' -T -

echo "Pacote criado: $PACOTE ($(du -h "$PACOTE" | cut -f1))"
echo "Conteúdo:"
tar -tzf "$PACOTE" | sed 's/^/  /'
