"""Abertura da fonte de vídeo: arquivo local ou câmera do DVR via RTSP.

As credenciais do DVR NUNCA ficam no código. Elas são lidas do arquivo
config/.env (que não deve ir para o repositório). Veja config/.env.example.
"""

import os
from pathlib import Path
from urllib.parse import quote

import cv2
from dotenv import load_dotenv

PASTA_PROJETO = Path(__file__).resolve().parent.parent
ARQUIVO_ENV = PASTA_PROJETO / "config" / ".env"


def montar_url_rtsp():
    """Monta a URL RTSP do DVR Intelbras a partir das variáveis do config/.env.

    Formato usado por DVRs Intelbras (mesmo padrão da Dahua):
        rtsp://usuario:senha@ip:porta/cam/realmonitor?channel=N&subtype=S
    subtype=0 é o fluxo principal (alta resolução) e subtype=1 é o substream
    (baixa resolução), que é o recomendado para economizar processamento.
    """
    load_dotenv(ARQUIVO_ENV)

    obrigatorias = ["DVR_IP", "DVR_USUARIO", "DVR_SENHA"]
    faltando = [nome for nome in obrigatorias if not os.getenv(nome)]
    if faltando:
        raise ValueError(
            f"Variáveis ausentes em {ARQUIVO_ENV}: {', '.join(faltando)}. "
            "Copie config/.env.example para config/.env e preencha."
        )

    ip = os.getenv("DVR_IP")
    porta = os.getenv("DVR_PORTA", "554")
    canal = os.getenv("DVR_CANAL", "1")
    subtipo = os.getenv("DVR_SUBTIPO", "1")
    # quote() protege senhas com caracteres especiais como @, : ou /
    usuario = quote(os.getenv("DVR_USUARIO"), safe="")
    senha = quote(os.getenv("DVR_SENHA"), safe="")

    return f"rtsp://{usuario}:{senha}@{ip}:{porta}/cam/realmonitor?channel={canal}&subtype={subtipo}"


def ocultar_senha(url):
    """Troca a senha por *** para a URL poder aparecer no log sem vazar credenciais."""
    if "@" not in url or "://" not in url:
        return url
    protocolo, resto = url.split("://", 1)
    credenciais, endereco = resto.split("@", 1)
    usuario = credenciais.split(":", 1)[0]
    return f"{protocolo}://{usuario}:***@{endereco}"


def abrir_fonte(fonte):
    """Abre a fonte de vídeo e devolve (captura, descricao_para_log).

    fonte pode ser:
      - o caminho de um arquivo de vídeo;
      - a palavra "rtsp", para usar a câmera configurada no config/.env.
    """
    if fonte == "rtsp":
        url = montar_url_rtsp()
        # TCP é mais estável que UDP em redes Wi-Fi ou congestionadas.
        # Precisa ser definido ANTES de criar o VideoCapture.
        os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp"
        captura = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        descricao = ocultar_senha(url)
    else:
        caminho = Path(fonte)
        if not caminho.is_file():
            raise FileNotFoundError(f"Arquivo de vídeo não encontrado: {caminho}")
        captura = cv2.VideoCapture(str(caminho))
        descricao = str(caminho)

    if not captura.isOpened():
        raise ConnectionError(f"Não foi possível abrir a fonte de vídeo: {descricao}")

    return captura, descricao
