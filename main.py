import os
import google.generativeai as genai
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes


# --- 1. CONFIGURAÇÕES (VERIFICA SE AS TUAS CHAVES ESTÃO AQUI) ---
GEMINI_KEY = os.environ.get("GEMINI_KEY")
TG_TOKEN = os.environ.get("TG_TOKEN")

# Configuração do Gemini
genai.configure(api_key=GEMINI_KEY)

# USANDO O GEMINI 3-FLASH (O ÚLTIMO GRITO DA TUA LISTA)
model = genai.GenerativeModel(
    model_name="gemini-3-flash-preview", 
    system_instruction=(
        "Tu és o COO de uma startup de automação de clínicas."
        "O teu tom é direto, profissional e focado em resultados."
        "A tua missão é guiar um Engenheiro de Coimbra na execução técnica."
        "Segue sempre esta estrutura: 1. Ação imediata (o que fazer); 2. Código/Passos; 3. Justificação (isto serve para...)."
        "Sê visionário, foca no ROI e na escalabilidade."
        "Não percas tempo com piadas repetitivas; foca na entrega do código."
        "Responde em Português de Portugal, de forma curta e bruta."
    )
)

# --- 2. LÓGICA ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Olá João. Tas fixe p trabalhar ou ja tas todo chapadão?")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    try:
        # Usando a engine de 2026
        response = model.generate_content(user_text)
        await update.message.reply_text(response.text)
    except Exception as e:
        await update.message.reply_text(f"Erro no meu cérebro 3.0: {e}")

# --- 3. RUN ---
if __name__ == '__main__':
    application = Application.builder().token(TG_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("COO 3.1 PRO ONLINE. VAI TRABALHAR, JOÃO.")
    application.run_polling()