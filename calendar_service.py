"""
calendar_service.py — Google Calendar integration para o COO Chato

SETUP (uma vez só, localmente):
    1. Cria projeto em console.cloud.google.com
    2. Ativa Calendar API
    3. Cria credenciais OAuth 2.0 (Desktop App) → faz download → guarda como credentials.json
    4. Corre: python setup_google_auth.py
    5. Copia o valor de GOOGLE_TOKEN_JSON e coloca nas env vars do Render
"""
import os
import json
import base64
import logging
from datetime import datetime, timedelta, timezone
import pytz

logger = logging.getLogger(__name__)

GOOGLE_TOKEN_JSON = os.environ.get("GOOGLE_TOKEN_JSON")  # base64 do token.json
LISBON_TZ = pytz.timezone("Europe/Lisbon")

SCOPES = ["https://www.googleapis.com/auth/calendar"]

_service = None


def _build_service():
    """Constrói o serviço do Google Calendar a partir do token em env var."""
    global _service
    if _service is not None:
        return _service

    if not GOOGLE_TOKEN_JSON:
        return None

    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
        from googleapiclient.discovery import build

        token_data = json.loads(base64.b64decode(GOOGLE_TOKEN_JSON).decode())
        creds = Credentials.from_authorized_user_info(token_data, SCOPES)

        # Refresh se expirado
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())

        _service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        logger.info("Google Calendar service iniciado com sucesso.")
        return _service
    except Exception as e:
        logger.error(f"Erro ao construir Google Calendar service: {e}")
        return None


def is_calendar_available() -> bool:
    """Verifica se o Calendar está configurado."""
    return _build_service() is not None


def get_today_events() -> list[str]:
    """
    Retorna lista de strings com os eventos de hoje.
    Formato: 'HH:MM — Título do evento'
    """
    service = _build_service()
    if not service:
        return []

    try:
        now_lisbon = datetime.now(LISBON_TZ)
        start_of_day = now_lisbon.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        events_result = service.events().list(
            calendarId="primary",
            timeMin=start_of_day.isoformat(),
            timeMax=end_of_day.isoformat(),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        items = events_result.get("items", [])
        formatted = []
        for item in items:
            summary = item.get("summary", "Sem título")
            start = item["start"].get("dateTime") or item["start"].get("date")
            if "T" in start:
                dt = datetime.fromisoformat(start).astimezone(LISBON_TZ)
                formatted.append(f"{dt.strftime('%H:%M')} — {summary}")
            else:
                formatted.append(f"Dia todo — {summary}")

        return formatted
    except Exception as e:
        logger.error(f"get_today_events error: {e}")
        return []


def get_upcoming_events(days: int = 3) -> list[str]:
    """Retorna eventos dos próximos N dias."""
    service = _build_service()
    if not service:
        return []

    try:
        now = datetime.now(LISBON_TZ)
        end = now + timedelta(days=days)

        result = service.events().list(
            calendarId="primary",
            timeMin=now.isoformat(),
            timeMax=end.isoformat(),
            singleEvents=True,
            orderBy="startTime",
            maxResults=10,
        ).execute()

        items = result.get("items", [])
        formatted = []
        for item in items:
            summary = item.get("summary", "Sem título")
            start = item["start"].get("dateTime") or item["start"].get("date")
            if "T" in start:
                dt = datetime.fromisoformat(start).astimezone(LISBON_TZ)
                formatted.append(f"{dt.strftime('%d/%m %H:%M')} — {summary}")
            else:
                formatted.append(f"{start} (dia todo) — {summary}")

        return formatted
    except Exception as e:
        logger.error(f"get_upcoming_events error: {e}")
        return []


def create_event(title: str, time_str: str, duration_hours: float = 1.0, description: str = "") -> str:
    """
    Cria um evento no Google Calendar para hoje.
    time_str: 'HH:MM' (hora de Lisboa)
    Retorna o link do evento.
    """
    service = _build_service()
    if not service:
        raise RuntimeError("Google Calendar não configurado.")

    now_lisbon = datetime.now(LISBON_TZ)
    hour, minute = map(int, time_str.split(":"))
    start_dt = now_lisbon.replace(hour=hour, minute=minute, second=0, microsecond=0)
    end_dt = start_dt + timedelta(hours=duration_hours)

    event = {
        "summary": title,
        "description": description or f"Criado pelo COO Chato em {now_lisbon.strftime('%d/%m/%Y %H:%M')}",
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/Lisbon"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Europe/Lisbon"},
    }

    created = service.events().insert(calendarId="primary", body=event).execute()
    return created.get("htmlLink", "")
