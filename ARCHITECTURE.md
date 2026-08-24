# Arquitetura v3.0

```text
Notion Mobile/Form
       ↓
✨ Caixa de Entrada IA
       ↓ polling
Watchdog (Windows)
 ├ verifica Ollama /api/tags
 ├ observa heartbeat e processo
 ├ limita recuperacoes/cooldown
 └ supervisiona app/worker.py
                 ↓
           app/worker.py
       ↓
app/processor.py
       ↓
Router
 ├ pontuacao semantica Python
 ├ resolucao de datas relativas
 ├ parsers deterministicos por destino
 └ Ollama com evidencias (fallback ambiguo)
       ├→ registrar → Notion writers → cinco bases
       ├→ actions[]
       │      ↓
       │  prévia / confirmação
       │      ↓
       │  executor idempotente
       │   ├ checkpoint local por ação
       │   └ marcador Origem IA no Notion
       └→ consultar
             ↓
      query_parser.py
             ↓
      notion/readers.py (paginado)
             ↓
      query_service.py
       ├ filtros contextuais
       ├ total / saldo / max / contagem
       └ listas resumidas
       ↓
Resultado (e link apenas quando houve registro)
```

Regra: o Notion é a interface/fila persistente; o worker é o motor; Ollama só entra quando as regras simples não resolvem. O Watchdog cuida apenas da disponibilidade local e nunca grava diretamente no Notion.

Consultas são estritamente somente leitura. O Router identifica a pergunta,
o parser cria um plano estruturado e o serviço consulta todas as páginas da
base escolhida. A resposta volta para a própria linha da Caixa de Entrada;
nenhum writer é chamado nesse ramo.

Rotinas carregam `recurrence_rule`, uma representação estável independente do
texto original. Uma conclusão pontual muda o status; uma conclusão recorrente
grava `Última conclusão` e calcula a próxima data.

Planos múltiplos nunca executam na primeira passagem. O worker persiste o plano
por ID da linha da Caixa de Entrada. Após confirmação, valida todas as ações e
faz checkpoints individuais. O marcador remoto cobre a janela entre a criação
de uma página e o checkpoint local, tornando a retomada segura.

O classificador diferencia estado e intencao. `Assinei HBO` e uma movimentacao
ja realizada; `quero assinar HBO` e um desejo; `preciso assinar HBO no fim do
mes` e uma tarefa pontual com prazo. Datas so levam ao Calendario quando a
frase descreve um evento ou compromisso.

O Worker publica `logs/worker-heartbeat.json` ao iniciar e após cada ciclo. O
Watchdog considera saudável apenas um processo lógico com heartbeat recente;
um heartbeat degradado continua vivo para permitir recuperação de falhas
transitórias sem reinícios desnecessários.
