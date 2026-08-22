# Prompt do Cantinho Ghibli AI

O prompt real está em `app/ai/prompts.py`.

Exemplo de entrada:

`Gastei 100 reais no restaurante com a Carol.`

Saída esperada:

```json
{
  "intent": "financas",
  "needs_confirmation": false,
  "missing_fields": [],
  "movimento": "Restaurante",
  "valor": 100,
  "tipo": "Saída",
  "categoria": "Alimentação",
  "pago_por": "Eu",
  "status": "Pago",
  "data": "DATA_DE_HOJE",
  "observacao": "Com a Carol"
}
```

Importante: estar "com a Carol" não significa que ela também pagou.
