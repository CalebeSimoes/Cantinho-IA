ROUTER_PROMPT = """
Classifique a mensagem em exatamente um destino:
financas, wishlist, lugares, calendario, rotina ou desconhecido.

Pagamento/gasto/receita já ocorridos -> financas.
Desejo de compra futura -> wishlist.
Lugar/experiência desejada -> lugares.
Compromisso/evento com data -> calendario.
Tarefa/hábito -> rotina.

Retorne somente o schema.
"""

FINANCE_PROMPT = """
Extraia uma movimentação financeira.

REGRAS IMPORTANTES:
- Nunca invente valor.
- Se o valor não estiver presente, use valor=null, NÃO use 0.
- Se faltar valor, needs_confirmation=true e inclua "valor" em missing_fields.

Categorias:
restaurante/mercado/iFood=Alimentação;
Uber/99/ônibus=Transporte;
cinema/show=Lazer;
roupas/eletrônicos=Compras;
aluguel/contas=Moradia;
farmácia/consulta=Saúde;
hotel/passagem=Viagem;
demais=Outros.

Gasto=Saída.
Salário/recebi/reembolso=Entrada.
Já ocorreu=Pago.

Retorne somente o schema.
"""

WISHLIST_PROMPT = """
Extraia um desejo de compra.

Item é obrigatório.
Preço é opcional e nunca deve ser inventado.
Se não houver preço, use preco_estimado=null, NÃO use 0.

Tipos: Item, Presente, Casa, Tecnologia, Roupa, Outro.
Status padrão: Quero.

Retorne somente o schema.
"""

PLACE_PROMPT = """
Extraia um lugar ou experiência desejada.

O nome do lugar/experiência é obrigatório.
Tipos: Restaurante, Viagem, Passeio, Show, Hotel, Outro.

Data e valor são opcionais.
Se a mensagem não informar valor, use valor_estimado=null, NÃO use 0.
Se a mensagem não informar data, use data_planejada=null.
Nunca invente preço, data, link ou endereço.

Status padrão: Ideia.

Exemplo:
"Quero conhecer um restaurante japonês em São Paulo"
-> lugar="Restaurante japonês"
-> local="São Paulo"
-> tipo="Restaurante"
-> valor_estimado=null
-> data_planejada=null

Retorne somente o schema.
"""

CALENDAR_PROMPT = """
Extraia compromisso para calendário.

Evento e data são essenciais.
Interprete datas relativas usando a data atual informada.
Se faltar data:
- needs_confirmation=true
- inclua "data" em missing_fields
- use data=null

Nunca invente uma data.

Retorne somente o schema.
"""

ROUTINE_PROMPT = """
Extraia tarefa ou rotina.

Tarefa é obrigatória.
Categorias: Casa, Saúde, Estudo, Trabalho, Relacionamento, Outro.
Frequências: Diária, Semanal, Mensal, Pontual.

Retorne somente o schema.
"""
