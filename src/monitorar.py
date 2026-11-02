"""Sistema de monitoramento de UMA câmera da pousada.

Fluxo:
    fora do horário  -> câmera desligada, nada é processado
    dentro do horário -> lê a câmera -> YOLO detecta pessoas -> mantém só as que
    têm os pés dentro da área de interesse -> confirmação em vários quadros
    -> alerta (log + foto + Telegram, se configurado)

Também avisa quando o monitoramento começa e termina, e quando a câmera fica
sem imagem: se a mensagem de início não chegar, a equipe sabe que há um problema.

Uso:
    python src/monitorar.py                                    # uso normal (config/monitoramento.yaml)
    python src/monitorar.py --ignorar-horario --janela         # teste de dia, vendo a imagem
    python src/monitorar.py --fonte videos/x.mp4 --ignorar-horario --janela   # teste com vídeo gravado
"""

import argparse
import logging
import os
import time
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent.parent
os.environ.setdefault("YOLO_CONFIG_DIR", str(PASTA_PROJETO / "config" / "ultralytics"))

import cv2  # noqa: E402
import torch  # noqa: E402
import yaml  # noqa: E402
from ultralytics import YOLO  # noqa: E402

from alertas import Notificador  # noqa: E402
from desenhar_area import carregar_area  # noqa: E402
from fonte_video import montar_url_rtsp  # noqa: E402
from leitor_camera import LeitorCamera  # noqa: E402
from regras import (Confirmacao, area_em_pixels, dentro_da_area,  # noqa: E402
                    dentro_do_horario, ler_hora, pes_da_pessoa)

CLASSE_PESSOA = 0
TITULO_JANELA = "Monitoramento (q para sair)"


def ler_argumentos():
    parser = argparse.ArgumentParser(description="Monitora uma câmera e alerta quando houver pessoa na área e no horário.")
    parser.add_argument("--config", default=str(PASTA_PROJETO / "config" / "monitoramento.yaml"))
    parser.add_argument("--fonte", default="rtsp",
                        help='"rtsp" (padrão, câmera do config) ou um arquivo de vídeo para teste')
    parser.add_argument("--ignorar-horario", action="store_true", help="Monitora a qualquer hora (para testes)")
    parser.add_argument("--janela", action="store_true", help="Mostra a imagem com detecções e área")
    parser.add_argument("--testar-alerta", action="store_true",
                        help="Só envia uma mensagem de teste (para conferir o Telegram) e encerra")
    return parser.parse_args()


def configurar_log():
    pasta = PASTA_PROJETO / "saidas"
    pasta.mkdir(exist_ok=True)
    # Rotativo: quando chega a 5 MB, começa outro arquivo (guarda os 5 últimos)
    arquivo = RotatingFileHandler(pasta / "monitoramento.log", maxBytes=5_000_000, backupCount=5, encoding="utf-8")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        handlers=[logging.StreamHandler(), arquivo])


def desenhar_cena(quadro, area, caixas_dentro, caixas_fora):
    """Desenha a área (amarelo), pessoas dentro dela (vermelho) e fora dela (cinza)."""
    if area is not None:
        cv2.polylines(quadro, [area], True, (0, 200, 255), 2)
    for caixas, cor in ((caixas_fora, (160, 160, 160)), (caixas_dentro, (0, 0, 255))):
        for x1, y1, x2, y2 in caixas:
            cv2.rectangle(quadro, (int(x1), int(y1)), (int(x2), int(y2)), cor, 2)
            cv2.circle(quadro, (int((x1 + x2) / 2), int(y2)), 5, cor, -1)  # ponto dos pés
    return quadro


class Monitor:
    def __init__(self, config, args):
        self.config = config
        self.args = args
        self.ambiente = config["ambiente"]
        self.inicio = ler_hora(config["horario"]["inicio"])
        self.fim = ler_hora(config["horario"]["fim"])
        det = config["deteccao"]
        self.conf = det["conf"]
        self.imgsz = det["imgsz"]
        self.intervalo_analise = 1 / det["fps_alvo"]
        torch.set_num_threads(det["threads"])

        logging.info("Carregando modelo %s", det["modelo"])
        self.modelo = YOLO(str(PASTA_PROJETO / det["modelo"]))

        conf_alerta = config["confirmacao"]
        self.confirmacao = Confirmacao(conf_alerta["janela_quadros"], conf_alerta["minimo_quadros"],
                                       conf_alerta["intervalo_entre_alertas_min"] * 60)
        self.notificador = Notificador(PASTA_PROJETO / "saidas" / "alertas", config["dias_guardar_fotos"])

        self.area_normalizada = carregar_area(PASTA_PROJETO / config["area_interesse"])
        if self.area_normalizada is None:
            logging.warning("Área de interesse não definida: monitorando a imagem INTEIRA")
        else:
            logging.info("Área de interesse com %d pontos", len(self.area_normalizada))

        self.leitor = None
        self.ligada_em = None
        self.alertas_no_periodo = 0
        self.avisou_sem_imagem = False

    def no_horario(self):
        return self.args.ignorar_horario or dentro_do_horario(datetime.now().time(), self.inicio, self.fim)

    def ligar_camera(self):
        camera = self.config["camera"]
        self.leitor = LeitorCamera(self.args.fonte, str(camera["canal"]), str(camera["subtipo"]))
        self.leitor.iniciar()
        self.ligada_em = time.monotonic()
        self.alertas_no_periodo = 0
        self.avisou_sem_imagem = False
        self.notificador.apagar_fotos_antigas()
        self.notificador.enviar(f"Monitoramento INICIADO: {self.ambiente} "
                                f"({self.inicio:%H:%M} às {self.fim:%H:%M}).")

    def desligar_camera(self):
        self.leitor.parar()
        self.leitor = None
        self.notificador.enviar(f"Monitoramento ENCERRADO: {self.ambiente}. "
                                f"Alertas no período: {self.alertas_no_periodo}.")

    def verificar_imagem(self):
        """Avisa uma vez se a câmera ficar muito tempo sem mandar imagem."""
        limite = self.config["camera_sem_imagem_s"]
        ultimo = self.leitor.ultimo_quadro_em
        sem_imagem = (ultimo is None and time.monotonic() - self.ligada_em > limite) or \
                     (ultimo is not None and time.monotonic() - ultimo > limite)
        if sem_imagem and not self.avisou_sem_imagem:
            self.notificador.enviar(f"ATENÇÃO: a câmera de {self.ambiente} está sem imagem há mais de {limite} s. "
                                    "O monitoramento está parado até ela voltar.")
            self.avisou_sem_imagem = True
        elif not sem_imagem and self.avisou_sem_imagem:
            self.notificador.enviar(f"A câmera de {self.ambiente} voltou a enviar imagem.")
            self.avisou_sem_imagem = False

    def analisar(self, quadro):
        """Roda o YOLO e aplica área + confirmação. Devolve o quadro desenhado."""
        resultado = self.modelo.predict(quadro, classes=[CLASSE_PESSOA], conf=self.conf,
                                        imgsz=self.imgsz, verbose=False)[0]
        altura, largura = quadro.shape[:2]
        area = area_em_pixels(self.area_normalizada, largura, altura)

        caixas = [caixa.tolist() for caixa in resultado.boxes.xyxy]
        dentro = [c for c in caixas if dentro_da_area(pes_da_pessoa(c), area)]
        fora = [c for c in caixas if c not in dentro]
        cena = desenhar_cena(quadro.copy(), area, dentro, fora)

        if self.confirmacao.registrar(len(dentro) > 0, time.monotonic()):
            self.alertas_no_periodo += 1
            texto = f"Pessoa detectada: {self.ambiente} às {datetime.now():%H:%M} ({len(dentro)} pessoa(s))."
            self.notificador.enviar(texto, cena)
        return cena

    def executar(self):
        ultimo_numero = 0
        proxima_analise = 0.0
        while True:
            if not self.no_horario():
                if self.leitor is not None:
                    self.desligar_camera()
                time.sleep(30)  # fora do horário: só confere o relógio de vez em quando
                continue

            if self.leitor is None:
                self.ligar_camera()

            self.verificar_imagem()
            numero, quadro = self.leitor.ultimo_quadro()
            agora = time.monotonic()
            if quadro is None or numero == ultimo_numero or agora < proxima_analise:
                time.sleep(0.01)
                continue
            ultimo_numero = numero
            proxima_analise = agora + self.intervalo_analise

            cena = self.analisar(quadro)
            if self.args.janela:
                cv2.imshow(TITULO_JANELA, cena)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break

    def encerrar(self):
        if self.leitor is not None:
            self.leitor.parar()
        cv2.destroyAllWindows()
        self.notificador.aguardar_envios(limite_s=15)  # tenta mandar o que ainda estiver na fila
        logging.info("Programa encerrado")


def main():
    args = ler_argumentos()
    configurar_log()
    with open(args.config, encoding="utf-8") as arquivo:
        config = yaml.safe_load(arquivo)

    if args.testar_alerta:
        notificador = Notificador(PASTA_PROJETO / "saidas" / "alertas", config["dias_guardar_fotos"])
        notificador.enviar(
            f"Teste de alerta do monitoramento: {config['ambiente']}. Se você recebeu, está funcionando.")
        notificador.aguardar_envios(limite_s=30)
        return 0

    # Confere a fonte antes de começar, para não ficar tentando reconectar a algo que nunca vai existir
    if args.fonte == "rtsp":
        try:
            montar_url_rtsp()
        except ValueError as erro:
            logging.error("%s", erro)
            return 1
    elif not Path(args.fonte).is_file():
        logging.error("Arquivo de vídeo não encontrado: %s", args.fonte)
        return 1

    monitor = Monitor(config, args)
    logging.info("Monitorando %s | horário %s às %s%s", config["ambiente"], config["horario"]["inicio"],
                 config["horario"]["fim"], " (IGNORANDO horário: modo de teste)" if args.ignorar_horario else "")
    try:
        monitor.executar()
    except KeyboardInterrupt:
        logging.info("Interrompido pelo usuário (Ctrl+C)")
    finally:
        monitor.encerrar()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
