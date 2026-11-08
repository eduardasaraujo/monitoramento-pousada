# Monitoramento Noturno Inteligente para Pousada

Projeto acadêmico de Robótica Inclusiva. O sistema usa as câmeras e o DVR que a pousada já possui
para detectar pessoas em áreas e horários em que não deve haver circulação, e avisa os responsáveis.

```
câmera → DVR → RTSP → OpenCV → YOLO → área + horário + confirmação → alerta (log, foto e Telegram)
```

## Situação atual

O sistema foi instalado na pousada em 02/11/2026 e está em funcionamento com **uma câmera**.

| Item | Configuração |
|---|---|
| Câmera | Recepção (canal 3 do DVR, substream) |
| Horário monitorado | 23:00 às 06:00 |
| Detecção | `yolo11s`, entrada 640, confiança 0.25, 5 quadros/s |
| Confirmação | pessoa em pelo menos 3 dos últimos 5 quadros; 5 min entre alertas |
| Alertas | grupo do Telegram com o proprietário da pousada |
| Computador | notebook com Pop!_OS (dual boot), placa de vídeo dedicada e 16 GB de RAM |
| Execução | serviço que inicia com o computador |

## Estrutura

```
monitoramento-pousada/
├── src/
│   ├── monitorar.py          # sistema que fica rodando na pousada
│   ├── regras.py             # horário, área de interesse e confirmação
│   ├── leitor_camera.py      # leitura contínua da câmera e reconexão
│   ├── alertas.py            # log, fotos, Telegram e limpeza de fotos antigas
│   ├── desenhar_area.py      # desenha a área de interesse sobre a imagem
│   ├── fonte_video.py        # abre arquivo de vídeo ou câmera RTSP (credenciais via config/.env)
│   ├── coletar_cameras.py    # testa os canais do DVR e coleta foto e vídeo
│   └── detectar_pessoas.py   # detector com métricas, para testes e demonstração
├── scripts/                  # instalação, serviço, medição de desempenho e empacotamento
├── config/
│   ├── monitoramento.yaml    # ambiente, canal, horário e parâmetros
│   └── .env.example          # modelo das credenciais do DVR e do Telegram
├── docs/planejamento.md      # etapas até a conclusão do projeto
├── modelos/                  # pesos do YOLO (baixados automaticamente se faltarem)
├── videos/                   # vídeos de teste
├── saidas/                   # logs, fotos dos alertas e vídeos anotados (gerados)
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

O `requirements.txt` instala o PyTorch **somente para CPU**. Os pesos do YOLO usados
(`modelos/yolo11n.pt` no detector e `modelos/yolo11s.pt` no monitoramento) são baixados na primeira
execução, se ainda não existirem.

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

# 2. Mesmo teste com a CPU limitada, simulando um notebook mais fraco (só Linux)
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
| `--modelo` | `modelos/yolo11n.pt` | pesos do YOLO (o `monitorar.py` usa o modelo definido em `config/monitoramento.yaml`) |
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

## Sistema de monitoramento (1 câmera)

`src/monitorar.py` é o sistema que fica rodando na pousada:

```
fora do horário  → câmera desligada, nada é processado
dentro do horário → câmera → YOLO → pessoas com os pés DENTRO da área de interesse
                  → confirmação (3 de 5 quadros) → alerta: log + foto + Telegram
```

| Arquivo | Função |
|---|---|
| `config/monitoramento.yaml` | Ambiente, canal da câmera, horário, parâmetros (edite aqui) |
| `src/monitorar.py` | Programa principal |
| `src/regras.py` | Horário (inclusive atravessando a meia-noite), área de interesse e confirmação |
| `src/leitor_camera.py` | Lê a câmera numa thread, guarda só o quadro mais recente e reconecta se cair |
| `src/alertas.py` | Registra, salva a foto e envia pelo Telegram em segundo plano, com novas tentativas; apaga fotos antigas (LGPD) |
| `src/desenhar_area.py` | Desenha a área de interesse clicando sobre a imagem da câmera |
| `scripts/instalar_servico.sh` | Faz o sistema iniciar sozinho com o computador |

Mensagens enviadas: início e fim do monitoramento (com o total de alertas da noite), pessoa
detectada (com foto), câmera sem imagem e câmera de volta. Se a mensagem de início não chegar,
há algum problema. Sem internet, as mensagens ficam numa fila e são reenviadas a cada 10 s, na ordem.

### Passo a passo na pousada

```bash
# 1. Configurar: canal, ambiente e horário em config/monitoramento.yaml; DVR e Telegram em config/.env
# 2. Desenhar a área (o contorno do CHÃO que deve ser vigiado)
.venv/bin/python src/desenhar_area.py --canal 1
# 3. Conferir o Telegram
.venv/bin/python src/monitorar.py --testar-alerta
# 4. Testar de dia, vendo a imagem (alguém passa na área e o alerta deve chegar)
.venv/bin/python src/monitorar.py --ignorar-horario --janela
# 5. Deixar rodando sozinho
scripts/instalar_servico.sh
```

Para testar sem câmera: `.venv/bin/python src/monitorar.py --fonte videos/noturno_cctv_mixkit_31372.mp4 --ignorar-horario --janela`

### Criar o bot do Telegram (uns 2 minutos)

1. No Telegram, converse com **@BotFather**, envie `/newbot` e siga as instruções. Ele devolve o
   **token**: coloque em `TELEGRAM_TOKEN` no `config/.env`.
2. Mande qualquer mensagem para o seu bot. Para alertar a equipe, crie um grupo, adicione o bot e
   mande uma mensagem no grupo.
3. Abra `https://api.telegram.org/bot<TOKEN>/getUpdates` no navegador e copie o número de
   `"chat":{"id": ...}` para `TELEGRAM_CHAT_ID` (em grupos, ele começa com `-`).
4. Rode `--testar-alerta` e confira se a mensagem chegou.

## Ferramentas para instalar e testar na pousada

| Script | Para que serve |
|---|---|
| `scripts/empacotar.sh` | Gera `saidas/pacote_pousada.tar.gz` (código, modelo e vídeo de teste, sem senhas) para copiar a outro computador |
| `scripts/instalar.sh` | Instala tudo num Linux novo: ambiente virtual, dependências, modelo e `config/.env` |
| `scripts/medir_desempenho.sh` | Mede o desempenho **real** do computador: 1 e 3 câmeras, entradas 640 e 416. Salva em `saidas/desempenho_<data>.txt` |
| `src/coletar_cameras.py` | Testa cada canal do DVR e salva foto, vídeo bruto e `resumo.csv` (resolução, FPS, codec) |

```bash
.venv/bin/python src/coletar_cameras.py --canais 1-8 --segundos 5    # quais canais têm câmera?
.venv/bin/python src/coletar_cameras.py --canais 2,5 --segundos 60   # trechos maiores das escolhidas
.venv/bin/python src/detectar_pessoas.py --fonte rtsp --canal 2      # detecção ao vivo numa câmera
```

## Câmera RTSP do DVR

1. Copie `config/.env.example` para `config/.env` e preencha IP, usuário, senha e canal.
2. Execute com `--fonte rtsp`.

A URL segue o padrão dos DVRs Intelbras
(`rtsp://usuario:senha@ip:554/cam/realmonitor?channel=N&subtype=1`), usa TCP e o substream
(`subtype=1`) por padrão. A senha aparece como `***` no log. Se não conseguir conectar em cerca
de 10 s, o `detectar_pessoas.py` encerra com erro, e o `monitorar.py` continua tentando reconectar.

**Segurança:** o RTSP deve ser acessado só pela rede local da pousada (ou por VPN). Nunca
abra a porta 554 do DVR para a internet. Use um usuário do DVR só com permissão de visualização.

## Testes na pousada (02/11/2026)

- **Câmera real:** o acesso ao vivo por RTSP à câmera da recepção (canal 3) funcionou.
- **Escolha do modelo:** num quadro ao vivo da recepção com 2 pessoas, o `yolo11n` encontrou 1 e o
  `yolo11s` encontrou as 2, a cerca de 78 ms por quadro em CPU. O monitoramento passou a usar o
  `yolo11s`. A comparação usou um único quadro.
- **Reinicialização:** a mensagem "Monitoramento INICIADO" se perdeu porque foi enviada antes de o
  Wi-Fi conectar. O envio passou a usar uma fila com novas tentativas.
- **Telegram:** o alerta de teste chegou ao grupo com o proprietário.

## Testes com vídeo gravado (18/10/2026)

**Vídeo:** `videos/noturno_cctv_mixkit_31372.mp4`, clipe de banco de vídeos gratuito
([Mixkit, licença Free](https://mixkit.co/free-stock-video/two-thieves-recorded-on-a-security-camera-31372/)).
Simula uma câmera de segurança à noite: preto e branco, interno, câmera no teto, 1280×720, 24 fps,
21,5 s, 2 pessoas de roupa escura. **É uma encenação, não uma imagem infravermelha real de DVR.**

**Máquina:** os testes rodaram num Ryzen 7 7735HS, com `scripts/simular_notebook_pousada.sh` limitando
o processo a 4 núcleos lógicos, 200% de CPU e 3 GB de RAM. Essa simulação aproximava o notebook
previsto na época (i7 de 4ª geração, 8 GB, sem GPU), que depois foi substituído. **Os números abaixo
são estimativas para esse notebook antigo, não medições do notebook atual.**

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

**Configuração escolhida nesta etapa:** `yolo11n`, `imgsz=640`, `conf=0.25`, que teve a melhor detecção
neste vídeo e continua como padrão do `detectar_pessoas.py`. Depois do teste na pousada, o sistema
de monitoramento passou a usar o `yolo11s`.

### Outros testes

- Janela de exibição no Linux/Wayland: o programa rodou até o fim sem erros. Aparecem avisos do Qt
  (plugin "wayland" e fontes), que não impedem o funcionamento.
- `--fonte rtsp` sem `config/.env`: mensagem clara indicando as variáveis faltando.
- `--fonte rtsp` com DVR inexistente: erro tratado, senha mascarada no log.
- Arquivo inexistente: mensagem de erro clara.
- Senha com caracteres especiais (`@`, `:`): codificada corretamente na URL.

## Limitações conhecidas

- Se o IP do DVR não estiver reservado no roteador, ele pode mudar; nesse caso, é preciso atualizar
  `DVR_IP` no `config/.env`. O sistema avisa que a câmera ficou sem imagem.
- O decodificador de vídeo (FFmpeg) usa threads próprias, que não são limitadas por `--threads`.

## Próximos passos

1. Medir, ao longo de várias noites, as passagens detectadas e os falsos alarmes.
2. Avaliar a inclusão da área do café da manhã e da piscina.
