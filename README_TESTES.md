# Testes e correcoes automaticas

Esta versao adiciona uma camada de seguranca para evoluir o Cantinho sem quebrar comportamentos que ja funcionam.

## Rodar a suite

No PowerShell, na raiz do projeto:

```powershell
.\test_cantinho.ps1
```

Na primeira execucao, o script instala apenas o `pytest` na `.venv` caso ainda nao exista.

Os testes sao **offline**: eles nao gravam no Notion e nao chamam o Ollama real.

A suite v3.0 possui **218 testes**, incluindo intenção, datas relativas,
recorrências, conclusão contextual, consultas complexas, paginação, leitores,
agregações, planos `actions[]`, confirmação, retomada parcial e idempotência.

O ultimo relatorio fica em:

```text
logs\tests-last.txt
```

## O que esta protegido

- valores brasileiros (`1.250,90`, `R$ 1.999,99`, etc.);
- roteamento de Query, Financas, Wishlist, Lugares, Calendario e Rotina;
- parser rapido de Financas;
- parser rapido de Wishlist;
- parser rapido de Lugares;
- validacao antes de escrever no Notion;
- baixa confianca -> `Precisa confirmacao`;
- resposta invalida do Ollama -> nova tentativa automatica;
- normalizacao dos nomes de propriedades do Notion.
- resultado mobile com link seguro para o registro criado.
- paginação integral dos resultados do Notion;
- consultas por período, pessoa, termo e status;
- totais, saldos, maior valor, contagens e listas;
- separação estrita entre leitura e escrita.
- regras de recorrência e próxima ocorrência;
- conclusão pontual e avanço de tarefas recorrentes;
- schema tipado do Ollama por destino;
- prévia obrigatória para múltiplas ações;
- checkpoint por ação e recuperação por `Origem IA`.

## Correcoes automaticas em runtime

Quando o Ollama retorna JSON invalido ou fora do schema, `structured_chat` tenta novamente uma vez com uma instrucao de reparo.

Se ainda assim falhar, o Worker registra `Erro` em vez de gravar dados potencialmente incorretos.

Quando o roteamento automatico vem com confianca abaixo do limite, o sistema envia para `Precisa confirmacao` e **nao grava** no banco de destino.

## Fila de aprendizado

Mensagens que terminam em `Precisa confirmacao` ou `Erro` sao registradas localmente em:

```text
logs\learning_cases.jsonl
```

Para ver um resumo:

```powershell
.\.venv\Scripts\python.exe -m scripts.learning_report
```

Esses casos devem ser transformados em novos testes antes de melhorar regras do parser/router.

## Regra de manutencao

Antes de mudar `router.py`, `parsers.py`, `prompts.py` ou `processor.py`:

1. adicione um teste que representa a frase nova;
2. rode `test_cantinho.ps1` e veja o teste falhar;
3. altere a regra;
4. rode novamente;
5. so mantenha a mudanca quando toda a suite passar.

O sistema **nao edita o proprio codigo automaticamente**. A autorrecuperacao e limitada a repeticao segura da interpretacao e bloqueio de escritas incertas.
