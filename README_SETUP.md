# COO Chato MONSTRO — Setup Guide

## O que este bot faz agora

- 🧠 **Memória de Longo Prazo** — lembra-se do que prometeste (Supabase)
- 📅 **Google Calendar** — lê a tua agenda antes de cada resposta
- 🔥 **Lembretes Proativos** — mensagem automática às 09h, 22h e se ficares 4h em silêncio
- 🔄 **Retry automático** — se o Gemini der 429, espera e tenta outra vez

---

## PASSO 1 — Supabase (Base de Dados)

### 1.1 Criar projeto
1. Vai a [supabase.com](https://supabase.com) → "Start your project" → "Sign Up" (grátis)
2. Cria um novo projeto (escolhe região **West EU**)
3. Guarda a password do projeto

### 1.2 Criar as tabelas
1. No dashboard do Supabase → **SQL Editor** → "New query"
2. Copia o conteúdo de `supabase_setup.sql` e clica **Run**
3. Deves ver as tabelas `users`, `messages`, `promises` criadas

### 1.3 Obter as credenciais
1. No Supabase → **Project Settings** → **API**
2. Copia:
   - **Project URL** → vai ser a env var `SUPABASE_URL`
   - **anon / public key** → vai ser `SUPABASE_KEY`

---

## PASSO 2 — Google Calendar (OAuth)

### 2.1 Criar projeto no Google Cloud
1. Vai a [console.cloud.google.com](https://console.cloud.google.com)
2. Cria um novo projeto (ex: "coo-chato")
3. No menu → **APIs & Services** → **Library**
4. Pesquisa "Google Calendar API" → **Enable**

### 2.2 Criar credenciais OAuth
1. **APIs & Services** → **Credentials** → **Create Credentials** → **OAuth client ID**
2. Se pedir configurar OAuth consent screen:
   - User Type: **External**
   - App name: "COO Chato"
   - Adiciona o teu email como test user
3. Tipo de aplicação: **Desktop app**
4. Nome: "COO Chato Bot"
5. Clica **Create** → **Download JSON**
6. Guarda o ficheiro como `credentials.json` na pasta `bot-chefe`

### 2.3 Correr o script de autenticação (localmente, só uma vez)
```powershell
# Na pasta bot-chefe
python setup_google_auth.py
```
- O browser abre → faz login com a tua conta Google → autoriza
- O terminal imprime um valor longo em base64
- **Copia esse valor** — vai ser a env var `GOOGLE_TOKEN_JSON`

> ⚠️ Adiciona ao `.gitignore`:
> ```
> credentials.json
> token.json
> ```

---

## PASSO 3 — Obter o teu Chat ID do Telegram

1. Corre o bot localmente (`python main.py`)
2. Vai ao Telegram e escreve `/start`
3. O bot responde com uma mensagem — mas precisas do teu chat_id
4. Alternativa: escreve para [@userinfobot](https://t.me/userinfobot) no Telegram — ele diz-te o teu ID

---

## PASSO 4 — Configurar as Env Vars no Render

No Render → o teu serviço → **Environment** → adiciona:

| Nome | Valor |
|------|-------|
| `GEMINI_KEY` | A tua chave do AI Studio |
| `TG_TOKEN` | O token do BotFather |
| `SUPABASE_URL` | URL do teu projeto Supabase |
| `SUPABASE_KEY` | anon/public key do Supabase |
| `MY_CHAT_ID` | O teu Telegram Chat ID (número) |
| `GOOGLE_TOKEN_JSON` | O valor base64 do setup_google_auth.py |

---

## PASSO 5 — Deploy no Render

1. Faz `git add . && git commit -m "feat: bot monstro com memoria e calendar" && git push`
2. O Render detecta o push e faz deploy automático
3. Vai aos logs do Render e verifica que aparece: `🔥 COO Chato MONSTRO online.`

---

## Comandos do Bot

| Comando | O que faz |
|---------|-----------|
| `/start` | Boas-vindas + lista de promessas abertas |
| `/promessas` | Ver todas as promessas em dívida |
| `/cumpri [n]` | Marcar promessa número N como cumprida |
| `/agenda` | Ver a agenda de hoje |
| `/proximos` | Ver eventos dos próximos 3 dias |
| `/marcar [HH:MM] [título]` | Criar evento no Calendar |

---

## Como a memória funciona

Quando escreves algo como "Vou acabar o pitch amanhã", o bot:
1. Detecta o compromisso
2. Guarda na tabela `promises` do Supabase
3. Inclui essa promessa no contexto de TODAS as futuras conversas
4. Cobra-te automaticamente no check-in das 09h

Para "cumprir" uma promessa: `/cumpri 1`

---

## Lembretes Automáticos

| Hora | O que acontece |
|------|---------------|
| 09:00 | Check-in com promessas em aberto + agenda do dia |
| 22:00 | Balanço do dia |
| A cada 2h (9h-22h) | Se estiveres 4h+ em silêncio → lembrete |

---

## Testar localmente (antes do deploy)

```powershell
# Instalar dependências
pip install -r requirements.txt

# Definir env vars temporariamente (PowerShell)
$env:GEMINI_KEY="a_tua_chave"
$env:TG_TOKEN="o_teu_token"
$env:SUPABASE_URL="https://xxx.supabase.co"
$env:SUPABASE_KEY="a_tua_key"
$env:MY_CHAT_ID="o_teu_id"

# Correr
python main.py
```
