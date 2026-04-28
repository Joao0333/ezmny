import os
import threading
from flask import Flask
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from google import genai  # Versão moderna 2026

# --- 1. O "ALIBI" PARA O RENDER (FLASK) ---
server = Flask(__name__)

@server.route('/')
def home():
    return "Monstro ezmny Online e a faturar."

def run_flask():
    # O Render injeta a porta nesta variável. É CRÍTICO usar 0.0.0.0
    port = int(os.environ.get("PORT", 5000))
    print(f"--> Flask a ouvir na porta {port}")
    server.run(host='0.0.0.0', port=port)

# --- 2. CONFIGURAÇÕES ---
GEMINI_KEY = os.environ.get("GEMINI_KEY")
TG_TOKEN = os.environ.get("TG_TOKEN")

# Nova forma de ligar ao Gemini em 2026
client = genai.Client(api_key=GEMINI_KEY)

# --- 3. LÓGICA DO BOT ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Estou online 24/7 no Render. O PC está desligado, mas eu continuo a vigiar-te.")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # Sintaxe 2026 para o Gemini
        response = client.models.generate_content(
            model="gemini-3-flash-preview", # Ou o 3-flash-preview que tens na lista
            contents=update.message.text,
            config={'system_instruction': "És o COO bruto de Coimbra. Dá passos técnicos e manda o João trabalhar."}
        )
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text(f"Erro: {e}")

# --- 4. EXECUÇÃO ---
if __name__ == '__main__':
    # Primeiro: Arrancamos a Flask numa thread para o Render não dar timeout
    t = threading.Thread(target=run_flask)
    t.daemon = True
    t.start()
    
    # Segundo: Arrancamos o Bot
    print("--> A ligar o Telegram...")
    application = Application.builder().token(TG_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Este comando bloqueia o código, por isso tem de ser o último
    application.run_polling()