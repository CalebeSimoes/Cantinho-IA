"""A fixed, deterministic corpus of 400 messages commonly used by a couple.

The corpus is generated from scenario families so it stays readable in code while
still exposing the evaluator to 400 concrete, unique messages.  Nothing in this
module contacts Ollama or Notion.
"""

from __future__ import annotations

from collections import Counter
from typing import TypedDict


class EvalCase(TypedDict):
    id: str
    message: str
    author: str
    expected: str
    scenario: str


def _expand(
    prefix: str,
    expected: str,
    bases: list[str],
    suffixes: list[str],
) -> list[EvalCase]:
    cases: list[EvalCase] = []
    for base_index, base in enumerate(bases):
        for suffix_index, suffix in enumerate(suffixes):
            number = len(cases) + 1
            cases.append(
                {
                    "id": f"{prefix}-{number:03d}",
                    "message": f"{base}{suffix}".strip(),
                    "author": "Carol" if (base_index + suffix_index) % 3 == 0 else "Eu",
                    "expected": expected,
                    "scenario": f"{prefix.lower()}-{base_index + 1:02d}",
                }
            )
    return cases


FINANCE = _expand(
    "FIN",
    "financas",
    [
        "Paguei 86 reais no mercado",
        "Gastei R$ 42,90 no remédio da gripe",
        "A Carol pagou 119 reais de internet",
        "O Calebe gastou 35 reais abastecendo a moto",
        "Comprei o gás por 112 reais",
        "Saiu 64 reais o jantar de ontem",
        "Transferi 550 reais para o aluguel",
        "A fatura da luz ficou em R$ 178,30 e já paguei",
        "Comprei duas camisetas por 79 reais no total",
        "Paguei 28 reais de estacionamento no centro",
    ],
    [
        ".",
        " no cartão da Carol.",
        " e isso estava no orçamento deste mês.",
        " depois que voltei do trabalho.",
        " para a nossa casa, pode registrar.",
    ],
)

WISHLIST = _expand(
    "WIS",
    "wishlist",
    [
        "Calebe precisa comprar um micro-ondas de até 300 reais",
        "Carol quer assinar HBO por no máximo 35 reais por mês",
        "Precisamos comprar uma panela de pressão nova",
        "Quero trocar meu celular quando aparecer um por até 1.500 reais",
        "Comprar um presente para a mãe da Carol",
        "A gente precisa pesquisar uma máquina de lavar econômica",
        "Calebe quer um tênis preto número 41",
        "Carol precisa comprar shampoo e condicionador sem sulfato",
        "Quero guardar a ideia de comprar uma air fryer",
        "Precisamos de uma estante pequena para a sala",
    ],
    [
        ".",
        " até o fim do mês.",
        " se encontrarmos uma promoção boa.",
        " antes da próxima viagem, sem criar tarefa de casa.",
        " e ainda não compramos, é só para lembrar da compra.",
    ],
)

# Pesquisar/comparar um produto é uma tarefa executável. A intenção só vira
# Wishlist quando o casal expressa aquisição futura, não mera investigação.
for _case in WISHLIST:
    if _case["scenario"] == "wis-06":
        _case["expected"] = "rotina"

PLACES = _expand(
    "PLC",
    "lugares",
    [
        "Quero conhecer o restaurante japonês novo do centro",
        "Carol quer visitar o Jardim Botânico",
        "Vamos guardar a ideia de ir àquele café com livros",
        "Calebe gostaria de conhecer Paraty",
        "A gente quer experimentar a pizzaria da esquina",
        "Tenho vontade de visitar o museu de arte moderna",
        "Adicionar a trilha da Pedra Bonita aos lugares que queremos conhecer",
        "Quero levar a Carol naquele bistrô francês",
    ],
    [
        ".",
        " algum dia.",
        " quando tivermos um fim de semana livre.",
        " sem marcar data ainda.",
        " porque vários amigos recomendaram.",
    ],
)

CALENDAR = _expand(
    "CAL",
    "calendario",
    [
        "Dentista da Carol terça-feira às 14h",
        "Jantar com meus pais sábado às 20h",
        "Nossa consulta de rotina é dia 28 às 9h30",
        "Marcar no calendário a viagem para Ubatuba de 12 a 15 de setembro",
        "Aniversário da Ana no próximo domingo às 16h",
        "Reunião do condomínio amanhã às 19h",
        "Cinema com a Carol sexta à noite, sessão das 21h",
        "O técnico da internet vem hoje entre 13h e 17h",
        "Reserva do restaurante confirmada para quinta às 20h30",
        "A prova do Calebe será em 3 de outubro às 8h",
    ],
    [
        ".",
        " e a Carol também vai.",
        "; não é uma rotina recorrente.",
        " no horário de Brasília.",
        " — o compromisso já está confirmado.",
    ],
)

ROUTINE = _expand(
    "ROT",
    "rotina",
    [
        "Calebe lavar a louça hoje à noite",
        "Carol colocar a roupa na máquina amanhã cedo",
        "Assistir à série O Mentalista no fim de semana",
        "Trocar a roupa de cama todo domingo",
        "Levar o lixo para fora às terças e quintas",
        "Calebe precisa ligar para o encanador amanhã",
        "Carol estudar inglês por meia hora depois do jantar",
        "Limpar a geladeira até sexta-feira",
        "Dar remédio para o cachorro de 12 em 12 horas por cinco dias",
        "Separar os documentos do imposto de renda esta semana",
        "Regar as plantas da varanda segunda, quarta e sexta",
        "Calebe buscar a encomenda antes das 18h",
        "Carol responder a mensagem da escola hoje",
        "Organizar as fotos da viagem quando sobrar tempo no sábado",
        "Fazer caminhada juntos três vezes por semana",
        "Cancelar a assinatura de teste antes do dia 30",
    ],
    [
        ".",
        " e avisar quando terminar.",
        " sem transformar isso em compromisso do calendário.",
        " porque combinamos essa divisão de tarefas.",
        " mesmo que o restante da casa fique para depois.",
    ],
)

QUERY = _expand(
    "QRY",
    "query",
    [
        "Quanto gastamos com mercado este mês?",
        "Quais tarefas da Carol estão pendentes?",
        "O que temos marcado para o próximo sábado?",
        "Qual foi nossa última conta de luz?",
        "Tem algum item da lista de compras abaixo de 300 reais?",
        "Quais lugares queremos conhecer no Rio?",
        "Quando é a próxima consulta do Calebe?",
        "Quem está responsável por lavar a louça hoje?",
        "Quanto ainda podemos gastar com lazer neste mês?",
        "Mostre as compras que ainda não fizemos.",
        "O que já concluímos da rotina desta semana?",
        "Existe algum compromisso conflitante na sexta à noite?",
    ],
    [
        "",
        " Quero apenas consultar, sem criar registro.",
        " Considere somente os dados do Cantinho.",
        " Pode me dar um resumo curto?",
        " Não altere nada, só me responda.",
    ],
)

MULTI = _expand(
    "MUL",
    "multi",
    [
        "Paguei 90 reais no mercado e Calebe precisa lavar a louça hoje",
        "Comprar uma cafeteira de até 250 reais e marcar dentista sexta às 10h",
        "Carol quer conhecer o restaurante coreano e precisa ligar para a mãe amanhã",
        "Gastei 45 reais no remédio e quero comprar um termômetro novo",
        "Agendar cinema sábado às 20h e guardar a ideia de conhecer o café ao lado",
        "Calebe limpar o banheiro hoje e Carol trocar a roupa de cama amanhã",
        "Quero comprar um sofá de até 2 mil reais e visitar a loja do centro algum dia",
        "Paguei a internet de 120 reais, marcar reunião do condomínio terça às 19h e tirar o lixo hoje",
    ],
    [
        ".",
        "; são registros separados.",
        ", por favor não perca nenhuma das duas partes.",
        " — cada ação deve ir para o seu canto correto.",
        "; a primeira parte é uma coisa e a segunda é outra.",
    ],
)

UNKNOWN = _expand(
    "UNK",
    "desconhecido",
    [
        "A casa está uma bagunça",
        "HBO",
        "Acho que talvez um dia a gente veja isso",
        "Não comprar micro-ondas e não criar tarefa",
        "300 reais",
        "Carol disse que o sábado foi ótimo",
    ],
    [
        ".",
        " Só estou comentando.",
        " Não registre nada.",
        " Isso não é pedido nem pergunta.",
        " Estou pensando em voz alta.",
    ],
)


CASES: list[EvalCase] = [
    *FINANCE,
    *WISHLIST,
    *PLACES,
    *CALENDAR,
    *ROUTINE,
    *QUERY,
    *MULTI,
    *UNKNOWN,
]

EXPECTED_DISTRIBUTION = {
    "financas": 50,
    "wishlist": 45,
    "lugares": 40,
    "calendario": 50,
    "rotina": 85,
    "query": 60,
    "multi": 40,
    "desconhecido": 30,
}

assert len(CASES) == 400
assert Counter(case["expected"] for case in CASES) == EXPECTED_DISTRIBUTION
