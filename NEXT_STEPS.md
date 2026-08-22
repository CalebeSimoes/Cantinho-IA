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
- Formulário mobile enxuto: Mensagem, Autor, Destino.
- View `Pendentes`.
- View `Processados hoje`.
- Cards/resumos de Finanças, Wishlist, Lugares, Calendário e Rotina.
- Caixa de Entrada IA no topo da Home.

## Fase 4 — confirmação/reprocessamento
Itens `Precisa confirmação` devem poder ser corrigidos no Notion e reenviados para a fila.

## Fase 5 — inicialização automática do Windows
Validar `start_cantinho_windows.ps1` e depois registrar no Agendador de Tarefas do Windows.

## Fase 6 — voz/mobile
Usar ditado do teclado do celular no próprio formulário do Notion.
