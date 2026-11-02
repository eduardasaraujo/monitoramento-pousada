"""Envio e registro dos alertas.

Todo alerta é SEMPRE registrado no log e, quando há imagem, a foto é salva em
saidas/alertas/<data>/. Se TELEGRAM_TOKEN e TELEGRAM_CHAT_ID estiverem no
config/.env, o alerta também é enviado pelo Telegram.

Fotos de pessoas são dados pessoais (LGPD): as pastas mais antigas que
`dias_guardar_fotos` são apagadas automaticamente.

O envio pelo Telegram acontece numa thread separada, com uma fila:
- a detecção não para enquanto a mensagem é enviada;
- se faltar internet (ex.: logo depois de ligar o computador, antes do Wi-Fi
  conectar), a mensagem não se perde: é tentada de novo a cada 10 s, na ordem;
- se sair com mais de 1 min de atraso, a mensagem informa a hora em que o fato ocorreu.
"""

import logging
import os
import queue
import shutil
import threading
import time
from datetime import date, datetime, timedelta

import cv2
import requests
from dotenv import load_dotenv

from fonte_video import ARQUIVO_ENV

TENTAR_DE_NOVO_S = 10  # espera entre tentativas quando não há conexão
AVISAR_ATRASO_S = 60   # a partir deste atraso, a mensagem diz quando o fato ocorreu

# Resultados possíveis de uma tentativa de envio
ENVIADO, RECUSADO, SEM_CONEXAO = "enviado", "recusado", "sem_conexao"


class Notificador:
    def __init__(self, pasta_alertas, dias_guardar_fotos):
        load_dotenv(ARQUIVO_ENV)
        self.token = os.getenv("TELEGRAM_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.telegram_ativo = bool(self.token and self.chat_id)
        self.pasta_alertas = pasta_alertas
        self.dias_guardar_fotos = dias_guardar_fotos

        self.fila = queue.Queue()

        if self.telegram_ativo:
            logging.info("Alertas pelo Telegram: ATIVADOS")
            # daemon=True: a thread não impede o programa de terminar
            threading.Thread(target=self._enviar_da_fila, daemon=True).start()
        else:
            logging.warning("Telegram não configurado no config/.env: alertas só no log e em %s", pasta_alertas)

    def enviar(self, texto, imagem=None):
        """Registra o alerta, salva a foto e, se configurado, coloca na fila do Telegram."""
        logging.warning("ALERTA: %s", texto)
        caminho_foto = self._salvar_foto(imagem) if imagem is not None else None
        if self.telegram_ativo:
            self.fila.put((datetime.now(), texto, caminho_foto))

    def aguardar_envios(self, limite_s):
        """Espera a fila esvaziar (até `limite_s` segundos). Usado ao encerrar o programa."""
        fim = time.monotonic() + limite_s
        while self.fila.unfinished_tasks and time.monotonic() < fim:
            time.sleep(0.2)
        if self.fila.unfinished_tasks:
            logging.error("%d alerta(s) não foram enviados pelo Telegram (sem conexão)",
                          self.fila.unfinished_tasks)

    def apagar_fotos_antigas(self):
        """Apaga as pastas de fotos com mais de `dias_guardar_fotos` dias."""
        if not self.pasta_alertas.exists():
            return
        limite = date.today() - timedelta(days=self.dias_guardar_fotos)
        for pasta in self.pasta_alertas.iterdir():
            try:
                dia = date.fromisoformat(pasta.name)
            except ValueError:
                continue  # não é uma pasta de data criada por este programa
            if dia < limite:
                shutil.rmtree(pasta)
                logging.info("Fotos de %s apagadas (mais de %d dias)", pasta.name, self.dias_guardar_fotos)

    def _salvar_foto(self, imagem):
        agora = datetime.now()
        pasta = self.pasta_alertas / agora.strftime("%Y-%m-%d")
        pasta.mkdir(parents=True, exist_ok=True)
        caminho = pasta / agora.strftime("%H%M%S.jpg")
        cv2.imwrite(str(caminho), imagem)
        logging.info("Foto do alerta salva em %s", caminho)
        return caminho

    def _enviar_da_fila(self):
        """Roda na thread de envio: manda as mensagens na ordem, insistindo enquanto não houver conexão."""
        while True:
            momento, texto, caminho_foto = self.fila.get()
            tentativas = 0
            while True:
                tentativas += 1
                if (datetime.now() - momento).total_seconds() >= AVISAR_ATRASO_S:
                    texto_final = f"{texto} (ocorreu às {momento:%H:%M}, enviado com atraso)"
                else:
                    texto_final = texto
                # Só registra a 1ª falha no log, para não encher o arquivo durante uma queda longa
                resultado = self._enviar_telegram(texto_final, caminho_foto, registrar_falha=tentativas == 1)
                if resultado != SEM_CONEXAO:
                    break
                time.sleep(TENTAR_DE_NOVO_S)
            if resultado == ENVIADO and tentativas > 1:
                logging.info("Alerta enviado pelo Telegram depois de %d tentativas", tentativas)
            self.fila.task_done()

    def _enviar_telegram(self, texto, caminho_foto, registrar_falha=True):
        """Uma tentativa de envio. Devolve ENVIADO, RECUSADO (não adianta repetir) ou SEM_CONEXAO."""
        url = f"https://api.telegram.org/bot{self.token}/"
        try:
            if caminho_foto is not None:
                with open(caminho_foto, "rb") as foto:
                    resposta = requests.post(url + "sendPhoto", data={"chat_id": self.chat_id, "caption": texto},
                                             files={"photo": foto}, timeout=20)
            else:
                resposta = requests.post(url + "sendMessage", data={"chat_id": self.chat_id, "text": texto},
                                         timeout=20)
        except requests.RequestException as erro:
            if registrar_falha:
                # A mensagem de erro contém a URL, e a URL contém o token: esconde antes de registrar
                logging.error("Falha ao enviar pelo Telegram (tentando de novo a cada %d s): %s",
                              TENTAR_DE_NOVO_S, str(erro).replace(self.token, "***"))
            return SEM_CONEXAO

        if resposta.ok:
            logging.info("Alerta enviado pelo Telegram")
            return ENVIADO
        # 429 (muitas mensagens) e 5xx (problema no servidor do Telegram) são temporários
        if resposta.status_code == 429 or resposta.status_code >= 500:
            if registrar_falha:
                logging.error("Telegram indisponível (HTTP %d), tentando de novo", resposta.status_code)
            return SEM_CONEXAO
        try:
            motivo = resposta.json().get("description", resposta.status_code)
        except ValueError:
            motivo = resposta.status_code
        logging.error("Telegram recusou o alerta: %s", motivo)
        return RECUSADO
