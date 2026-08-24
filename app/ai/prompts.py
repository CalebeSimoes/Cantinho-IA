ROUTER_PROMPT = """
Classifique a mensagem em exatamente um destino:
query, financas, wishlist, lugares, calendario, rotina ou desconhecido.

DISTINCOES OBRIGATORIAS:
- query: pergunta que pede para ler, listar, contar, comparar ou calcular
  informacoes ja registradas. Nunca trate uma pergunta como novo registro.
- financas: dinheiro que ja entrou ou saiu. Ex.: "paguei a internet".
- wishlist: aquisicao futura, desejada ou necessaria. Ex.: "quero assinar
  HBO" ou "preciso comprar um micro-ondas ate 300 reais".
- lugares: desejo de conhecer/visitar um lugar ou experiencia.
- calendario: evento ao qual alguem comparece, reserva ou compromisso.
- rotina: acao que alguem precisa executar, com ou sem prazo/recorrencia.

Uma data nao transforma automaticamente uma tarefa em calendario.
"Calebe precisa assinar HBO no final do mes" -> rotina.
"Separar os documentos importantes" -> rotina, pois e uma acao direta.
"Preciso pagar a internet dia 10" -> rotina, pois o pagamento ainda e tarefa.
"Quero assinar HBO" -> wishlist.
"Assinei HBO por 30 reais" -> financas.
"Cinema sabado as 20h" -> calendario.
"Quero conhecer o MASP" -> lugares.
"Lavar banheiro toda sexta" -> rotina.
"Tenho que comprar pao" -> wishlist, pois e uma aquisicao futura.
"Comprar pao toda segunda" -> rotina, pois a compra e recorrente.
"Me lembre de comprar pao sexta" -> rotina, pois o ato principal e lembrar.
"Pesquisar precos antes de comprar um notebook" -> rotina.
"Comprei pao por 20 reais" -> financas.
"Visitar o MASP" -> lugares.
"Ir ao dentista terca as 9h" -> calendario.
"Quanto gastei com Uber este mes?" -> query.
"O que temos marcado para sabado?" -> query.
"Quais lugares queremos conhecer?" -> query.
"Qual item mais caro da wishlist?" -> query.

Preencha confidence obrigatoriamente entre 0 e 1:
- 0.90 a 1.00: intencao clara;
- 0.70 a 0.89: melhor destino com pequena ambiguidade;
- abaixo de 0.55: realmente nao ha informacao suficiente.

Use desconhecido apenas quando nenhum destino for defensavel.
Explique a distincao em reason, em uma frase curta.

Retorne somente o schema.
"""

QUERY_PROMPT = """
Extraia o plano de uma pergunta sobre dados ja registrados no Notion.

Dominios: financas, wishlist, lugares, calendario, rotina, desconhecido.
Operacoes:
- total: somar valores;
- max: encontrar o maior/mais caro;
- count: contar;
- list: listar registros;
- summary: resumir entradas, saidas e saldo.

Periodos: all, today, this_week, this_month, last_month, next_month,
specific_date. Para specific_date, preencha specific_date.

Em rotina, reconheca categoria Casa e os estados Pendentes/Atrasadas.
"O que tenho para fazer hoje?" e rotina, today, Eu, Pendentes.
"Quais tarefas da casa estao atrasadas?" e rotina, Casa, Atrasadas.

Pessoa:
- Calebe/Caleb/eu/meu -> Eu;
- Carol/minha esposa -> Minha esposa;
- "nos/nosso/nossa/gastamos/temos" representa a casa inteira: person=null;
- use Nos dois apenas se a pergunta pedir registros marcados exatamente
  como responsabilidade/pagamento conjunto.

Em financas, use transaction_type=Saida para gastos e Entrada para
recebimentos. Fora de financas, transaction_type deve ser null.
Nao invente termo, pessoa, status ou data.
Se o dominio realmente nao puder ser identificado, use desconhecido,
needs_confirmation=true e inclua "domain" em missing_fields.

Retorne somente o schema.
"""

MULTI_ACTION_PROMPT = """
Transforme uma frase com dois ou mais efeitos reais em actions[].

Cada ação possui:
- operation: create, update ou complete;
- destination: financas, wishlist, lugares, calendario ou rotina;
- subject: entidade curta e específica;
- payload: campos do schema do destino;
- sensitive=true para qualquer escrita/atualização.

REGRAS:
- Nunca invente valor, data, hora, lugar ou item.
- Uma compra de item da wishlist gera update wishlist=Comprado + create financas.
- Uma reserva de lugar com data gera update lugares=Reservado + create calendario.
- Passagem comprada gera financas + lugares; calendario somente se houver data.
- "tenho que comprar" é compra planejada na wishlist, não compra realizada.
- "quero comprar" é wishlist, não finanças.
- Use no máximo uma ação por efeito; não duplique destinos sem necessidade.
- requires_confirmation=true.

Payloads usam os mesmos nomes dos schemas individuais, por exemplo:
financas: movimento, valor, tipo="Saída", categoria em Moradia/Alimentação/
Transporte/Lazer/Compras/Saúde/Viagem/Outros, pago_por em Eu/Minha esposa/
Nós dois, status em Pago/Pendente, data, observacao;
calendario: evento, data, hora, quem, status, tipo, local, observacao;
wishlist: item, status, preco_estimado, preco_relacao, data_desejada,
responsavel;
lugares: lugar, status, data_planejada, tipo, local, descricao;
rotina: tarefa, dia_data, frequencia, recurrence_rule, responsavel, status.

Exemplo:
"Comprei o fone da wishlist por 350 reais"
1. update wishlist, payload item="fone", status="Comprado",
   preco_estimado=350
2. create financas, payload movimento="Fone", valor=350, tipo="Saída",
   categoria="Compras", pago_por="Eu", status="Pago", data=data atual

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
Extraia uma compra futura, desejada ou necessaria.

Item é obrigatório.
Preço é opcional e nunca deve ser inventado.
Se não houver preço, use preco_estimado=null, NÃO use 0.
Interprete "ate 300 reais" como preco_relacao="Máximo".
Interprete "por volta de 300" como "Aproximado", "exatamente 300"
como "Exato" e "a partir de 300" como "Mínimo".
Datas representam data_desejada, nao evento de calendario.
Use status="Planejando" para preciso/tem que/vou/planejo comprar e
status="Quero" para quero/gostaria/talvez comprar.
Responsavel: autor/Calebe/Caleb/eu -> Eu; Carol/minha esposa ->
Minha esposa; nos/precisamos/vamos -> Nós dois.

Tipos: Item, Presente, Casa, Tecnologia, Roupa, Outro.
Nao confunda capacidade, quantidade ou voltagem com preco.

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

Calendario representa algo que acontece em uma data: consulta, reuniao,
cinema, jantar, aniversario, viagem, reserva ou evento.

Nao use calendario para uma acao a executar ate uma data. Exemplos:
"preciso assinar HBO ate o fim do mes" e tarefa, nao evento.
"preciso pagar a conta dia 10" e tarefa, nao evento.

Evento e data sao essenciais.
Se houver horario explicito como "as 20h" ou "20:30", preencha hora.
Interprete datas relativas usando a data atual informada, incluindo hoje,
amanha, dias da semana, fim do mes e datas numericas.
Se faltar data:
- needs_confirmation=true
- inclua "data" em missing_fields
- use data=null

Nunca invente uma data.

Retorne somente o schema.
"""

ROUTINE_PROMPT = """
Extraia tarefa ou rotina.

Tarefa e uma acao que alguem precisa executar. Ela pode ter prazo sem ser
recorrente. Exemplo: "Calebe precisa assinar HBO final do mes" significa:
- tarefa="assinar HBO"
- dia_data=ultimo dia do mes informado pela data atual
- frequencia="Pontual"
- responsavel="Eu" quando Calebe/Caleb for o usuario
- categoria="Outro"

"Final do mes" e prazo pontual. So use Mensal quando houver recorrencia
explicita como "todo mes" ou "mensalmente".

Comprar/adquirir algo no futuro pertence a Wishlist, mesmo quando a frase
usa preciso/tem que. Use Rotina para compra recorrente, lembrete de compra
ou tarefa preparatoria como pesquisar, comparar e cotar precos.

Responsavel:
- autor/Calebe/Caleb/eu -> Eu
- Carol/minha esposa -> Minha esposa
- nos/precisamos/temos que -> Nos dois

Categorias: Casa, Saude, Estudo, Trabalho, Relacionamento, Outro.
Frequencias e regras:
- todo dia -> Diaria, recurrence_rule="daily";
- toda terca -> Semanal, recurrence_rule="weekly:1";
- quinzenalmente -> Quinzenal, recurrence_rule="biweekly";
- uma vez por mes -> Mensal, recurrence_rule="monthly:DIA";
- dias uteis -> Dias uteis, recurrence_rule="weekdays";
- fim de semana -> Fim de semana, recurrence_rule="weekends";
- sem repeticao -> Pontual, recurrence_rule="once".
Data e opcional; nunca invente uma data sem expressao temporal.

Retorne somente o schema.
"""
