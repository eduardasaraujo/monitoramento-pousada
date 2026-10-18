"""Primeira etapa do projeto: detectar pessoas em um vídeo com YOLO.

Fluxo: fonte de vídeo -> OpenCV lê os quadros -> YOLO detecta pessoas
       -> desenha as caixas -> mostra na tela e/ou salva o vídeo anotado.

Ainda NÃO há regras de área, horário, rastreamento ou alertas.

Exemplo:
    python src/detectar_pessoas.py --fonte videos/noturno_cctv_mixkit_31372.mp4 --salvar
"""

import argparse
import logging
import os
import time
from datetime import datetime
from pathlib import Path

PASTA_PROJETO = Path(__file__).resolve().parent.parent

# Mantém as configurações da Ultralytics dentro do projeto em vez de ~/.config.
# Precisa ser definido antes de importar a biblioteca.
os.environ.setdefault("YOLO_CONFIG_DIR", str(PASTA_PROJETO / "config" / "ultralytics"))

import cv2  # noqa: E402
import psutil  # noqa: E402
import torch  # noqa: E402
from ultralytics import YOLO  # noqa: E402

from fonte_video import abrir_fonte  # noqa: E402

CLASSE_PESSOA = 0  # no conjunto de dados COCO, usado no treino do YOLO, a classe 0 é "person"
COR_CAIXA = (0, 255, 0)  # verde, no formato BGR do OpenCV


def ler_argumentos():
    parser = argparse.ArgumentParser(description="Detecta pessoas em vídeo usando YOLO.")
    parser.add_argument("--fonte", required=True,
                        help='Caminho do arquivo de vídeo, ou "rtsp" para usar a câmera do config/.env')
    parser.add_argument("--modelo", default=str(PASTA_PROJETO / "modelos" / "yolo11n.pt"),
                        help="Arquivo de pesos do YOLO (padrão: modelos/yolo11n.pt)")
    parser.add_argument("--conf", type=float, default=0.25,
                        help="Confiança mínima para aceitar uma detecção, entre 0 e 1 (padrão: 0.25)")
    parser.add_argument("--imgsz", type=int, default=640,
                        help="Tamanho da imagem de entrada do YOLO; menor = mais rápido e menos preciso (padrão: 640)")
    parser.add_argument("--fps-alvo", type=float, default=5,
                        help="Quantos quadros por segundo analisar; os demais são descartados (padrão: 5)")
    parser.add_argument("--threads", type=int, default=4,
                        help="Threads de CPU usadas pelo PyTorch e pelo OpenCV (padrão: 4)")
    parser.add_argument("--salvar", action="store_true",
                        help="Salva o vídeo com as detecções em saidas/")
    parser.add_argument("--sem-janela", action="store_true",
                        help="Não abre janela de exibição (útil para medir desempenho)")
    return parser.parse_args()


def configurar_log(pasta_saidas):
    pasta_saidas.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(pasta_saidas / "execucao.log", encoding="utf-8"),
        ],
    )


def desenhar_deteccoes(quadro, caixas):
    """Desenha um retângulo e a confiança para cada pessoa detectada."""
    for caixa in caixas:
        x1, y1, x2, y2 = map(int, caixa.xyxy[0])
        confianca = float(caixa.conf[0])
        cv2.rectangle(quadro, (x1, y1), (x2, y2), COR_CAIXA, 2)
        cv2.putText(quadro, f"pessoa {confianca:.2f}", (x1, max(y1 - 8, 15)),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, COR_CAIXA, 2)


def main():
    args = ler_argumentos()
    pasta_saidas = PASTA_PROJETO / "saidas"
    configurar_log(pasta_saidas)

    torch.set_num_threads(args.threads)
    cv2.setNumThreads(args.threads)

    logging.info("Carregando modelo %s", args.modelo)
    modelo = YOLO(args.modelo)

    try:
        captura, descricao = abrir_fonte(args.fonte)
    except (FileNotFoundError, ConnectionError, ValueError) as erro:
        logging.error("%s", erro)
        return 1

    fps_fonte = captura.get(cv2.CAP_PROP_FPS)
    if not 0 < fps_fonte <= 120:
        # Algumas câmeras RTSP não informam o FPS corretamente.
        logging.warning("FPS da fonte inválido (%s); assumindo 25", fps_fonte)
        fps_fonte = 25.0
    # Ex.: fonte a 25 fps e alvo de 5 fps -> analisa 1 a cada 5 quadros
    passo = max(1, round(fps_fonte / args.fps_alvo))

    logging.info("Fonte: %s | %.1f fps | analisando 1 a cada %d quadros (~%.1f fps)",
                 descricao, fps_fonte, passo, fps_fonte / passo)
    logging.info("Parâmetros: conf=%.2f imgsz=%d threads=%d", args.conf, args.imgsz, args.threads)

    gravador = None
    quadros_lidos = 0
    quadros_analisados = 0
    quadros_com_pessoa = 0
    total_deteccoes = 0
    tempos_inferencia = []
    processo = psutil.Process()
    memoria_pico = 0
    cpu_inicio = processo.cpu_times()
    inicio = time.perf_counter()

    while True:
        # grab() lê o próximo quadro; retrieve() só o converte em imagem quando ele será analisado
        if not captura.grab():
            if args.fonte == "rtsp":
                logging.error("Falha ao ler quadro da câmera (conexão perdida?)")
            break
        quadros_lidos += 1
        if (quadros_lidos - 1) % passo != 0:
            continue

        ok, quadro = captura.retrieve()
        if not ok:
            logging.warning("Quadro %d corrompido, ignorando", quadros_lidos)
            continue

        t0 = time.perf_counter()
        resultado = modelo.predict(quadro, classes=[CLASSE_PESSOA], conf=args.conf,
                                   imgsz=args.imgsz, verbose=False)[0]
        tempos_inferencia.append(time.perf_counter() - t0)

        caixas = resultado.boxes
        quadros_analisados += 1
        total_deteccoes += len(caixas)
        if len(caixas) > 0:
            quadros_com_pessoa += 1

        desenhar_deteccoes(quadro, caixas)
        cv2.putText(quadro, f"{len(caixas)} pessoa(s) | {tempos_inferencia[-1] * 1000:.0f} ms",
                    (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)

        if args.salvar:
            if gravador is None:
                altura, largura = quadro.shape[:2]
                nome = Path(args.fonte).stem if args.fonte != "rtsp" else "rtsp"
                caminho_saida = pasta_saidas / f"{nome}_{datetime.now():%Y%m%d_%H%M%S}.mp4"
                gravador = cv2.VideoWriter(str(caminho_saida), cv2.VideoWriter_fourcc(*"mp4v"),
                                           fps_fonte / passo, (largura, altura))
                logging.info("Salvando vídeo anotado em %s", caminho_saida)
            gravador.write(quadro)

        if not args.sem_janela:
            cv2.imshow("Deteccao de pessoas (q para sair)", quadro)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                logging.info("Interrompido pelo usuário")
                break

        memoria_pico = max(memoria_pico, processo.memory_info().rss)

    tempo_total = time.perf_counter() - inicio
    cpu_fim = processo.cpu_times()
    captura.release()
    if gravador is not None:
        gravador.release()
    cv2.destroyAllWindows()

    if quadros_analisados == 0:
        logging.error("Nenhum quadro foi analisado")
        return 1

    # A primeira inferência é mais lenta (aquecimento do modelo), então fica fora da média
    tempos = tempos_inferencia[1:] or tempos_inferencia
    media_ms = 1000 * sum(tempos) / len(tempos)
    maximo_ms = 1000 * max(tempos)
    duracao_video = quadros_lidos / fps_fonte
    # Acima de 1.0 significa que o sistema processa mais rápido que o vídeo acontece
    fator_tempo_real = duracao_video / tempo_total
    uso_cpu = 100 * ((cpu_fim.user + cpu_fim.system) - (cpu_inicio.user + cpu_inicio.system)) / tempo_total

    logging.info("===== RESUMO =====")
    logging.info("Quadros lidos: %d (%.1f s de vídeo) | analisados: %d",
                 quadros_lidos, duracao_video, quadros_analisados)
    logging.info("Quadros com pessoa: %d (%.0f%%) | total de detecções: %d",
                 quadros_com_pessoa, 100 * quadros_com_pessoa / quadros_analisados, total_deteccoes)
    logging.info("Inferência: média %.0f ms | máximo %.0f ms | primeira (aquecimento) %.0f ms",
                 media_ms, maximo_ms, 1000 * tempos_inferencia[0])
    logging.info("Capacidade máxima de análise: ~%.1f quadros/s", 1000 / media_ms)
    logging.info("Tempo total: %.1f s | fator tempo real: %.2fx (%s)", tempo_total, fator_tempo_real,
                 "acompanha" if fator_tempo_real >= 1 else "NÃO acompanha o vídeo")
    logging.info("CPU média: %.0f%% (100%% = 1 núcleo) | memória pico: %.0f MB",
                 uso_cpu, memoria_pico / 1024 ** 2)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
