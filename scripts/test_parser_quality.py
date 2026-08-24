from app.ai.parsers import (
    money,
    fast_finance,
    fast_wishlist,
    fast_place,
    fast_routine,
)
from app.ai.router import route_message


def check(label, got, expected):
    ok = got == expected
    print(f"{'OK' if ok else 'ERRO'} | {label}")
    print(f"  obtido:   {got!r}")
    print(f"  esperado: {expected!r}")
    if not ok:
        raise AssertionError(label)


# 1. Valor financeiro que havia falhado.
check(
    "money: paguei 32 no uber",
    money("Paguei 32 no Uber"),
    32.0,
)

finance = fast_finance("Paguei 32 no Uber", "Eu")
check("finance.valor", finance.valor, 32.0)
check("finance.categoria", finance.categoria, "Transporte")
check("finance.movimento", finance.movimento, "Uber")
check("finance.confirmacao", finance.needs_confirmation, False)

# 2. Wishlist deve salvar somente o objeto.
wishlist = fast_wishlist(
    "Quero comprar um fone de ate 400 reais"
)
check("wishlist.item", wishlist.item, "fone")
check("wishlist.preco", wishlist.preco_estimado, 400.0)
check("wishlist.tipo", wishlist.tipo, "Tecnologia")

wishlist2 = fast_wishlist(
    "Quero comprar um fone de ouvido de ate 400 reais"
)
check("wishlist item composto", wishlist2.item, "fone de ouvido")

# 3. Lugar deve salvar o lugar, nao o verbo da frase.
place = fast_place(
    "Quero conhecer um restaurante italiano em SP"
)
check("place.lugar", place.lugar, "restaurante italiano")
check("place.local", place.local, "sp")
check("place.tipo", place.tipo, "Restaurante")

# 4. Router nao deve chamar IA para esses casos comuns.
check(
    "router wishlist",
    route_message(
        "Quero comprar um fone de ate 400 reais"
    ).destination,
    "wishlist",
)
check(
    "router lugares",
    route_message(
        "Quero conhecer um restaurante italiano em SP"
    ).destination,
    "lugares",
)
check(
    "router financas",
    route_message("Paguei 32 no Uber").destination,
    "financas",
)

# 5. Tarefa com prazo nao pode virar evento de calendario.
hbo = fast_routine(
    "Calebe precisa assinar HBO final do mes"
)
check("hbo tarefa", hbo.tarefa, "assinar hbo")
check("hbo frequencia", hbo.frequencia, "Pontual")
check("hbo responsavel", hbo.responsavel, "Eu")
check(
    "router hbo",
    route_message(
        "Calebe precisa assinar HBO final do mes"
    ).destination,
    "rotina",
)

print("\nTodos os testes de qualidade passaram.")
