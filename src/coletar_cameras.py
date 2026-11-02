"""Ferramenta para a visita à pousada: testa cada câmera do DVR e coleta material.

Para cada canal: conecta via RTSP, mede resolução, FPS e codec, salva uma foto
(para desenhar a área de interesse depois) e um trecho de vídeo BRUTO, sem
anotações (para testar o detector depois, em casa). No fim, mostra um resumo.

Precisa do config/.env preenchido (IP, usuário e senha do DVR).

Exemplos:
    python src/coletar_cameras.py --canais 1-8 --segundos 5     # varredura rápida: quais canais têm câmera?
    python src/coletar_cameras.py --canais 2,5 --segundos 60    # trechos maiores das câmeras escolhidas
    python src/coletar_cameras.py --canais 2 --subtipo 0        # fluxo principal, para comparar
"""

import argparse
import csv
import time
from datetime import datetime
from pathlib import Path

import cv2

from fonte_video import abrir_fonte, montar_url_rtsp

PASTA_PROJETO = Path(__file__).resolve().parent.parent


def ler_canais(texto):
    """Converte "1-4" em [1, 2, 3, 4] e "1,3,5" em [1, 3, 5]."""
    canais = []
    for parte in texto.split(","):
        if "-" in parte:
            inicio, fim = parte.split("-")
            canais.extend(range(int(inicio), int(fim) + 1))
        else:
            canais.append(int(parte))
    return canais


def nome_do_codec(captura):
    """O OpenCV devolve o codec como um número de 4 bytes; isto o transforma em texto (ex.: "h264")."""
    codigo = int(captura.get(cv2.CAP_PROP_FOURCC))
    return "".join(chr((codigo >> (8 * i)) & 0xFF) for i in range(4)).strip("\x00 ") or "?"


def coletar(captura, pasta, segundos):
    """Lê a câmera por `segundos`, salvando uma foto e o vídeo bruto. Devolve as medições."""
    fps_informado = captura.get(cv2.CAP_PROP_FPS)
    gravador = None
    quadros = 0
    inicio = time.perf_counter()

    while time.perf_counter() - inicio < segundos:
        ok, quadro = captura.read()
        if not ok:
            break
        quadros += 1
        if gravador is None:
            altura, largura = quadro.shape[:2]
            # A foto é tirada do primeiro quadro; serve para desenhar a área de interesse
            cv2.imwrite(str(pasta / "foto.jpg"), quadro)
            fps_video = fps_informado if 0 < fps_informado <= 120 else 25
            gravador = cv2.VideoWriter(str(pasta / "video.mp4"), cv2.VideoWriter_fourcc(*"mp4v"),
                                       fps_video, (largura, altura))
        gravador.write(quadro)

    duracao = time.perf_counter() - inicio
    if gravador is not None:
        gravador.release()

    return {
        "largura": int(captura.get(cv2.CAP_PROP_FRAME_WIDTH)),
        "altura": int(captura.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        "codec": nome_do_codec(captura),
        "fps_informado": round(fps_informado, 1),
        # Quadros que realmente chegaram por segundo (pode ser menor que o informado se a rede estiver ruim)
        "fps_medido": round(quadros / duracao, 1) if duracao > 0 else 0,
        "quadros": quadros,
    }


def main():
    parser = argparse.ArgumentParser(description="Testa as câmeras do DVR e coleta foto e vídeo de cada uma.")
    parser.add_argument("--canais", default="1-8", help='Canais a testar, ex.: "1-8" ou "1,3,5" (padrão: 1-8)')
    parser.add_argument("--subtipo", default="1", choices=["0", "1"],
                        help="0 = fluxo principal, 1 = substream (padrão: 1)")
    parser.add_argument("--segundos", type=float, default=30, help="Duração do vídeo de cada canal (padrão: 30)")
    parser.add_argument("--timeout", type=int, default=10,
                        help="Segundos de espera antes de desistir de um canal (padrão: 10)")
    args = parser.parse_args()

    try:
        montar_url_rtsp()  # só confere se o config/.env está preenchido, antes de criar pastas
    except ValueError as erro:
        print(f"ERRO: {erro}")
        return

    pasta_coleta = PASTA_PROJETO / "saidas" / f"coleta_{datetime.now():%Y%m%d_%H%M%S}"
    pasta_coleta.mkdir(parents=True)
    tipo = "principal" if args.subtipo == "0" else "substream"
    print(f"Salvando em {pasta_coleta}\n")

    resultados = []
    for canal in ler_canais(args.canais):
        print(f"Canal {canal} ({tipo}): conectando...", flush=True)
        linha = {"canal": canal, "fluxo": tipo, "status": "", "largura": "", "altura": "", "codec": "",
                 "fps_informado": "", "fps_medido": "", "quadros": "", "tempo_conexao_s": ""}
        t0 = time.perf_counter()
        try:
            captura, _ = abrir_fonte("rtsp", str(canal), args.subtipo, args.timeout)
        except ConnectionError as erro:
            linha["status"] = "FALHOU"
            print(f"  FALHOU: {erro}\n")
            resultados.append(linha)
            continue

        linha["tempo_conexao_s"] = round(time.perf_counter() - t0, 1)
        pasta_canal = pasta_coleta / f"canal{canal:02d}_{tipo}"
        pasta_canal.mkdir()
        linha.update(coletar(captura, pasta_canal, args.segundos))
        captura.release()

        linha["status"] = "OK" if linha["quadros"] > 0 else "SEM IMAGEM"
        print(f"  {linha['status']}: {linha['largura']}x{linha['altura']} | codec {linha['codec']} | "
              f"fps informado {linha['fps_informado']}, medido {linha['fps_medido']} | "
              f"{linha['quadros']} quadros | conectou em {linha['tempo_conexao_s']} s\n")
        resultados.append(linha)

    with open(pasta_coleta / "resumo.csv", "w", newline="", encoding="utf-8") as arquivo:
        escritor = csv.DictWriter(arquivo, fieldnames=list(resultados[0].keys()))
        escritor.writeheader()
        escritor.writerows(resultados)

    print("===== RESUMO =====")
    for linha in resultados:
        print(f"Canal {linha['canal']}: {linha['status']}")
    print(f"\nFotos, vídeos e resumo.csv em {pasta_coleta}")


if __name__ == "__main__":
    main()
