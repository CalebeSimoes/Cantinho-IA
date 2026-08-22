from app.ai.parsers import parse_place

samples = [
    "Quero conhecer um restaurante japonês em São Paulo",
    "Quero conhecer um hotel em Campos do Jordão de até 900 reais",
]

for sample in samples:
    print("\nMensagem:", sample)
    result = parse_place(sample)
    print(result.model_dump(mode="json"))
