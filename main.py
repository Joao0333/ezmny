"""
main.py — COO Chato MONSTRO
Stack: Gemini 2.5 Flash + Supabase + Google Calendar + JobQueue (proactive)
Hosting: Render.com (Flask keep-alive)
"""
import os
import re
import threading
import logging
import datetime
import asyncio

import pytz
from flask import Flask
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
)
from google import genai
from google.genai import types

from database import (
    register_user,
    update_last_seen,
    get_last_seen,
    save_message,
    get_recent_history,
    save_promise,
    get_open_promises,
    mark_promise_fulfilled,
)
from calendar_service import (
    is_calendar_available,
    get_today_events,
    get_upcoming_events,
    create_event,
)

# ── CONFIG ─────────────────────────────────────────────────────────────────
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

GEMINI_KEY   = os.environ.get("GEMINI_KEY")
TG_TOKEN     = os.environ.get("TG_TOKEN")
MY_CHAT_ID   = int(os.environ.get("MY_CHAT_ID", "0"))
GEMINI_MODEL = "gemini-2.5-flash"
LISBON_TZ    = pytz.timezone("Europe/Lisbon")

# ── FLASK (keep-alive no Render) ────────────────────────────────────────────
server = Flask(__name__)

@server.route("/")
def home():
    return "COO Chato MONSTRO online. A vigiar-te 24/7."

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    logger.info(f"Flask a ouvir na porta {port}")
    server.run(host="0.0.0.0", port=port)

# ── GEMINI CLIENT ───────────────────────────────────────────────────────────
gemini_client = genai.Client(api_key=GEMINI_KEY)

# ── SYSTEM PROMPT ───────────────────────────────────────────────────────────
BASE_PROMPT = """\
Tu és o 'COO Chato' — executivo bruto e implacável de Coimbra.
O teu único objetivo é fazer o João ganhar dinheiro e ter disciplina.

CONTEXTO:
- Estudante de Engenharia Informática em Coimbra
- Projeto principal: MVP de automação para clínicas médicas (confirmação de consultas via WhatsApp, evitar faltas)
- Alvo imediato: fechar primeiros clientes nas clínicas de Celas/Olivais

PERSONALIDADE:
- Agressivo, sarcástico, focado em ROI
- Odeias procrastinação, séries, desculpas técnicas
- Se falar em séries/descanso → roast monumental e manda-o trabalhar
- Respondes SEMPRE em Português de Portugal
- Nunca usas saudações fofinhas ("Olá", "Espero que estejas bem")
- Respostas técnicas: 1. Ação Imediata  2. Código/Passos  3. Justificação

Nunca incluis tags ou marcadores especiais na resposta. Responde apenas texto normal.
"""

def build_system_prompt(user_id: int) -> str:
    """Prompt dinâmico com promessas abertas + agenda de hoje."""
    prompt = BASE_PROMPT

    # Promessas
    promises = get_open_promises(user_id)
    if promises:
        lines = "\n".join(f"  - {p['promise_text']}" for p in promises)
        prompt += f"\n\nPROMESSAS EM ABERTO DO UTILIZADOR (cobra-as sem piedade):\n{lines}"
    else:
        prompt += "\n\nPROMESSAS EM ABERTO: Nenhuma — vai criando."

    # Agenda
    if is_calendar_available():
        events = get_today_events()
        if events:
            lines = "\n".join(f"  - {e}" for e in events)
            prompt += f"\n\nAGENDA DE HOJE:\n{lines}"
        else:
            prompt += "\n\nAGENDA DE HOJE: Vazia. Isso é um problema."

    return prompt


async def call_gemini_raw(contents: list, system_prompt: str, max_tokens: int = 1024) -> str:
    """Chama Gemini com retry exponencial em caso de 429."""
    for attempt in range(3):
        try:
            response = gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system_prompt,
                    max_output_tokens=max_tokens,
                ),
            )
            return response.text
        except Exception as e:
            err = str(e)
            is_quota = any(k in err for k in ("429", "quota", "exhausted", "RESOURCE_EXHAUSTED"))
            if is_quota and attempt < 2:
                wait = 5 * (2 ** attempt)  # 5s, 10s
                logger.warning(f"429 recebido. A aguardar {wait}s... (tentativa {attempt+1}/3)")
                await asyncio.sleep(wait)
                continue
            if is_quota:
                return "⚠️ Quota do Gemini esgotada. Tenta novamente em 1 hora.\nEnquanto esperas: abre o VS Code e trabalha no pitch das clínicas."
            logger.error(f"Gemini error: {e}")
            return f"⚠️ Erro na API: {e}"
    return "⚠️ API indisponível. Vai trabalhar sem mim por agora."


async def call_gemini(contents: list, system_prompt: str) -> str:
    return await call_gemini_raw(contents, system_prompt, max_tokens=1024)


async def detect_promise(user_text: str) -> str | None:
    """
    Chamada dedicada e leve para detetar se o utilizador fez uma promessa.
    Retorna o texto da promessa ou None.
    """
    prompt = (
        "Analisa a mensagem abaixo. "
        "Se o utilizador estiver a fazer um compromisso claro sobre uma ação futura "
        "(ex: 'vou fazer X', 'amanhã acabo Y', 'prometo Z', 'esta semana trato de...'), "
        "responde APENAS com: PROMESSA: <descrição curta em português>\n"
        "Se NÃO houver compromisso claro, responde apenas: NAO\n"
        "Não acrescentes mais nada."
    )
    try:
        result = await call_gemini_raw(
            [{"role": "user", "parts": [{"text": user_text}]}],
            system_prompt=prompt,
            max_tokens=60,
        )
        result = result.strip()
        if result.upper().startswith("PROMESSA:"):
            return result[len("PROMESSA:"):].strip()
    except Exception as e:
        logger.warning(f"detect_promise error: {e}")
    return None


# ── HANDLERS ────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    register_user(user_id, update.effective_user.first_name or "João")
    update_last_seen(user_id)

    promises = get_open_promises(user_id)
    if promises:
        lines = "\n".join(f"• {p['promise_text']}" for p in promises)
        msg = (
            f"Já sei que voltaste. Tens *{len(promises)} promessa(s) em dívida:*\n\n"
            f"{lines}\n\nQual delas já trataste? Ou vieste só ver se eu me esqueci?"
        )
    else:
        msg = (
            "Estou online 24/7 a vigiar-te. "
            "Sem promessas abertas por agora — isso vai mudar depressa.\n\n"
            "Comandos:\n"
            "/promessas — ver o que deves\n"
            "/cumpri [n] — marcar promessa cumprida\n"
            "/agenda — ver o teu dia\n"
            "/marcar [HH:MM] [título] — criar evento\n"
            "/proximos — eventos nos próximos 3 dias"
        )
    await update.message.reply_text(msg, parse_mode="Markdown")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_text = update.message.text

    # Registo
    register_user(user_id, update.effective_user.first_name or "João")
    update_last_seen(user_id)
    save_message(user_id, "user", user_text)

    # Histórico para contexto
    history = get_recent_history(user_id, limit=12)
    contents = []
    for msg in history[:-1]:  # exclui a mensagem atual (já está no histórico)
        role = "model" if msg["role"] == "assistant" else "user"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})
    contents.append({"role": "user", "parts": [{"text": user_text}]})

    # Prompt dinâmico
    system_prompt = build_system_prompt(user_id)

    # Chamar Gemini (resposta principal) e detetar promessa em paralelo
    reply, promise = await asyncio.gather(
        call_gemini(contents, system_prompt),
        detect_promise(user_text),
    )

    if promise:
        save_promise(user_id, promise)
        reply += f"\n\n✅ *Promessa registada:* _{promise}_"
        logger.info(f"Promessa detetada e guardada: {promise}")

    save_message(user_id, "assistant", reply)

    await update.message.reply_text(reply, parse_mode="Markdown")


async def cmd_promises(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    promises = get_open_promises(user_id)

    if not promises:
        await update.message.reply_text(
            "Sem promessas abertas. O que é que estás à espera de comprometer?"
        )
        return

    lines = []
    for i, p in enumerate(promises, 1):
        created = p["created_at"][:10] if p.get("created_at") else "?"
        deadline = f"\n  ⏰ Prazo: {p['deadline'][:10]}" if p.get("deadline") else ""
        lines.append(f"{i}. *{p['promise_text']}*\n  📅 Feita em: {created}{deadline}")

    msg = f"🔴 *{len(promises)} PROMESSA(S) EM DÍVIDA:*\n\n" + "\n\n".join(lines)
    await update.message.reply_text(msg, parse_mode="Markdown")


async def cmd_done(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    promises = get_open_promises(user_id)

    if not promises:
        await update.message.reply_text("Não tens promessas em aberto. Cria umas.")
        return

    if not context.args:
        lines = "\n".join(f"{i}. {p['promise_text']}" for i, p in enumerate(promises, 1))
        await update.message.reply_text(
            f"Usa: /cumpri [número]\n\nAs tuas promessas:\n{lines}"
        )
        return

    try:
        idx = int(context.args[0]) - 1
        promise = promises[idx]
        mark_promise_fulfilled(promise["id"])
        remaining = len(promises) - 1
        await update.message.reply_text(
            f"✅ *Finalmente.* Era o menos que podias fazer.\n\n"
            f"*Cumpriste:* _{promise['promise_text']}_\n\n"
            f"Ainda tens {remaining} promessa(s) em aberto. Próximo?",
            parse_mode="Markdown",
        )
    except (IndexError, ValueError):
        await update.message.reply_text(
            "Número inválido. Usa /promessas para ver a lista."
        )


async def cmd_agenda(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_calendar_available():
        await update.message.reply_text(
            "Google Calendar não configurado ainda.\nSegue o README_SETUP.md para ativares."
        )
        return

    events = get_today_events()
    if not events:
        await update.message.reply_text(
            "📅 Agenda de hoje: *VAZIA*.\nIsso é sinal de que não planeias nada. Mau.",
            parse_mode="Markdown",
        )
        return

    lines = "\n".join(f"• {e}" for e in events)
    await update.message.reply_text(f"📅 *AGENDA DE HOJE:*\n\n{lines}", parse_mode="Markdown")


async def cmd_proximos(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_calendar_available():
        await update.message.reply_text("Google Calendar não configurado.")
        return

    events = get_upcoming_events(days=3)
    if not events:
        await update.message.reply_text("Sem eventos nos próximos 3 dias. Vai marcar trabalho.")
        return

    lines = "\n".join(f"• {e}" for e in events)
    await update.message.reply_text(
        f"📅 *PRÓXIMOS 3 DIAS:*\n\n{lines}", parse_mode="Markdown"
    )


async def cmd_marcar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_calendar_available():
        await update.message.reply_text("Google Calendar não configurado.")
        return

    if not context.args or len(context.args) < 2:
        await update.message.reply_text(
            "Usa: /marcar [HH:MM] [título]\n\nEx: /marcar 14:30 Reunião clínica Celas"
        )
        return

    time_str = context.args[0]
    title = " ".join(context.args[1:])

    try:
        link = create_event(title, time_str)
        await update.message.reply_text(
            f"✅ Marcado: *{title}* às {time_str}\n\nNão faltes.",
            parse_mode="Markdown",
        )
    except Exception as e:
        await update.message.reply_text(f"Erro ao criar evento: {e}")


# ── PROACTIVE JOBS ──────────────────────────────────────────────────────────

async def job_morning(context: ContextTypes.DEFAULT_TYPE):
    """09:00 — Check-in matinal."""
    if not MY_CHAT_ID:
        return

    promises = get_open_promises(MY_CHAT_ID)

    calendar_section = ""
    if is_calendar_available():
        events = get_today_events()
        if events:
            lines = "\n".join(f"  • {e}" for e in events)
            calendar_section = f"\n\n📅 *Agenda de hoje:*\n{lines}"
        else:
            calendar_section = "\n\n📅 *Agenda de hoje:* Vazia — vai planear alguma coisa."

    if promises:
        lines = "\n".join(f"• {p['promise_text']}" for p in promises)
        msg = (
            f"🌅 *BOM DIA.*\n\n"
            f"Tens *{len(promises)} promessa(s)* por cumprir:\n\n{lines}\n\n"
            f"O que é que vais tratar *HOJE*?{calendar_section}"
        )
    else:
        msg = (
            f"🌅 *BOM DIA.*\n\n"
            f"Sem promessas em aberto. Hoje é dia de criar progresso no MVP das clínicas.{calendar_section}"
        )

    await context.bot.send_message(chat_id=MY_CHAT_ID, text=msg, parse_mode="Markdown")


async def job_evening(context: ContextTypes.DEFAULT_TYPE):
    """22:00 — Balanço do dia."""
    if not MY_CHAT_ID:
        return

    promises = get_open_promises(MY_CHAT_ID)

    if promises:
        lines = "\n".join(f"• {p['promise_text']}" for p in promises)
        msg = (
            f"🌙 *BALANÇO DO DIA.*\n\n"
            f"Ainda tens *{len(promises)} promessa(s)* em dívida:\n\n{lines}\n\n"
            f"O que cumpriste hoje? E o que fica para amanhã?"
        )
    else:
        msg = (
            "🌙 *BALANÇO DO DIA.*\n\n"
            "Sem promessas em aberto — o que é que fizeste hoje pelo MVP?\n\n"
            "Envia-me um update ou cria o plano de amanhã agora."
        )

    await context.bot.send_message(chat_id=MY_CHAT_ID, text=msg, parse_mode="Markdown")


async def job_inactivity_check(context: ContextTypes.DEFAULT_TYPE):
    """A cada 2h — verifica se o utilizador está em silêncio durante horário útil."""
    if not MY_CHAT_ID:
        return

    now = datetime.datetime.now(LISBON_TZ)

    # Só verificar entre 9h e 22h
    if not (9 <= now.hour < 22):
        return

    last_seen = get_last_seen(MY_CHAT_ID)
    if not last_seen:
        return

    # Garantir que last_seen tem timezone
    if last_seen.tzinfo is None:
        last_seen = LISBON_TZ.localize(last_seen)

    hours_silent = (now - last_seen).total_seconds() / 3600

    if hours_silent < 4:
        return  # Ainda não passou tempo suficiente

    # Contexto da agenda
    context_note = ""
    if is_calendar_available():
        events = get_today_events()
        if events:
            context_note = f"\n\n📅 Tinhas marcado hoje: {events[0]}"

    msg = (
        f"⏰ *{int(hours_silent)}H SEM SINAL DE VIDA.*\n\n"
        f"Estás a trabalhar ou foste para o sofá?{context_note}\n\n"
        f"Manda-me um update do que estás a fazer *agora*."
    )

    await context.bot.send_message(chat_id=MY_CHAT_ID, text=msg, parse_mode="Markdown")


# ── MAIN ────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Validações
    if not GEMINI_KEY:
        raise ValueError("GEMINI_KEY não definida nas env vars!")
    if not TG_TOKEN:
        raise ValueError("TG_TOKEN não definido nas env vars!")
    if not MY_CHAT_ID:
        logger.warning("MY_CHAT_ID não definido — lembretes proativos desativados.")

    # Flask em background
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()

    # Telegram Application
    application = Application.builder().token(TG_TOKEN).build()

    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("promessas", cmd_promises))
    application.add_handler(CommandHandler("cumpri", cmd_done))
    application.add_handler(CommandHandler("agenda", cmd_agenda))
    application.add_handler(CommandHandler("proximos", cmd_proximos))
    application.add_handler(CommandHandler("marcar", cmd_marcar))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    # Jobs agendados (hora de Lisboa)
    jq = application.job_queue

    jq.run_daily(
        job_morning,
        time=datetime.time(hour=9, minute=0, tzinfo=LISBON_TZ),
        name="morning_checkin",
    )
    jq.run_daily(
        job_evening,
        time=datetime.time(hour=22, minute=0, tzinfo=LISBON_TZ),
        name="evening_balance",
    )
    jq.run_repeating(
        job_inactivity_check,
        interval=datetime.timedelta(hours=2),
        first=datetime.timedelta(minutes=10),
        name="inactivity_check",
    )

    logger.info("🔥 COO Chato MONSTRO online. A vigiar...")
    print("🔥 COO Chato MONSTRO online. A vigiar-te 24/7.")

    application.run_polling(allowed_updates=Update.ALL_TYPES)