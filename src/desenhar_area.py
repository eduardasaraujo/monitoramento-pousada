"""Desenha a área de interesse (o polígono monitorado) clicando sobre a imagem da câmera.

Comandos na janela:
    clique esquerdo   adiciona um ponto
    z                 desfaz o último ponto
    Enter ou s        salva (precisa de pelo menos 3 pontos)
    Esc ou q          sai sem salvar

Desenhe o contorno do CHÃO da área: o sistema verifica onde estão os pés da pessoa.

Exemplos:
    python src/desenhar_area.py --imagem saidas/coleta_.../canal01_substream/foto.jpg
    python src/desenhar_area.py --canal 1          # tira a foto direto da câmera
"""

import argparse
import json
from pathlib import Path

import cv2
import numpy as np

from fonte_video import abrir_fonte

PASTA_PROJETO = Path(__file__).resolve().parent.parent
TITULO = "Area de interesse (Enter salva, z desfaz, Esc sai)"


def salvar_area(pontos, largura, altura, caminho):
    """Salva os pontos de 0 a 1 (independente da resolução) num arquivo JSON."""
    normalizados = [[round(x / largura, 4), round(y / altura, 4)] for x, y in pontos]
    caminho.write_text(json.dumps({"pontos": normalizados}, indent=2), encoding="utf-8")
    return normalizados


def carregar_area(caminho):
    """Lê os pontos salvos por salvar_area; devolve None se o arquivo não existir."""
    if not caminho.is_file():
        return None
    return json.loads(caminho.read_text(encoding="utf-8"))["pontos"]


def desenhar(imagem, pontos):
    tela = imagem.copy()
    if len(pontos) >= 3:
        camada = tela.copy()
        cv2.fillPoly(camada, [np.array(pontos, dtype=np.int32)], (0, 200, 255))
        tela = cv2.addWeighted(camada, 0.3, tela, 0.7, 0)  # preenchimento semitransparente
    for i, ponto in enumerate(pontos):
        cv2.circle(tela, ponto, 5, (0, 200, 255), -1)
        if i > 0:
            cv2.line(tela, pontos[i - 1], ponto, (0, 200, 255), 2)
    if len(pontos) >= 3:
        cv2.line(tela, pontos[-1], pontos[0], (0, 200, 255), 2)
    return tela


def main():
    parser = argparse.ArgumentParser(description="Desenha a área de interesse sobre a imagem da câmera.")
    origem = parser.add_mutually_exclusive_group(required=True)
    origem.add_argument("--imagem", help="Foto da câmera (ex.: a foto.jpg da coleta)")
    origem.add_argument("--canal", help="Tira a foto direto do canal do DVR")
    parser.add_argument("--subtipo", default="1", choices=["0", "1"])
    parser.add_argument("--saida", default=str(PASTA_PROJETO / "config" / "area_interesse.json"))
    args = parser.parse_args()

    if args.imagem:
        imagem = cv2.imread(args.imagem)
        if imagem is None:
            print(f"ERRO: não consegui abrir a imagem {args.imagem}")
            return
    else:
        try:
            captura, _ = abrir_fonte("rtsp", args.canal, args.subtipo)
        except (ConnectionError, ValueError) as erro:
            print(f"ERRO: {erro}")
            return
        ok, imagem = captura.read()
        captura.release()
        if not ok:
            print("ERRO: a câmera não enviou imagem")
            return

    altura, largura = imagem.shape[:2]
    pontos = []

    def ao_clicar(evento, x, y, _flags, _param):
        if evento == cv2.EVENT_LBUTTONDOWN:
            pontos.append((x, y))

    cv2.namedWindow(TITULO)
    cv2.setMouseCallback(TITULO, ao_clicar)

    while True:
        cv2.imshow(TITULO, desenhar(imagem, pontos))
        tecla = cv2.waitKey(30) & 0xFF
        if tecla == ord("z") and pontos:
            pontos.pop()
        elif tecla in (13, 10, ord("s")):  # 13 e 10 = Enter
            if len(pontos) < 3:
                print("Marque pelo menos 3 pontos")
                continue
            caminho = Path(args.saida)
            salvar_area(pontos, largura, altura, caminho)
            cv2.imwrite(str(caminho.with_suffix(".png")), desenhar(imagem, pontos))  # imagem de conferência
            print(f"Área salva em {caminho} (e imagem de conferência em {caminho.with_suffix('.png')})")
            break
        elif tecla in (27, ord("q")):  # 27 = Esc
            print("Saiu sem salvar")
            break

    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()
