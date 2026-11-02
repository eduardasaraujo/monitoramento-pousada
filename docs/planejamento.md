# Planejamento do projeto — Monitoramento Noturno da Pousada Porto Verano

_Atualizado em 01/11/2026, véspera da primeira visita. O prazo de entrega ainda não foi definido,
então as etapas depois da visita não têm datas fixas._

## Onde o projeto está

**Pronto e testado:**
- sistema de 1 câmera: horário, área de interesse, confirmação em vários quadros, alertas com foto,
  reconexão automática, aviso de câmera sem imagem, início automático com o computador;
- alertas pelo Telegram funcionando com o bot real (`@porto_verano_bot`);
- ferramentas para a visita: coleta das câmeras, instalador, medidor de desempenho;
- pacote enviado para as Mensagens salvas do Telegram.

**Ainda não testado** (só dá para testar na pousada): conexão RTSP com o DVR real, imagem noturna
infravermelha real e desempenho no notebook real.

## Dá para fazer tudo amanhã?

**Dá para deixar o sistema instalado e funcionando amanhã**, com 1 câmera e alertas no Telegram,
se as condições da tabela abaixo se confirmarem.

**Não dá para concluir o projeto amanhã.** O que impede não é programação, é tempo de calendário:

1. **A primeira noite real só acontece depois que você sair.** A visita é de dia, então o
   funcionamento noturno (infravermelho, horário, alertas) só pode ser confirmado à noite, de casa,
   pelo Telegram.
2. **Avaliar a qualidade exige várias noites:** quantos alertas falsos por noite e quantas
   passagens o sistema deixa de ver. Uma noite só não é uma amostra.
3. **Os ajustes dependem desses dados:** confiança, área e confirmação são ajustados depois de ver
   os resultados.
4. **Há decisões que não dependem de você:** o WhatsApp oficial depende de aprovação da Meta, e as
   outras 2 câmeras dependem do desempenho real e de uma decisão da pousada.
5. **O relatório e a apresentação** só podem ser feitos com os dados do piloto.

## Condições para amanhã dar certo (confirmar logo cedo)

| Condição | Se não acontecer |
|---|---|
| Dono autoriza **formatar o notebook** (ou não há nada importante nele) | Instalar o Linux **ao lado** do Windows, com backup antes; ou só coletar material e deixar a instalação para a 2ª visita |
| Senha de **administrador do DVR** | Sem ela não há RTSP nem exportação de gravações. Pedir ao dono ou ao técnico das câmeras |
| **RTSP funciona** (passo 2 do roteiro) | Verificar no menu de rede do DVR se o RTSP está habilitado e a porta 554. Se não resolver, coletar as gravações e deixar o sistema para depois |
| DVR e notebook na **mesma rede** | Usar cabo de rede no mesmo roteador do DVR |
| **Internet** no notebook da pousada | Necessária para a instalação (~1 GB) e para o Telegram |
| Equipe aceita o **Telegram** | Alertas vão só para você durante os testes; o WhatsApp fica como evolução |
| Linux instala e reconhece a rede | Cabo de rede; se falhar, reinstalar a partir do pendrive (por isso só formatar o pendrive no fim) |

## Roteiro de amanhã (cerca de 5 a 7 horas)

**Levar:** notebook com carregador, o pendrive (Linux), cabo de rede se tiver, celular com
Telegram, este plano. O token e o chat id estão nas Mensagens salvas.

1. **Conversa com o dono (30 min).**
   - Autorizações: formatar o notebook, usar a câmera, fotos nos alertas (LGPD), Telegram e
     acesso remoto.
   - Definir **qual câmera**, o horário e quem recebe os alertas.
   - Senha do DVR e criação de um usuário só de visualização.
2. **Teste do RTSP, no seu notebook (30 min). É o marco mais importante do dia.**
   - Rede da pousada e `config/.env` com os dados do DVR.
   - `coletar_cameras.py --canais 1-8 --segundos 5` para achar o canal.
   - `--canais N --segundos 60` no canal escolhido.
   - `detectar_pessoas.py --fonte rtsp --canal N` com alguém passando.
3. **Instalar o Linux no notebook da pousada (1 a 1,5 h).** Enquanto instala, crie o grupo do
   Telegram com o celular da recepção e converse com a equipe.
4. **Gravações noturnas (30 min).** Só depois que o Linux iniciar sozinho, sem o pendrive:
   formatar o pendrive (app Discos, FAT/exFAT), exportar do DVR as noites anteriores dessa câmera,
   com e sem gente passando (em MP4 se houver a opção), e copiar para o seu notebook.
5. **Instalar o sistema (30 a 45 min).**
   - Baixar o pacote pelo web.telegram.org e rodar `scripts/instalar.sh`.
   - Preencher o `config/.env` (DVR + Telegram) e o `config/monitoramento.yaml` (ambiente, canal,
     horário).
6. **Área e teste real (20 min).**
   - `desenhar_area.py --canal N`, contornando o chão.
   - `monitorar.py --testar-alerta`.
   - `monitorar.py --ignorar-horario --janela`, com alguém passando **dentro** da área (tem que
     alertar) e **fora** dela (não pode alertar).
7. **Grupo da equipe (15 min).** Adicionar o bot ao grupo, enviar `/start@porto_verano_bot`, pegar
   o id do grupo no `getUpdates` (começa com `-`), colocar no `.env` e repetir o `--testar-alerta`.
8. **Deixar rodando (20 min).**
   - `scripts/instalar_servico.sh` e os comandos de não suspender que ele mostra.
   - Reiniciar o notebook e conferir se o serviço voltou sozinho.
   - Sair da sua conta do Telegram Web.
9. **Desempenho real, se der tempo (15 min):** `scripts/medir_desempenho.sh`.
10. **Orientar a equipe (15 min).**
    - O que fazer ao receber um alerta.
    - A mensagem "Monitoramento INICIADO" chega no começo do horário.
    - Manter o notebook ligado na tomada.
    - Como falar com você se algo parar.

**Checklist antes de ir embora:**
- [ ] serviço ativo depois de reiniciar o notebook;
- [ ] alerta de teste chegou no grupo;
- [ ] área desenhada;
- [ ] horário certo;
- [ ] gravações noturnas copiadas;
- [ ] resultados da coleta e do desempenho no seu notebook;
- [ ] equipe orientada.

## Depois de amanhã (de casa, comigo)

| Etapa | O que fazer | Duração |
|---|---|---|
| A. Primeiras noites | Conferir se chegam "INICIADO" e "ENCERRADO" e se os alertas fazem sentido | 1–2 noites |
| B. Avaliação com as gravações | Eu preparo um script de avaliação. Rodamos o sistema nas gravações noturnas reais e medimos detecção por evento e falsos alarmes; depois ajustamos confiança, área e confirmação | algumas horas |
| C. Piloto | Anotar todo dia, numa planilha simples: alertas recebidos, quantos eram reais (pela foto ou perguntando à equipe), noites com problema | 1–2 semanas, conforme o prazo |
| D. Ajustes | Com acesso remoto, eu aplico daqui. Sem ele, cada ajuste exige ir à pousada (por isso o acesso remoto vale tanto) | conforme necessário |
| E. Entrega acadêmica | Relatório: arquitetura, decisões, métricas (detecção por evento, falsos alarmes por noite, tempo até o alerta, tempo no ar) e opinião da equipe. Mais a apresentação e o repositório atualizado | depois do piloto |

**2ª visita (se acontecer):** aplicar os ajustes, conferir as fotos dos alertas com a equipe e
coletar mais gravações.

**Fica para depois, fora do escopo atual:**
- as outras 2 câmeras: um único processo compartilhando o modelo, depois de medir o desempenho real;
- WhatsApp oficial;
- passar a posse do bot para a conta da pousada;
- ByteTrack, se a confirmação simples não bastar.

## Quando o projeto estará concluído
- [ ] sistema rodando na pousada há pelo menos uma semana sem precisar de intervenção;
- [ ] taxa de detecção e de falsos alarmes medidas com imagens reais;
- [ ] equipe recebendo e usando os alertas, e aprovando o uso;
- [ ] relatório e apresentação com esses dados;
- [ ] repositório atualizado.

## Riscos principais
- **Imagem infravermelha ruim:** mais falsos alarmes ou perdas. Mitigação: as etapas B e D.
- **Notebook desligado pela equipe ou por falta de energia:** o serviço volta sozinho quando o
  notebook liga, mas alguém precisa ligá-lo. A falta da mensagem "INICIADO" denuncia o problema.
- **Equipe não aderir ao Telegram:** rever o canal de alertas.
