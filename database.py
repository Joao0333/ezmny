"""
database.py — Supabase client + todas as operações de DB para o COO Chato
Tabelas: promises, messages, users
"""
import os
import logging
from datetime import datetime, timezone
from supabase import create_client, Client

logger = logging.getLogger(__name__)

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

_client: Client = None

def get_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL e SUPABASE_KEY têm de estar definidas nas env vars.")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


# ── USERS ──────────────────────────────────────────────────────────────────

def register_user(user_id: int, first_name: str = "João"):
    """Regista o utilizador na DB (upsert)."""
    try:
        get_client().table("users").upsert({
            "user_id": user_id,
            "first_name": first_name,
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.error(f"register_user error: {e}")


def update_last_seen(user_id: int):
    """Atualiza o timestamp da última mensagem do utilizador."""
    try:
        get_client().table("users").upsert({
            "user_id": user_id,
            "last_seen": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.error(f"update_last_seen error: {e}")


def get_last_seen(user_id: int):
    """Retorna datetime da última mensagem ou None."""
    try:
        result = get_client().table("users").select("last_seen").eq("user_id", user_id).execute()
        if result.data:
            raw = result.data[0]["last_seen"]
            return datetime.fromisoformat(raw)
    except Exception as e:
        logger.error(f"get_last_seen error: {e}")
    return None


# ── MESSAGES (histórico de conversa) ───────────────────────────────────────

def save_message(user_id: int, role: str, content: str):
    """Guarda uma mensagem no histórico (role: 'user' ou 'assistant')."""
    try:
        get_client().table("messages").insert({
            "user_id": user_id,
            "role": role,
            "content": content,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }).execute()
    except Exception as e:
        logger.error(f"save_message error: {e}")


def get_recent_history(user_id: int, limit: int = 12) -> list[dict]:
    """Busca as últimas N mensagens do utilizador (ordem cronológica)."""
    try:
        result = (
            get_client()
            .table("messages")
            .select("role, content, created_at")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(reversed(result.data or []))
    except Exception as e:
        logger.error(f"get_recent_history error: {e}")
        return []


# ── PROMISES ───────────────────────────────────────────────────────────────

def save_promise(user_id: int, promise_text: str, deadline: str = None):
    """Guarda uma nova promessa."""
    try:
        row = {
            "user_id": user_id,
            "promise_text": promise_text,
            "fulfilled": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        if deadline:
            row["deadline"] = deadline
        get_client().table("promises").insert(row).execute()
        logger.info(f"Promessa guardada: {promise_text}")
    except Exception as e:
        logger.error(f"save_promise error: {e}")


def get_open_promises(user_id: int) -> list[dict]:
    """Retorna todas as promessas não cumpridas."""
    try:
        result = (
            get_client()
            .table("promises")
            .select("id, promise_text, created_at, deadline")
            .eq("user_id", user_id)
            .eq("fulfilled", False)
            .order("created_at", desc=False)
            .execute()
        )
        return result.data or []
    except Exception as e:
        logger.error(f"get_open_promises error: {e}")
        return []


def mark_promise_fulfilled(promise_id: str):
    """Marca uma promessa como cumprida."""
    try:
        get_client().table("promises").update({
            "fulfilled": True,
            "fulfilled_at": datetime.now(timezone.utc).isoformat(),
        }).eq("id", promise_id).execute()
    except Exception as e:
        logger.error(f"mark_promise_fulfilled error: {e}")
