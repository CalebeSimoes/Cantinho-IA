# v3.0 - Rotina inteligente, actions[] e Overview

- Recorrências: diária, dia semanal, quinzenal, mensal, dias úteis e fim de semana.
- Padrão canônico persistido e cálculo da próxima ocorrência.
- Conclusão por linguagem natural com correspondência contextual de tarefas.
- Tarefas recorrentes avançam a data sem duplicar páginas.
- Consultas de tarefas de hoje, pendências por pessoa e atrasos por categoria.
- Horários de calendário preservados com timezone de São Paulo.
- Planner `actions[]` para uma frase produzir múltiplos efeitos.
- Compra da wishlist, reserva datada e compra de passagens cobertas.
- Prévia obrigatória e confirmação na mesma linha da Caixa de Entrada.
- Transação recuperável com progresso por ação e replay idempotente.
- Coluna `Origem IA` nas bases para recuperação após falha de processo.
- Schema tipado do Ollama por destino; enums livres são rejeitados e reparados.
- Dashboard nativo do Notion com cinco widgets e atalhos Home/mobile.
- Migração de schema e dashboard idempotente em `scripts/setup_v30_notion.py`.
- Suite completa ampliada para 218 testes aprovados.

# v2.9 - Cantinho 2.0: perguntas e consultas

- Nova intenção `query`, separada dos cinco destinos de escrita.
- A mesma Caixa de Entrada agora registra frases e responde perguntas.
- Parser contextual de consultas com domínio, operação, período, pessoa,
  termo, status e tipo de movimentação.
- Leitores para Finanças, Wishlist, Lugares, Calendário e Rotina.
- Paginação completa da API do Notion com proteção de cursor e limite.
- Filtros e cálculos locais: total, saldo, maior valor, contagem e listagem.
- Valores formatados em real e respostas limitadas ao campo `Resultado`.
- Perguntas não criam páginas e resultados vazios são respostas válidas.
- Classificador ampliado para perguntas indiretas e verbos na terceira pessoa.
- Linhas antigas sem título são ignoradas pelos leitores.
- Suite completa ampliada para 169 testes aprovados.
- Fluxo real validado em modo somente leitura nas cinco bases do Notion.

# v2.8 - Classificador semantico e datas relativas

- Router Python trocado por pontuacao semantica com evidencias e margem.
- Tarefas com prazo nao sao mais confundidas com eventos de calendario.
- Contraste entre `quero assinar`, `preciso assinar` e `assinei` coberto.
- Novo parser deterministico para Rotina e Calendario.
- Datas relativas: hoje, amanha, dias da semana, dia N e fim do mes.
- Responsavel inferido por Calebe/Caleb, Carol, autor ou linguagem conjunta.
- Prompts do Ollama ampliados com exemplos negativos e confianca obrigatoria.
- Contexto do modelo aumentado para 4096 tokens com geracao deterministica.
- Fallback do Ollama passa a receber evidencias calculadas pelo Python.
- Suite completa ampliada para 132 testes aprovados.

# v2.7 - Experiencia mobile

- Nova pagina `📱 Cantinho no celular` ligada no topo da Home do Notion.
- Formulario de uma pergunta, otimizado para digitacao ou ditado por voz.
- Views compactas para pendencias, fila, ultimos registros e as cinco areas.
- Resultados processados agora incluem o link clicavel `Abrir registro`.
- Links externos do resultado sao aceitos apenas com `http://` ou `https://`.
- Testes offline protegem a renderizacao do link e o contrato com o Worker.
- Suite completa ampliada para 65 testes aprovados.

# v2.6 - Watchdog e autorrecuperacao

- Worker publica heartbeat atomico em `logs/worker-heartbeat.json`.
- Falhas gerais transitorias de Notion/rede nao encerram mais o loop do Worker.
- Novo Watchdog supervisiona Worker e Ollama em background.
- Worker ausente ou sem heartbeat recente e reiniciado automaticamente.
- Ollama offline e recuperado pelo fluxo de inicializacao existente.
- Limite de recuperacoes por janela e cooldown evitam tempestades de reinicio.
- Estado operacional em `logs/watchdog-state.json` e eventos em `logs/watchdog.log`.
- Agendador do Windows agora executa o Watchdog de longa duracao.
- Scripts de status, inicio, reinicio e parada integrados ao supervisor.
- Corrigida a espera da recuperacao para nao acompanhar o Worker filho permanente.

# v2.5 - Testes e correcoes automaticas

- Suite offline com 59 testes de regressao.
- Corrigido `NUMBER_PATTERN` ausente nos parsers de Wishlist e Lugares.
- Router financeiro nao depende mais de valor numerico para identificar um gasto; valor ausente vai para confirmacao.
- Removido falso gatilho generico `" as "` do Calendario; horario agora usa regex especifica.
- Ollama faz uma segunda tentativa automatica quando a resposta estruturada e invalida.
- Roteamento automatico de baixa confianca nao grava no Notion.
- Casos `Precisa confirmacao` e `Erro` sao salvos em `logs/learning_cases.jsonl`.
- Adicionado `test_cantinho.ps1`, `requirements-dev.txt` e relatorio de aprendizado.
- Modelo padrao/documentado atualizado para `qwen3:4b`.
- `status_cantinho.ps1` agora conta Workers logicos, evitando falso aviso do wrapper da `.venv`.

# v2.3

Correcao estrutural de encoding e schema do Notion:

- Os writers nao usam mais nomes acentuados hardcoded.
- O codigo busca o schema real do Notion e resolve nomes de propriedades
  ignorando acentos e diferencas de espacos ao redor de "/".
- Corrige definitivamente casos como:
  - Lugar / Experiencia -> Lugar / Experiencia (nome real com acento)
  - Descricao -> Descricao (nome real com acentos)
  - Observacao
  - Preco estimado
  - Frequencia
  - Responsavel
  - Dia / Data
- Adicionado `python -m scripts.test_property_mapping`.
- Mantidas as correcoes de valores opcionais da v2.1.

# v2.2

Correções baseadas no schema real do Notion:
- Lugares: `Lugar/Experiência` -> `Lugar / Experiência`.
- Rotina: `Dia/Data` -> `Dia / Data`.
- Mantidas as correções v2.1 para valores opcionais `0 -> None`.
- Adicionado `scripts.audit_notion_schema` para facilitar futuras validações.

# v2.1

Correções:
- Campos monetários opcionais agora tratam 0/negativo como `None`.
- Evita ValidationError quando o Qwen usa 0 para representar valor desconhecido.
- FinanceAction também ficou robusto para valor ausente.
- Prompts reforçam que preço desconhecido deve ser `null`, nunca 0.
- Adicionado `python -m scripts.test_place`.
