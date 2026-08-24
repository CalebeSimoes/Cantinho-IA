# 🌿 Cantinho Ghibli AI v3.0

A v2 usa o **Notion como interface mobile** e o PC como processador local.

```text
Notion Form / celular
   ↓
✨ Caixa de Entrada IA
   ↓
worker.py
   ↕ heartbeat
Watchdog local
   ├ recupera Worker travado/encerrado
   └ recupera Ollama offline
   ↓
router híbrido (Python + Ollama tipado)
   ├→ REGISTRAR → Finanças | Wishlist | Lugares | Calendário | Rotina
   ├→ PLANEJAR → actions[] → confirmar → transação idempotente
   └→ CONSULTAR → leitores → filtros/cálculos
   ↓
Resultado volta para a Caixa de Entrada
```

## Uso no celular

Abra a pagina
[📱 Cantinho no celular](https://app.notion.com/p/3c5e855068c581e086b6c05b5d4f810d)
ou use o atalho verde no topo da Home.

Use o atalho **Adicionar uma mensagem agora**, toque em **Novo** e digite ou
dite no campo `Mensagem`. Ao voltar, o Worker pega o item automaticamente.
O bloco de formulario e apenas o editor; o formulario com botao `Enviar`
precisa ser aberto em `Pre-visualizar` e compartilhado pelo Notion no PC.

Depois do processamento, `Resultado` mostra a resposta da consulta ou um
atalho clicavel para abrir o registro criado.

## Cantinho 2.0 — perguntas v2.9

A mesma caixa agora aceita tanto registros quanto perguntas:

- `Paguei 30 no Uber` → cria uma saída em Finanças.
- `Quanto gastei com Uber esse mês?` → lê Finanças e devolve o total.
- `O que temos marcado para sábado?` → lê o Calendário.
- `Quais lugares queremos conhecer?` → lista ideias ainda ativas.
- `Qual item mais caro da wishlist?` → compara os preços informados.

As consultas entendem período, pessoa, termo, status e operação. Os leitores
paginam todas as linhas das cinco bases; perguntas nunca criam uma página de
destino e a resposta fica registrada no campo `Resultado`.

## Rotina inteligente v3.0

A Rotina funciona como um pequeno Todoist por linguagem natural:

- `Lavar banheiro toda sexta` → Semanal, próxima sexta.
- `Tomar vitamina nos dias úteis` → próxima ocorrência útil.
- `Limpar geladeira quinzenalmente` → intervalo de 14 dias.
- `O que tenho para fazer hoje?` → tarefas abertas de hoje.
- `O que a Carol tem pendente?` → filtro de responsável e status.
- `Quais tarefas da casa estão atrasadas?` → prazo vencido + categoria Casa.
- `Terminei de lavar a louça` → conclui a tarefa correspondente.

Ao concluir uma tarefa recorrente, o Cantinho registra a conclusão e avança
automaticamente para a próxima ocorrência, sem criar duplicatas.

## Múltiplas ações com confirmação

Frases com efeitos cruzados geram `actions[]` antes de qualquer escrita:

- `Comprei o fone da wishlist por 350 reais` → Wishlist + Finanças.
- `Reservei o restaurante italiano para sábado às 20h` → Lugares + Calendário.
- `Compramos passagem para Campos do Jordão por 600` → Finanças + Lugares;
  Calendário só é incluído quando uma data foi informada.

O campo `Resultado` mostra a prévia. Para executar, acrescente `confirmar` à
mesma `Mensagem` e mude o `Status` para `Novo`. Para desistir, substitua a
mensagem por `cancelar` e volte o status para `Novo`.

Cada efeito possui ID estável e marcador `Origem IA`. Se o PC ou a rede falhar
no meio, o worker continua do ponto seguro sem repetir o que já foi aplicado.

## Overview no Notion

O dashboard nativo reúne tarefas abertas, próximos compromissos, movimentações,
wishlist e lugares: [🌿 Abrir Overview do Cantinho](https://app.notion.com/p/517b09965cb3404787a56fcfe1dfd367?v=3c5e855068c5810e9a54000cab2dcc1c).

Há atalhos para ele na Home e na página mobile.

## Interpretação semântica v3.1

O Router combina pontuação Python e Ollama. Frases comuns são resolvidas
localmente com baixa latência; ambiguidades reais recebem uma segunda análise
do modelo com as evidências encontradas pelo Python.

Exemplos:

- `Assinei HBO por 30 reais` → Finanças.
- `Quero assinar HBO` → Wishlist.
- `Calebe precisa comprar um micro-ondas até sexta, de até 300 reais`
  → Wishlist, status Planejando, responsável, prazo e teto de preço.
- `Comprar ração toda segunda-feira` → Rotina recorrente.
- `Me lembre de comprar ração sexta` → Rotina pontual.
- `Pesquisar preços antes de comprar um notebook` → Rotina pontual.
- `Calebe precisa assinar HBO final do mes` → Rotina, prazo no último dia do mês.
- `Cinema sábado às 20h` → Calendário.
- `Quero conhecer o MASP` → Lugares.

Uma data pode ser prazo de tarefa ou data desejada de compra e não força o
destino Calendário. Compras futuras vão para a Wishlist; compras realizadas
com valor vão para Finanças. Números de capacidade, quantidade ou voltagem não
são tratados como preço sem contexto monetário.

A Wishlist v3.1 mantém `Preço estimado` por compatibilidade e acrescenta
`Relação do preço` (Máximo, Aproximado, Exato ou Mínimo) e `Responsável`.

## Arquivos novos principais

- `app/worker.py`: verifica pendências automaticamente.
- `app/health.py`: publica o heartbeat atômico do Worker.
- `watchdog_cantinho.ps1`: supervisiona Worker e Ollama continuamente.
- `start_watchdog_background.ps1`: inicia o Watchdog sem abrir janela.
- `stop_cantinho.ps1`: encerra Watchdog e Worker com segurança.
- `app/processor.py`: orquestra cada mensagem.
- `app/ai/router.py`: escolhe o destino.
- `app/ai/date_utils.py`: resolve datas relativas em português.
- `app/ai/parsers.py`: extrai os campos.
- `app/notion/inbox.py`: lê/atualiza a Caixa de Entrada IA.
- `app/notion/writers.py`: grava nas cinco bases.
- `app/notion/readers.py`: lê e normaliza as cinco bases com paginação.
- `app/ai/query_parser.py`: transforma perguntas em planos estruturados.
- `app/query_service.py`: filtra, calcula e redige as respostas.
- `app/ai/recurrence.py`: interpreta e avança padrões recorrentes.
- `app/routine_service.py`: localiza e conclui tarefas por linguagem natural.
- `app/ai/action_planner.py`: cria planos tipados `actions[]`.
- `app/action_executor.py`: executa planos recuperáveis e idempotentes.
- `app/action_store.py`: persiste confirmação e progresso de transações.
- `scripts/setup_v30_notion.py`: migra schemas e mantém o dashboard.
- `run_worker_windows.ps1`: roda só o worker.
- `worker_once_windows.ps1`: processa a fila uma vez.
- `start_cantinho_windows.ps1`: inicia Ollama, worker e API.

## 1. Configurar

Edite `.env` e preserve o seu token real:

```env
NOTION_TOKEN=ntn_...
```

A v2 já vem com os Data Source IDs das seis bases deste projeto.

## 2. Instalar

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_windows.ps1
```

## 3. Testar

```powershell
.\testar_windows.ps1
```

## 4. Primeiro teste do worker

No formulario `✨ Registrar por texto ou voz` do Notion, envie:

`Paguei 25 reais no Uber`

Depois:

```powershell
.\worker_once_windows.ps1
```

Esperado:
- item da Caixa de Entrada -> `Processado`;
- `Resultado` preenchido com o link `Abrir registro`;
- nova linha em `💸 Finanças do Casal`.

## 5. Rodar continuamente

```powershell
.\run_worker_windows.ps1
```

Ele verifica a Caixa de Entrada a cada 10 segundos.

Para o modo supervisionado recomendado:

```powershell
.\start_watchdog_background.ps1
.\status_cantinho.ps1
```

O Watchdog verifica o Worker e o Ollama a cada 15 segundos. Um Worker sem
heartbeat por 90 segundos é considerado travado e reiniciado. Há um limite de
5 recuperações em 10 minutos, seguido de 5 minutos de cooldown, para evitar
loops de reinício.

## 6. API/Swagger (opcional)

```powershell
.\run_api_windows.ps1
```

Abra `http://127.0.0.1:8000/docs`.

## 7. Iniciar tudo depois

```powershell
.\start_cantinho_windows.ps1
```

Para registrar o Watchdog no login do Windows, execute uma vez:

```powershell
.\install_cantinho_startup_v2.ps1
```

Comandos operacionais:

```powershell
.\status_cantinho.ps1   # diagnostico completo
.\restart_cantinho.ps1  # reinicia Watchdog e Worker
.\stop_cantinho.ps1     # para Watchdog e Worker; preserva o Ollama
```

Os limites podem ser ajustados no `.env` por
`WATCHDOG_CHECK_SECONDS`, `WATCHDOG_WORKER_STALE_SECONDS`,
`WATCHDOG_MAX_RECOVERIES`, `WATCHDOG_RECOVERY_WINDOW_SECONDS` e
`WATCHDOG_COOLDOWN_SECONDS`.

O Notion continua recebendo anotações quando o PC está desligado; elas ficam pendentes e serão processadas quando o worker voltar.
