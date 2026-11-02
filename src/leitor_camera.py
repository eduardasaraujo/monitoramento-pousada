"""Leitura contínua da câmera numa thread separada.

Por que uma thread? A câmera envia ~25 quadros por segundo, mas o YOLO analisa
só ~5. Se lêssemos a câmera apenas quando o YOLO pede, os quadros não lidos se
acumulariam e o sistema passaria a analisar imagens de segundos (ou minutos)
atrás. Aqui, a thread lê tudo o tempo todo e guarda só o quadro MAIS RECENTE.

A thread também reconecta sozinha se a câmera cair.
"""

import logging
import threading
import time

import cv2

from fonte_video import abrir_fonte


class LeitorCamera:
    def __init__(self, fonte, canal=None, subtipo=None):
        self.fonte = fonte
        self.canal = canal
        self.subtipo = subtipo
        self.ultimo_quadro_em = None  # instante (time.monotonic) do último quadro recebido
        self._quadro = None
        self._numero = 0  # conta os quadros recebidos, para saber se chegou um quadro novo
        self._trava = threading.Lock()  # impede ler o quadro enquanto a thread o substitui
        self._parar = threading.Event()
        self._thread = threading.Thread(target=self._executar, daemon=True)

    def iniciar(self):
        self._thread.start()

    def parar(self):
        self._parar.set()
        self._thread.join(timeout=15)

    def ultimo_quadro(self):
        """Devolve (numero, quadro) do quadro mais recente; quadro é None se ainda não chegou nenhum."""
        with self._trava:
            return self._numero, self._quadro

    def _executar(self):
        espera = 2  # segundos até tentar reconectar; dobra a cada falha, até 60
        while not self._parar.is_set():
            try:
                captura, descricao = abrir_fonte(self.fonte, self.canal, self.subtipo)
            except ConnectionError as erro:
                logging.error("Câmera indisponível: %s. Nova tentativa em %d s", erro, espera)
                self._parar.wait(espera)
                espera = min(espera * 2, 60)
                continue

            logging.info("Câmera conectada: %s", descricao)
            espera = 2
            self._ler_ate_falhar(captura)
            captura.release()

    def _ler_ate_falhar(self, captura):
        e_arquivo = self.fonte != "rtsp"
        fps = captura.get(cv2.CAP_PROP_FPS)
        intervalo_arquivo = 1 / fps if 0 < fps <= 120 else 1 / 25

        while not self._parar.is_set():
            ok, quadro = captura.read()
            if not ok:
                if e_arquivo:
                    # Arquivo de teste: ao terminar, recomeça, imitando uma câmera que nunca para
                    captura.set(cv2.CAP_PROP_POS_FRAMES, 0)
                    ok, quadro = captura.read()
                if not ok:
                    logging.warning("A câmera parou de enviar imagens; reconectando")
                    return

            with self._trava:
                self._quadro = quadro
                self._numero += 1
                self.ultimo_quadro_em = time.monotonic()

            if e_arquivo:
                # Um arquivo seria lido o mais rápido possível; isto o faz ir no ritmo de uma câmera real
                time.sleep(intervalo_arquivo)
