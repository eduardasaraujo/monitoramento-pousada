"""Regras que decidem se uma detecção vira alerta: horário, área de interesse e confirmação."""

from collections import deque
from datetime import time as Hora

import cv2
import numpy as np


def ler_hora(texto):
    """Converte "23:30" em um objeto de hora do Python."""
    horas, minutos = map(int, texto.split(":"))
    return Hora(horas, minutos)


def dentro_do_horario(agora, inicio, fim):
    """Diz se `agora` está no período de monitoramento.

    Cuidado com períodos que atravessam a meia-noite, como 23:00 às 06:00:
    nesse caso o fim é MENOR que o início, e a hora vale se for depois do
    início OU antes do fim.
    """
    if inicio <= fim:
        return inicio <= agora < fim
    return agora >= inicio or agora < fim


def pes_da_pessoa(caixa):
    """Ponto da base da caixa (onde estão os pés), que é onde a pessoa está no chão.

    Usar o centro da caixa daria errado: a cabeça de quem está FORA da área
    pode aparecer em cima dela na imagem.
    """
    x1, y1, x2, y2 = caixa
    return ((x1 + x2) / 2, y2)


def area_em_pixels(pontos_normalizados, largura, altura):
    """Converte os pontos da área (salvos de 0 a 1) para pixels da imagem atual.

    Os pontos são guardados de 0 a 1 para continuarem certos se a resolução
    da câmera mudar (ex.: trocar o substream pelo fluxo principal).
    """
    if not pontos_normalizados:
        return None
    pontos = [(x * largura, y * altura) for x, y in pontos_normalizados]
    return np.array(pontos, dtype=np.int32).reshape(-1, 1, 2)


def dentro_da_area(ponto, area):
    """Diz se o ponto está dentro do polígono da área. Sem área definida, vale a imagem toda."""
    if area is None:
        return True
    return cv2.pointPolygonTest(area, (float(ponto[0]), float(ponto[1])), False) >= 0


class Confirmacao:
    """Evita alertas falsos e repetidos.

    - Só confirma se houver pessoa em pelo menos `minimo` dos últimos `janela`
      quadros analisados (uma detecção isolada pode ser um erro do modelo).
    - Depois de um alerta, espera `intervalo_s` segundos antes de permitir
      outro (para não mandar dezenas de mensagens da mesma pessoa).
    """

    def __init__(self, janela, minimo, intervalo_s):
        self.historico = deque(maxlen=janela)  # guarda só os últimos `janela` resultados
        self.minimo = minimo
        self.intervalo_s = intervalo_s
        self.ultimo_alerta = None

    def registrar(self, tem_pessoa, instante):
        """Registra o resultado de um quadro e devolve True se é hora de alertar."""
        self.historico.append(tem_pessoa)
        # O quadro atual também precisa ter pessoa: é ele que vai como foto no alerta
        if not tem_pessoa or sum(self.historico) < self.minimo:
            return False
        if self.ultimo_alerta is not None and instante - self.ultimo_alerta < self.intervalo_s:
            return False
        self.ultimo_alerta = instante
        return True
