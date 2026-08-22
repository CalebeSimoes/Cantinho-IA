# Arquitetura v2

```text
Notion Mobile/Form
       ↓
✨ Caixa de Entrada IA
       ↓ polling
app/worker.py
       ↓
app/processor.py
       ↓
Router
 ┌─────┴─────┐
Python      Ollama
rápido      fallback
 └─────┬─────┘
       ↓
Notion writers
 ├ Finanças
 ├ Wishlist
 ├ Lugares
 ├ Calendário
 └ Rotina
```

Regra: o Notion é a interface/fila persistente; o worker é o motor; Ollama só entra quando as regras simples não resolvem.
