from app.ai.parsers import money

CASES = {
    "Paguei 32 no Uber": 32.0,
    "Paguei 50 no Uber": 50.0,
    "Paguei 32,50 no Uber": 32.5,
    "Gastei 1.250,90 no mercado": 1250.9,
    "Gastei 2.500 no mercado": 2500.0,
    "Paguei R$ 1.999,99 no mercado": 1999.99,
    "Quero comprar um fone de ate 400 reais": 400.0,
    "Comprei 3500 no notebook": 3500.0,
}

failed = False

for phrase, expected in CASES.items():
    got = money(phrase)
    ok = got == expected
    print(("OK" if ok else "ERRO"), "|", phrase, "->", got, "| esperado:", expected)
    if not ok:
        failed = True

if failed:
    raise SystemExit(1)

print("\nTodos os testes monetarios passaram.")
