# Próximos passos

## Fase 1 — validar a Caixa de Entrada
1. Enviar `Paguei 25 reais no Uber` pelo formulário do Notion.
2. Rodar `worker_once_windows.ps1`.
3. Conferir Status, Resultado e a base Finanças.

## Fase 2 — validar os cinco destinos
- Finanças: `Paguei 25 reais no Uber`
- Wishlist: `Quero comprar uma cafeteira de até 500 reais`
- Lugares: `Quero conhecer um restaurante japonês`
- Calendário: `Marcar cinema sábado`
- Rotina: `Toda semana precisamos limpar a cozinha`

## Fase 3 — melhorar a interface no Notion
- [x] Central `📱 Cantinho no celular` ligada no topo da Home.
- [x] Formulário de uma pergunta, com destino automático por padrão.
- [x] Views mobile para atenção, fila e últimos registros.
- [x] Listas compactas de Finanças, Wishlist, Lugares, Calendário e Rotina.

## Fase 4 — confirmação/reprocessamento
- [x] Itens `Precisa confirmação` podem ser corrigidos e reenviados ao mudar o Status para `Novo`.

## Fase 5 — Watchdog e inicialização automática do Windows
- [x] Heartbeat atômico do Worker.
- [x] Recuperação de Worker encerrado ou travado.
- [x] Recuperação do Ollama offline.
- [x] Limite de tentativas e cooldown contra loop de reinício.
- [x] Integração com status, reinício e Agendador de Tarefas.
- [x] Tarefa `Cantinho Ghibli AI` instalada e habilitada no Windows.

## Fase 6 — voz/mobile
- [x] Ditado pelo microfone do teclado no próprio formulário do Notion.
- [x] Uma única pergunta para reduzir toques no celular.
- [x] Atalho `Abrir registro` no retorno do Worker.
- [ ] Fazer o teste de usabilidade nos celulares do casal.

## Fase 7 — categorização semântica v2.8
- [x] Pontuação híbrida por intenção, ação, temporalidade e estado.
- [x] Diferenciar tarefa com prazo de evento de calendário.
- [x] Resolver datas relativas comuns em português brasileiro.
- [x] Parsers rápidos para Rotina e Calendário.
- [x] Inferir responsável entre Calebe, Carol e o casal.
- [x] Enriquecer prompts e fallback do Ollama.
- [x] Cobrir o pipeline com 132 testes offline.

## Fase 8 — Cantinho 2.0: perguntas v2.9
- [x] Criar a intenção `query` sem interferir nos registros existentes.
- [x] Interpretar domínio, operação, período, pessoa, termo e status.
- [x] Criar leitores paginados para as cinco bases do Notion.
- [x] Calcular totais, saldos, maiores valores, contagens e listas.
- [x] Salvar respostas no campo `Resultado` da Caixa de Entrada.
- [x] Garantir que consultas nunca criem páginas nos destinos.
- [x] Testar frases complexas e pares equivalentes de registro/consulta.
- [x] Validar 169 testes offline e consultas reais somente de leitura.

## Fase 9 — Ações múltiplas (Fase 7 do Cantinho 2.0)
- [x] Trocar efeito único por planos estruturados `actions[]`.
- [x] Integrar Wishlist + Finanças, Lugares + Calendário e viagens.
- [x] Exigir prévia e confirmação antes de ações cruzadas.
- [x] Criar IDs estáveis, marcadores no Notion e retomada parcial.
- [x] Impedir duplicação mesmo após queda entre escrita e checkpoint.
- [x] Preservar horário e impedir invenção de data de calendário.

## Fase 10 — Rotina inteligente (Fase 8 do Cantinho 2.0)
- [x] Interpretar todo dia, dia semanal, quinzenal, mensal, dias úteis e fim de semana.
- [x] Persistir a regra exata de recorrência.
- [x] Consultar hoje, pendências da Carol e tarefas da casa atrasadas.
- [x] Concluir tarefas por frase natural e localizar por similaridade.
- [x] Avançar tarefas recorrentes para a próxima ocorrência.
- [x] Criar Overview nativo com cinco widgets e atalhos mobile/Home.
- [x] Validar 218 testes e Ollama real com schema multi tipado.
