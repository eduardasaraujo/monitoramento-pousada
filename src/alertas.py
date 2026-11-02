"""Envio e registro dos alertas.

Todo alerta é SEMPRE registrado no log e, quando há imagem, a foto é salva em
saidas/alertas/<data>/. Se TELEGRAM_TOKEN e TELEGRAM_CHAT_ID estiverem no
config/.env, o alerta também é enviado pelo Telegram.

Fotos de pessoas são dados pessoais (LGPD): as pastas mais antigas que
`dias_guardar_fotos` são apagadas automaticamente.
"""

import logging
import os
import shutil
from datetime import date, datetime, timedelta

import cv2
import requests
from dotenv import load_dotenv

from fonte_video import ARQUIVO_ENV


class Notificador:
    def __init__(self, pasta_alertas, dias_guardar_fotos):
        load_dotenv(ARQUIVO_ENV)
        self.token = os.getenv("TELEGRAM_TOKEN", "")
        self.chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.telegram_ativo = bool(self.token and self.chat_id)
        self.pasta_alertas = pasta_alertas
        self.dias_guardar_fotos = dias_guardar_fotos

        if self.telegram_ativo:
            logging.info("Alertas pelo Telegram: ATIVADOS")
        else:
            logging.warning("Telegram não configurado no config/.env: alertas só no log e em %s", pasta_alertas)

    def enviar(self, texto, imagem=None):
        """Registra o alerta, salva a foto e, se configurado, envia pelo Telegram."""
        logging.warning("ALERTA: %s", texto)
        caminho_foto = self._salvar_foto(imagem) if imagem is not None else None
        if self.telegram_ativo:
            self._enviar_telegram(texto, caminho_foto)

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

    def _enviar_telegram(self, texto, caminho_foto):
        url = f"https://api.telegram.org/bot{self.token}/"
        try:
            if caminho_foto is not None:
                with open(caminho_foto, "rb") as foto:
                    resposta = requests.post(url + "sendPhoto", data={"chat_id": self.chat_id, "caption": texto},
                                             files={"photo": foto}, timeout=20)
            else:
                resposta = requests.post(url + "sendMessage", data={"chat_id": self.chat_id, "text": texto},
                                         timeout=20)
            if resposta.ok:
                logging.info("Alerta enviado pelo Telegram")
            else:
                logging.error("Telegram recusou o alerta: %s", resposta.json().get("description", resposta.status_code))
        except requests.RequestException as erro:
            # A mensagem de erro contém a URL, e a URL contém o token: esconde antes de registrar
            logging.error("Falha ao enviar pelo Telegram: %s", str(erro).replace(self.token, "***"))
