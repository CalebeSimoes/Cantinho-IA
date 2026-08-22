# 🌿 Cantinho Ghibli AI v2

A v2 usa o **Notion como interface mobile** e o PC como processador local.

```text
Notion Form / celular
   ↓
✨ Caixa de Entrada IA
   ↓
worker.py
   ↓
router híbrido (Python + Ollama)
   ↓
Finanças | Wishlist | Lugares | Calendário | Rotina
   ↓
Resultado volta para a Caixa de Entrada
```

## Arquivos novos principais

- `app/worker.py`: verifica pendências automaticamente.
- `app/processor.py`: orquestra cada mensagem.
- `app/ai/router.py`: escolhe o destino.
- `app/ai/parsers.py`: extrai os campos.
- `app/notion/inbox.py`: lê/atualiza a Caixa de Entrada IA.
- `app/notion/writers.py`: grava nas cinco bases.
- `run_worker_windows.ps1`: roda só o worker.
- `worker_once_windows.ps1`: processa a fila uma vez.
- `start_cantinho_windows.ps1`: inicia Ollama, worker e API.

## 1. Configurar

Edite `.env` e preserve o seu token real:

```env
NOTION_TOKEN=ntn_...
```

A v2 já vem com os Data Source IDs das seis bases deste projeto.

## 2. Instalar

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\setup_windows.ps1
```

## 3. Testar

```powershell
.\testar_windows.ps1
```

## 4. Primeiro teste do worker

No formulário `📱 Anotar com IA` do Notion, envie:

`Paguei 25 reais no Uber`

Depois:

```powershell
.\worker_once_windows.ps1
```

Esperado:
- item da Caixa de Entrada -> `Processado`;
- `Resultado` preenchido;
- nova linha em `💸 Finanças do Casal`.

## 5. Rodar continuamente

```powershell
.\run_worker_windows.ps1
```

Ele verifica a Caixa de Entrada a cada 10 segundos.

## 6. API/Swagger (opcional)

```powershell
.\run_api_windows.ps1
```

Abra `http://127.0.0.1:8000/docs`.

## 7. Iniciar tudo depois

```powershell
.\start_cantinho_windows.ps1
```

O Notion continua recebendo anotações quando o PC está desligado; elas ficam pendentes e serão processadas quando o worker voltar.
