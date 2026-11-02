#!/usr/bin/env bash
# Faz o monitoramento iniciar sozinho quando o computador liga e reiniciar se travar.
# Cria um serviço do systemd do usuário (não precisa de sudo).
#
# Uso, dentro da pasta do projeto:
#   scripts/instalar_servico.sh            instala e inicia o serviço
#   scripts/instalar_servico.sh --mostrar  só mostra o serviço, sem instalar
#   scripts/instalar_servico.sh --remover  para e remove o serviço

set -euo pipefail
cd "$(dirname "$0")/.."
PASTA="$PWD"
NOME="monitoramento-pousada"
ARQUIVO="$HOME/.config/systemd/user/$NOME.service"

SERVICO="[Unit]
Description=Monitoramento noturno da pousada (detecção de pessoas)

[Service]
WorkingDirectory=$PASTA
ExecStart=$PASTA/.venv/bin/python $PASTA/src/monitorar.py
# Se o programa cair, reinicia depois de 10 s
Restart=always
RestartSec=10
# Ctrl+C (SIGINT) faz o programa encerrar de forma organizada
KillSignal=SIGINT
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=default.target"

case "${1:-}" in
  --mostrar)
    echo "$SERVICO"
    exit 0 ;;
  --remover)
    systemctl --user disable --now "$NOME" || true
    rm -f "$ARQUIVO"
    systemctl --user daemon-reload
    echo "Serviço removido."
    exit 0 ;;
esac

[ -f config/.env ] || { echo "ERRO: falta config/.env (rode scripts/instalar.sh)"; exit 1; }

mkdir -p "$(dirname "$ARQUIVO")"
echo "$SERVICO" > "$ARQUIVO"
systemctl --user daemon-reload
systemctl --user enable --now "$NOME"

# "Linger": o serviço roda mesmo sem ninguém ter feito login no computador
loginctl enable-linger "$USER"

echo
echo "Serviço instalado e iniciado."
echo "  Ver se está rodando:  systemctl --user status $NOME"
echo "  Acompanhar o log:     tail -f saidas/monitoramento.log"
echo "  Reiniciar (após mudar a configuração): systemctl --user restart $NOME"
echo
echo "IMPORTANTE, para o notebook não dormir (rode uma vez):"
echo "  1. Não suspender ao fechar a tampa:"
echo "     sudo sed -i 's/^#\\?HandleLidSwitch=.*/HandleLidSwitch=ignore/' /etc/systemd/logind.conf"
echo "     sudo sed -i 's/^#\\?HandleLidSwitchExternalPower=.*/HandleLidSwitchExternalPower=ignore/' /etc/systemd/logind.conf"
echo "  2. Não suspender por inatividade (Ubuntu/Pop!_OS com GNOME):"
echo "     gsettings set org.gnome.settings-daemon.plugins.power sleep-inactive-ac-type 'nothing'"
echo "  3. Reinicie o computador e confira se o serviço voltou sozinho."
