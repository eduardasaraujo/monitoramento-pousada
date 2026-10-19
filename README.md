# Monitoramento Noturno Inteligente para Pousada — Etapa 1

Projeto acadêmico de Robótica Inclusiva. Esta primeira etapa valida o início da arquitetura:

```
vídeo (arquivo ou RTSP do DVR) → OpenCV → YOLO (detecção de pessoas) → vídeo anotado + métricas
```

**Ainda não implementado:** rastreamento (ByteTrack), áreas de interesse, regras de horário,
alertas por WhatsApp, AWS e processamento simultâneo das três câmeras.

## Estrutura

```
monitoramento-pousada/
├── src/
│   ├── detectar_pessoas.py   # programa principal: lê quadros, roda o YOLO, desenha, mede desempenho
│   └── fonte_video.py        # abre arquivo de vídeo ou câmera RTSP (credenciais via config/.env)
├── scripts/
│   └── simular_notebook_pousada.sh  # roda o detector com CPU limitada (só Linux)
├── config/
│   └── .env.example          # modelo das credenciais do DVR
├── modelos/                  # pesos do YOLO (baixados automaticamente se faltarem)
├── videos/                   # vídeos de teste
├── saidas/                   # vídeos anotados e execucao.log (gerados)
└── requirements.txt
```

## Instalação

Requer Python 3.10 ou superior (testado com 3.12.3). Não precisa de privilégios de administrador.

**Linux**
```bash
cd monitoramento-pousada
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
```

**Windows** (provável sistema do notebook da pousada)
```powershell
cd monitoramento-pousada
py -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

O `requirements.txt` instala o PyTorch **somente para CPU**. Na primeira execução, o YOLO baixa
o arquivo `modelos/yolo11n.pt` (cerca de 5 MB) se ele não existir.

**Vídeo de teste:** o vídeo não fica no repositório, porque a licença da Mixkit não permite
redistribuí-lo. Baixe-o com o comando abaixo, que funciona no Linux e no Windows 10/11:
```bash
curl -L -o videos/noturno_cctv_mixkit_31372.mp4 https://assets.mixkit.co/videos/31372/31372-720.mp4
```

## Demonstração rápida

Com o ambiente instalado e o vídeo baixado:

```bash
# 1. Detecção com janela ao vivo, repetindo até apertar q
.venv/bin/python src/detectar_pessoas.py --fonte videos/noturno_cctv_mixkit_31372.mp4 --repetir

# 2. Mesmo teste simulando a CPU do notebook da pousada (só Linux), para mostrar as métricas
scripts/simular_notebook_pousada.sh --fonte videos/noturno_cctv_mixkit_31372.mp4 --sem-janela

# 3. Comparar com a entrada menor do YOLO (mais rápida, detecta menos)
scripts/simular_notebook_pousada.sh --fonte videos/noturno_cctv_mixkit_31372.mp4 --sem-janela --imgsz 416
```

## Execução

```bash
# Linux (no Windows, troque .venv/bin/python por .venv\Scripts\python e / por \)
.venv/bin/python src/detectar_pessoas.py --fonte videos/noturno_cctv_mixkit_31372.mp4
```

Uma janela mostra as detecções (tecla `q` ou o X da janela encerram). Ao final aparece um resumo com
quadros analisados, detecções, tempo de inferência, uso de CPU e memória. O mesmo resumo
é gravado em `saidas/execucao.log`.

| Parâmetro | Padrão | Função |
|---|---|---|
| `--fonte` | (obrigatório) | caminho do vídeo, ou `rtsp` para a câmera do `config/.env` |
| `--modelo` | `modelos/yolo11n.pt` | pesos do YOLO |
| `--conf` | `0.25` | confiança mínima de uma detecção (0 a 1) |
| `--imgsz` | `640` | tamanho da imagem de entrada do YOLO; `416` é ~45% mais rápido, mas detecta menos |
| `--fps-alvo` | `5` | quadros analisados por segundo; os demais são descartados |
| `--threads` | `4` | threads de CPU do PyTorch/OpenCV |
| `--salvar` | — | grava o vídeo anotado em `saidas/` |
| `--sem-janela` | — | não abre janela (use para medir desempenho) |
| `--repetir` | — | recomeça o vídeo ao terminar e só para com `q`; o vídeo salvo guarda só a 1ª passagem |

Ao reproduzir um **arquivo**, o programa roda o mais rápido que conseguir, não na velocidade
real do vídeo. É por isso que o "fator tempo real" pode passar de 1.

### Como ler o resumo

- **Fator tempo real**: duração do vídeo ÷ tempo de processamento. Acima de 1,0, o sistema dá
  conta da câmera ao vivo. Abaixo de 1,0, ele fica para trás, e numa câmera ao vivo o atraso cresce.
- **Capacidade máxima de análise**: quantos quadros por segundo o YOLO aguentaria analisar
  (considera só a inferência, sem a decodificação do vídeo).
- **Quadros com pessoa**: não é acurácia, porque não há rótulos verdadeiros. É preciso comparar
  com o vídeo para saber quantos quadros realmente têm pessoa.

## Câmera RTSP do DVR (preparado, ainda não validado)

1. Copie `config/.env.example` para `config/.env` e preencha IP, usuário, senha e canal.
2. Execute com `--fonte rtsp`.

A URL segue o padrão dos DVRs Intelbras
(`rtsp://usuario:senha@ip:554/cam/realmonitor?channel=N&subtype=1`), usa TCP e o substream
(`subtype=1`) por padrão. A senha aparece como `***` no log. Se não conseguir conectar, o
programa encerra com erro após cerca de 30 s.

**Segurança:** o RTSP deve ser acessado só pela rede local da pousada (ou por VPN). Nunca
abra a porta 554 do DVR para a internet. Use um usuário do DVR só com permissão de visualização.

## Testes realizados (18/10/2026)

**Vídeo:** `videos/noturno_cctv_mixkit_31372.mp4`, clipe de banco de vídeos gratuito
([Mixkit, licença Free](https://mixkit.co/free-stock-video/two-thieves-recorded-on-a-security-camera-31372/)).
Simula uma câmera de segurança à noite: preto e branco, interno, câmera no teto, 1280×720, 24 fps,
21,5 s, 2 pessoas de roupa escura. **É uma encenação, não uma imagem infravermelha real de DVR.**

**Máquina:** os testes rodaram num Ryzen 7 7735HS, bem mais potente que o notebook da pousada.
Para aproximar o i7 de 4ª geração, foi usado `scripts/simular_notebook_pousada.sh`, que limita o
processo a 4 núcleos lógicos, 200% de CPU e 3 GB de RAM. O perfil corresponde a um i7-4500U,
o cenário mais fraco. É uma estimativa: o número definitivo só sai rodando no notebook real.

### Desempenho simulado, 1 câmera (5 quadros/s analisados)

| Modelo | imgsz | Inferência média | Fator tempo real | Memória |
|---|---|---|---|---|
| yolo11n | 320 | 26 ms | 5,1x | 580 MB |
| yolo11n | 416 | 36 ms | 4,2x | 586 MB |
| **yolo11n** | **640** | **63 ms** | **2,7x** | **597 MB** |
| yolo26n | 416 | 36 ms | 4,1x | 583 MB |
| yolo26n | 640 | 64 ms | 2,7x | 594 MB |

### Desempenho simulado, 3 processos simultâneos (estimativa para as 3 câmeras)

| imgsz | Inferência média | Fator tempo real | Memória total |
|---|---|---|---|
| 640 | ~225 ms | ~0,8x (**não acompanha**) | ~1,8 GB |
| 416 | ~126 ms | ~1,3x (acompanha, com pouca folga) | ~1,75 GB |

### Qualidade da detecção (mesmo vídeo, 103 quadros analisados)

Por inspeção visual, há pessoa visível em praticamente todos os quadros analisados.

| Configuração | Quadros com pessoa detectada |
|---|---|
| yolo11n, 416, conf 0.4 | 28 (27%) |
| yolo26n, 416, conf 0.4 | 41 (40%) |
| yolo26n, 640, conf 0.25 | 63 (61%) |
| **yolo11n, 640, conf 0.25** | **67 (65%)** |

Nos quadros revisados, as detecções extras com `conf=0.25` estavam sobre pessoas reais; não foram
observados falsos positivos. As falhas acontecem principalmente com a pessoa agachada, de roupa
preta, diante da cortina escura. Mesmo assim, a pessoa foi detectada já no 2º quadro analisado
(~0,2 s), e um alerta por **evento** (presença confirmada em vários quadros) seria disparado.

**Configuração escolhida como padrão:** `yolo11n`, `imgsz=640`, `conf=0.25`. Neste vídeo ela teve a
melhor detecção com a mesma velocidade do yolo26n, e o yolo11n é mais documentado. Se as 3 câmeras
precisarem rodar no notebook, `--imgsz 416` é a alternativa, à custa de detectar menos.

### Outros testes

- Janela de exibição no Linux/Wayland: o programa rodou até o fim sem erros. Aparecem avisos do Qt
  (plugin "wayland" e fontes), que não impedem o funcionamento.
- `--fonte rtsp` sem `config/.env`: mensagem clara indicando as variáveis faltando.
- `--fonte rtsp` com DVR inexistente: erro tratado após ~30 s, senha mascarada no log.
- Arquivo inexistente: mensagem de erro clara.
- Senha com caracteres especiais (`@`, `:`): codificada corretamente na URL.

## Limitações conhecidas

- Os números de desempenho são **simulados**. O modelo exato do i7 da pousada ainda não é conhecido
  (um i7-4700HQ, de 4 núcleos, seria mais rápido que o simulado).
- O vídeo noturno é encenado. Câmeras com infravermelho real geram imagem com mais ruído, menos
  contraste e reflexos.
- Foi testado um único vídeo, com poucas pessoas; os resultados de qualidade não são estatísticos.
- O decodificador de vídeo (FFmpeg) usa threads próprias, que não são limitadas por `--threads`.
- A conexão RTSP não foi testada com o DVR real.

## Próximos passos

1. Descobrir o modelo exato do processador do notebook (no Windows: Configurações → Sistema → Sobre)
   e o sistema operacional.
2. Instalar o projeto **no notebook da pousada** e rodar
   `python src/detectar_pessoas.py --fonte videos/noturno_cctv_mixkit_31372.mp4 --sem-janela`
   com `--imgsz 640` e `--imgsz 416`, para obter os números reais.
3. Exportar do DVR um trecho **noturno real** de cada câmera (de preferência com alguém passando)
   e repetir o teste de qualidade.
4. Confirmar no DVR: RTSP habilitado, resolução do substream, modelo da câmera da piscina e um
   usuário só de visualização.
5. Testar `--fonte rtsp` com uma câmera, na rede local da pousada.
