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
