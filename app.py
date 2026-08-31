import copy
import calendar as month_calendar
import base64
from contextlib import contextmanager
import datetime as dt
from email.message import EmailMessage
import hashlib
import hmac
import html
import json
import os
import platform
import re
import sqlite3
import smtplib
import subprocess
import threading
import time
import uuid
from zoneinfo import ZoneInfo

import streamlit as st
from streamlit_calendar import calendar


st.set_page_config(
    page_title="Agenda Sem Fricção — v7",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed",
)


APP_TIMEZONE = ZoneInfo(os.environ.get("AGENDA_TIMEZONE", "America/Sao_Paulo"))


def local_now():
    """Horário local sem fuso, compatível com os valores salvos na agenda."""
    return dt.datetime.now(APP_TIMEZONE).replace(tzinfo=None)


TODAY = local_now().date()
NOW = local_now()
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()
DB_PATH = os.environ.get(
    "AGENDA_DB_PATH",
    os.path.join(os.getcwd(), "agenda_v7.db"),
)
REMINDER_REPEAT_MINUTES = 30
CURRENT_USER_NAME = os.environ.get("AGENDA_USER_NAME", "Matheus").strip() or "Vendedor"
CURRENT_ROLE = os.environ.get("AGENDA_ROLE", "manager").strip().lower()
PEOPLE = list(dict.fromkeys([CURRENT_USER_NAME, "Ana", "Bruno", "Carla", "Diego", "Fernanda"]))
TEAMS = {
    "Comercial": [CURRENT_USER_NAME, "Ana", "Bruno"],
    "Operações": ["Carla", "Diego"],
    "Gestão": [CURRENT_USER_NAME, "Fernanda"],
}
CATEGORY_COLORS = {
    "Retorno": "#ff5a52",
    "Reunião": "#0a84ff",
    "Foco": "#bf5af2",
    "Pessoal": "#ff9f0a",
    "Reserva": "#30d158",
}


st.markdown(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root { color-scheme: dark; }
html, body, [class*="css"] { font-family: Inter, -apple-system, BlinkMacSystemFont, "SF Pro Text", sans-serif; }
.stApp { background: radial-gradient(circle at 52% -20%, #292a2f 0, #17181b 40%, #101114 100%); color:#f5f5f7; }
[data-testid="stHeader"] { background: transparent; }
.block-container { max-width: 1500px; padding-top: 1.25rem; padding-bottom: 3rem; }
.hero { display:flex; justify-content:space-between; align-items:flex-end; padding: 8px 2px 18px; border-bottom:1px solid #32343a; margin-bottom:18px; }
.hero h1 { font-size:25px; letter-spacing:-.7px; margin:0; }
.hero p { margin:5px 0 0; color:#92949b; font-size:13px; }
.live { padding:7px 11px; background:#1e3327; color:#61dc84; border:1px solid #28583a; border-radius:999px; font-size:12px; }
.metric-row { display:grid; grid-template-columns:repeat(4,1fr); gap:10px; margin:0 0 16px; }
.metric { background:rgba(39,40,45,.85); border:1px solid #373940; border-radius:14px; padding:13px 15px; }
.metric .n { display:block; font-size:23px; font-weight:700; }
.metric .l { color:#92949b; font-size:11px; text-transform:uppercase; letter-spacing:.5px; }
.section-label { color:#94969d; font-size:11px; font-weight:700; letter-spacing:.75px; margin:9px 0 8px; text-transform:uppercase; }
.return-card { background:rgba(41,42,47,.92); border:1px solid #3a3c43; border-left:4px solid var(--accent); border-radius:12px; padding:12px 14px; margin:0 0 7px; }
.return-card.overdue { background:linear-gradient(90deg, rgba(126,36,36,.25), rgba(41,42,47,.92) 28%); }
.card-top { display:flex; justify-content:space-between; gap:12px; align-items:center; }
.card-title { font-weight:600; font-size:14px; }
.pill { border-radius:999px; padding:3px 8px; font-size:10px; font-weight:700; white-space:nowrap; }
.card-meta { color:#a2a4aa; font-size:12px; margin-top:5px; }
.card-note { color:#d6d6da; font-size:12px; margin-top:8px; padding-top:8px; border-top:1px solid #383a40; }
.empty { text-align:center; padding:35px; border:1px dashed #3b3d43; border-radius:14px; color:#8f9198; }
.small-note { color:#8f9198; font-size:11px; }
.search-hit { border-left:3px solid #0a84ff; padding:9px 12px; background:#24262b; border-radius:8px; margin-bottom:6px; }
div[data-testid="stButton"] button { border-radius:9px; border-color:#45474f; min-height:35px; }
div[data-testid="stButton"] button:hover { border-color:#0a84ff; color:#fff; }
div[data-baseweb="select"] > div, .stTextInput input, .stTextArea textarea, .stDateInput input, .stTimeInput input { background:#25262b !important; border-color:#3b3d44 !important; }
[data-testid="stDialog"] { color:#f5f5f7; }
.fc { --fc-border-color:#383a40; --fc-page-bg-color:#1d1e22; --fc-neutral-bg-color:#25262b; --fc-list-event-hover-bg-color:#292b31; color:#ececf0; }
.fc .fc-toolbar-title { font-size:1.05rem !important; text-transform:capitalize; }
.fc .fc-button { background:#303239 !important; border-color:#464851 !important; box-shadow:none !important; }
.fc .fc-button-active, .fc .fc-button:hover { background:#0a84ff !important; border-color:#0a84ff !important; }
.fc .fc-col-header-cell-cushion, .fc .fc-daygrid-day-number { color:#d8d8dc; }
.fc .fc-timegrid-now-indicator-line { border-color:#ff453a; border-width:2px; }
.fc .fc-timegrid-now-indicator-arrow { border-color:#ff453a; }
.fc-event { border:0 !important; border-radius:6px !important; padding:2px 4px !important; cursor:grab; }
@media(max-width:800px){ .metric-row{grid-template-columns:repeat(2,1fr)} .hero{align-items:flex-start;gap:10px}.hero h1{font-size:21px} }
</style>
""",
    unsafe_allow_html=True,
)


def uid():
    return uuid.uuid4().hex[:10]


def env_flag(name, default="0"):
    return os.environ.get(name, default).strip().lower() in {"1", "true", "yes", "on"}


def verify_password(password, encoded_hash, pepper=""):
    try:
        algorithm, iterations, salt_b64, digest_b64 = encoded_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        salt = base64.urlsafe_b64decode(salt_b64.encode())
        expected = base64.urlsafe_b64decode(digest_b64.encode())
        candidate = hashlib.pbkdf2_hmac(
            "sha256", (password + pepper).encode(), salt, int(iterations)
        )
        return hmac.compare_digest(candidate, expected)
    except Exception:
        return False


def logout():
    st.session_state.authenticated = False
    st.session_state.pop("v7_db_loaded", None)


def require_login():
    if not env_flag("AGENDA_AUTH_REQUIRED"):
        return

    username = os.environ.get("AGENDA_USERNAME", "").strip()
    password_hash = os.environ.get("AGENDA_PASSWORD_HASH", "").strip()
    pepper = os.environ.get("AGENDA_AUTH_PEPPER", "")
    if not username or not password_hash:
        st.error("O acesso ainda não foi configurado pelo administrador.")
        st.stop()

    if st.session_state.get("authenticated"):
        with st.sidebar:
            st.caption(f"Conectado como **{CURRENT_USER_NAME}**")
            st.button("Sair", use_container_width=True, on_click=logout)
        return

    locked_until = st.session_state.get("login_locked_until")
    if locked_until and local_now() < locked_until:
        seconds = max(1, int((locked_until - local_now()).total_seconds()))
        st.warning(f"Muitas tentativas. Aguarde {seconds} segundos para tentar novamente.")
        st.stop()

    left, center, right = st.columns([1, 1.1, 1])
    with center:
        st.markdown("## ⚡ Agenda Sem Fricção")
        st.caption("Entre para acessar sua agenda individual.")
        with st.form("login_form", clear_on_submit=False):
            entered_user = st.text_input("Usuário", autocomplete="username")
            entered_password = st.text_input("Senha", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Entrar", type="primary", use_container_width=True)
        if submitted:
            valid_user = hmac.compare_digest(entered_user.strip(), username)
            valid_password = verify_password(entered_password, password_hash, pepper)
            if valid_user and valid_password:
                st.session_state.authenticated = True
                st.session_state.login_attempts = 0
                st.session_state.pop("login_locked_until", None)
                st.rerun()
            attempts = st.session_state.get("login_attempts", 0) + 1
            st.session_state.login_attempts = attempts
            if attempts >= 5:
                st.session_state.login_attempts = 0
                st.session_state.login_locked_until = local_now() + dt.timedelta(seconds=60)
            st.error("Usuário ou senha incorretos.")
    st.stop()


def json_default(value):
    if isinstance(value, dt.datetime):
        return {"__type__": "datetime", "value": value.isoformat()}
    if isinstance(value, dt.date):
        return {"__type__": "date", "value": value.isoformat()}
    if isinstance(value, dt.time):
        return {"__type__": "time", "value": value.isoformat()}
    raise TypeError(f"Tipo não serializável: {type(value)}")


def json_hook(value):
    marker = value.get("__type__")
    if marker == "datetime":
        return dt.datetime.fromisoformat(value["value"])
    if marker == "date":
        return dt.date.fromisoformat(value["value"])
    if marker == "time":
        return dt.time.fromisoformat(value["value"])
    return value


def db_sql(query):
    return query.replace("?", "%s") if DATABASE_URL else query


def db_connect():
    if DATABASE_URL:
        import psycopg

        return psycopg.connect(DATABASE_URL, connect_timeout=10)
    connection = sqlite3.connect(DB_PATH, timeout=10)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA busy_timeout=10000")
    return connection


@contextmanager
def db_session():
    connection = db_connect()
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def init_db():
    with db_session() as connection:
        connection.execute("CREATE TABLE IF NOT EXISTS app_state (id INTEGER PRIMARY KEY CHECK(id=1), payload TEXT NOT NULL, updated_at TEXT NOT NULL)")
        connection.execute("CREATE TABLE IF NOT EXISTS sent_notifications (return_id TEXT NOT NULL, due_key TEXT NOT NULL, sent_at TEXT NOT NULL, PRIMARY KEY(return_id, due_key))")


def load_data():
    with db_session() as connection:
        row = connection.execute(db_sql("SELECT payload FROM app_state WHERE id=1")).fetchone()
    return json.loads(row[0], object_hook=json_hook) if row else None


def save_data(data=None):
    payload = json.dumps(data if data is not None else st.session_state.data, default=json_default, ensure_ascii=False)
    with db_session() as connection:
        connection.execute(
            db_sql("INSERT INTO app_state(id,payload,updated_at) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET payload=excluded.payload, updated_at=excluded.updated_at"),
            (payload, local_now().isoformat()),
        )


def ensure_v7_schema(data):
    data.setdefault("inbox", [])
    data.setdefault("review_queue", [])
    for item in data.get("returns", []):
        item.setdefault("last_contact", item.get("note", ""))
        item.setdefault("next_action", "Realizar o próximo contato")
        item.setdefault("crm_status", "Fora do CRM")
        item.setdefault("confidence", 1.0)
    return data


def send_macos_notification(title, body):
    script = 'on run argv\n display notification (item 2 of argv) with title (item 1 of argv)\nend run'
    completed = subprocess.run(["osascript", "-e", script, "--", title, body], capture_output=True, text=True, timeout=10)
    return completed.returncode == 0


def notification_channel():
    if os.environ.get("SMTP_HOST") and os.environ.get("AGENDA_NOTIFICATION_EMAIL"):
        return "e-mail"
    if platform.system() == "Darwin":
        return "notificação do macOS"
    return "não configurado"


def send_email_notification(title, body):
    host = os.environ.get("SMTP_HOST", "").strip()
    recipient = os.environ.get("AGENDA_NOTIFICATION_EMAIL", "").strip()
    if not host or not recipient:
        return False
    port = int(os.environ.get("SMTP_PORT", "587"))
    username = os.environ.get("SMTP_USER", "").strip()
    password = os.environ.get("SMTP_PASSWORD", "")
    sender = os.environ.get("SMTP_FROM", username or recipient).strip()
    message = EmailMessage()
    message["Subject"] = title
    message["From"] = sender
    message["To"] = recipient
    message.set_content(body)
    with smtplib.SMTP(host, port, timeout=15) as server:
        server.ehlo()
        if env_flag("SMTP_STARTTLS", "1"):
            server.starttls()
            server.ehlo()
        if username:
            server.login(username, password)
        server.send_message(message)
    return True


def send_notification(title, body):
    if os.environ.get("SMTP_HOST") and os.environ.get("AGENDA_NOTIFICATION_EMAIL"):
        return send_email_notification(title, body)
    if platform.system() == "Darwin":
        return send_macos_notification(title, body)
    return False


def notification_worker(stop_event):
    while not stop_event.wait(15):
        try:
            data = load_data()
            if not data:
                continue
            current = local_now()
            for item in data.get("returns", []):
                # Cada instância piloto envia apenas alertas do usuário configurado.
                if item.get("owner") != CURRENT_USER_NAME:
                    continue
                if item.get("status") in ["Concluído"]:
                    continue
                due = dt.datetime.combine(item["date"], item["time"])
                if due > current:
                    continue
                due_key = due.isoformat()
                with db_session() as connection:
                    previous = connection.execute(db_sql("SELECT sent_at FROM sent_notifications WHERE return_id=? AND due_key=?"), (item["id"], due_key)).fetchone()
                if previous:
                    last_sent = dt.datetime.fromisoformat(previous[0])
                    if current - last_sent < dt.timedelta(minutes=REMINDER_REPEAT_MINUTES):
                        continue
                body = f"{item.get('client', '')} · {item.get('next_action') or item.get('note', '')}"
                if send_notification(f"Retorno: {item['title']}", body):
                    with db_session() as connection:
                        connection.execute(
                            db_sql("INSERT INTO sent_notifications(return_id,due_key,sent_at) VALUES(?,?,?) "
                            "ON CONFLICT(return_id,due_key) DO UPDATE SET sent_at=excluded.sent_at"),
                            (item["id"], due_key, current.isoformat()),
                        )
        except Exception:
            time.sleep(5)


@st.cache_resource
def start_notification_service():
    stop_event = threading.Event()
    thread = threading.Thread(target=notification_worker, args=(stop_event,), daemon=True, name="agenda-notifications")
    thread.start()
    return stop_event


def base_data():
    if not env_flag("AGENDA_SEED_DEMO", "1"):
        return {"returns": [], "events": [], "inbox": [], "review_queue": []}
    return {
        "returns": [
            {
                "id": uid(), "title": "Retorno Nicolly sobre a vaga de TI", "client": "Nicolly Alves",
                "date": TODAY - dt.timedelta(days=1), "time": dt.time(9, 0), "status": "Pendente",
                "owner": CURRENT_USER_NAME, "note": "Confirmar disponibilidade para a próxima etapa e registrar o interesse.",
                "last_contact": "Recebeu a indicação para a vaga de TI.", "next_action": "Confirmar interesse e disponibilidade.", "crm_status": "Fora do CRM",
                "original": "retorno para Nicolly sobre vaga TI ontem às 9h", "history": ["Retorno criado a partir do bloco de notas."],
            },
            {
                "id": uid(), "title": "Ligar para Isabella", "client": "Isabella Martins",
                "date": TODAY, "time": dt.time(14, 0), "status": "Pendente",
                "owner": "Ana", "note": "Falar sobre a indicação recebida e combinar o próximo contato.",
                "last_contact": "Indicação recebida por mensagem.", "next_action": "Explicar a oportunidade e combinar o próximo passo.", "crm_status": "Precisa atualizar o CRM",
                "original": "Ligar para Isabella hoje às 14h", "history": ["Retorno criado por Ana."],
            },
            {
                "id": uid(), "title": "Retorno Rafael — proposta", "client": "Rafael Lima",
                "date": TODAY + dt.timedelta(days=1), "time": dt.time(10, 30), "status": "Aguardando resposta",
                "owner": CURRENT_USER_NAME, "note": "Proposta enviada; aguardar confirmação do cliente.",
                "last_contact": "Proposta enviada por e-mail.", "next_action": "Confirmar se recebeu e tirar dúvidas.", "crm_status": "CRM atualizado",
                "original": "Retorno para Rafael amanhã 10h30", "history": ["Proposta enviada.", "Status alterado para Aguardando resposta."],
            },
        ],
        "events": [
            {
                "id": uid(), "title": "Alinhamento semanal", "category": "Reunião", "date": TODAY,
                "start": dt.time(10, 0), "end": dt.time(11, 0), "owner": CURRENT_USER_NAME, "participants": ["Ana", "Bruno", "Carla"],
                "room": True, "teams": True, "status": "Confirmado", "note": "Prioridades da semana e pontos de bloqueio.", "recurrence": "Sem recorrência",
            },
            {
                "id": uid(), "title": "Bloco de foco — planejamento", "category": "Foco", "date": TODAY,
                "start": dt.time(15, 0), "end": dt.time(16, 30), "owner": CURRENT_USER_NAME, "participants": [],
                "room": False, "teams": False, "status": "Confirmado", "note": "Revisar planejamento trimestral.", "recurrence": "Sem recorrência",
            },
            {
                "id": uid(), "title": "Apresentação de resultados", "category": "Reunião", "date": TODAY + dt.timedelta(days=2),
                "start": dt.time(14, 0), "end": dt.time(15, 0), "owner": "Fernanda", "participants": [CURRENT_USER_NAME, "Ana", "Bruno", "Carla", "Diego"],
                "room": True, "teams": True, "status": "Confirmado", "note": "Apresentação mensal para a liderança.", "recurrence": "Mensal",
            },
        ],
        "inbox": [
            {"id": uid(), "raw": "falar com Mariana sobre os retornos da Renata", "created_at": NOW, "confidence": 0.35, "reason": "Data e horário não identificados"},
        ],
    }


require_login()
init_db()
if "v7_db_loaded" not in st.session_state:
    stored_data = load_data()
    if stored_data is None:
        stored_data = ensure_v7_schema(st.session_state.get("data", base_data()))
        save_data(stored_data)
    st.session_state.data = ensure_v7_schema(stored_data)
    st.session_state.v7_db_loaded = True
if os.environ.get("AGENDA_DISABLE_NOTIFICATIONS") != "1":
    start_notification_service()
if "undo" not in st.session_state:
    st.session_state.undo = []
if "notice" not in st.session_state:
    st.session_state.notice = ""
if "error_notice" not in st.session_state:
    st.session_state.error_notice = ""
if "selected_calendar_event" not in st.session_state:
    st.session_state.selected_calendar_event = None


def snapshot(action):
    st.session_state.undo.append((action, copy.deepcopy(st.session_state.data)))
    st.session_state.undo = st.session_state.undo[-8:]


def undo():
    if st.session_state.undo:
        action, data = st.session_state.undo.pop()
        st.session_state.data = data
        st.session_state.notice = f"Ação desfeita: {action}."
        save_data()


def fmt_date(value):
    if value == TODAY:
        return "Hoje"
    if value == TODAY + dt.timedelta(days=1):
        return "Amanhã"
    return value.strftime("%d/%m/%Y")


def due_datetime(item):
    return dt.datetime.combine(item["date"], item["time"])


def is_overdue(item):
    return item.get("status") != "Concluído" and due_datetime(item) < local_now()


@st.fragment(run_every="15s")
def show_in_app_reminders():
    """Mostra retornos vencidos enquanto o vendedor mantém o app aberto."""
    current = local_now()
    shown = st.session_state.setdefault("in_app_notifications", {})
    for item in st.session_state.data.get("returns", []):
        if item.get("owner") != CURRENT_USER_NAME or item.get("status") == "Concluído":
            continue
        due = due_datetime(item)
        if due > current:
            continue
        notification_key = f"{item['id']}:{due.isoformat()}"
        last_shown = shown.get(notification_key)
        if last_shown and current - last_shown < dt.timedelta(minutes=REMINDER_REPEAT_MINUTES):
            continue
        detail = item.get("next_action") or item.get("note") or item.get("client", "")
        st.toast(f"🔔 Retorno vencido: {item['title']}\n\n{detail}")
        shown[notification_key] = current


def esc(value):
    return html.escape(str(value or ""))


def expand_people(selected_team, selected_people):
    result = set(selected_people)
    if selected_team != "Nenhuma":
        result.update(TEAMS[selected_team])
    return sorted(result)


def room_conflict(date, start, end, ignore_id=None):
    for event in st.session_state.data["events"]:
        if event["id"] == ignore_id or event["status"] == "Cancelado" or not event["room"]:
            continue
        if event["date"] == date and start < event["end"] and end > event["start"]:
            return event
    return None


def find_return(return_id):
    return next((x for x in st.session_state.data["returns"] if x["id"] == return_id), None)


def find_event(event_id):
    return next((x for x in st.session_state.data["events"] if x["id"] == event_id), None)


def natural_preview(text):
    items = []
    weekdays = {"segunda": 0, "terça": 1, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sábado": 5, "sabado": 5, "domingo": 6}
    for raw in [line.strip() for line in text.splitlines() if line.strip()]:
        low = raw.lower()
        kind = "Retorno" if any(word in low for word in ["ligar", "retorno", "falar", "responder", "cliente", "contato"]) else "Reunião" if any(word in low for word in ["reunião", "reuniao", "alinhamento", "teams"]) else "Foco"
        date = TODAY
        ambiguous = False
        if "amanhã" in low or "amanha" in low:
            date = TODAY + dt.timedelta(days=1)
        elif "hoje" not in low:
            found_day = next((number for name, number in weekdays.items() if name in low), None)
            if found_day is not None:
                delta = (found_day - TODAY.weekday()) % 7
                date = TODAY + dt.timedelta(days=delta or 7)
                ambiguous = True
        match = re.search(r"\b([01]?\d|2[0-3])(?::([0-5]\d)|h(?:([0-5]\d))?)\b", low)
        hour = int(match.group(1)) if match else 9
        minute = int(match.group(2) or match.group(3) or 0) if match else 0
        person_match = re.search(r"(?:para|com)\s+([A-ZÁÉÍÓÚÂÊÔÃÕÇ][\wÀ-ÿ]+)", raw)
        person = person_match.group(1) if person_match else "A identificar"
        has_explicit_date = any(token in low for token in ["hoje", "amanhã", "amanha", *weekdays.keys()])
        confidence = 0.25 + (0.3 if match else 0) + (0.25 if has_explicit_date else 0) + (0.2 if person != "A identificar" else 0)
        if ambiguous:
            confidence = min(confidence, 0.7)
        items.append({"raw": raw, "kind": kind, "date": date, "time": dt.time(hour, minute), "duration": 60 if kind == "Reunião" else 30, "person": person, "ambiguous": ambiguous or not match, "confidence": min(1.0, confidence)})
    return items


def create_from_parsed(item, reviewed=False):
    if item["kind"] == "Retorno":
        st.session_state.data["returns"].append({
            "id": uid(), "title": item.get("title", item["raw"]), "client": item["person"],
            "date": item["date"], "time": item["time"], "status": "Pendente", "owner": CURRENT_USER_NAME,
            "note": item["raw"], "last_contact": "", "next_action": item["raw"], "crm_status": "Fora do CRM",
            "original": item["raw"], "confidence": item.get("confidence", 1.0),
            "history": ["Criado após revisão." if reviewed else "Criado automaticamente pela captura rápida."],
        })
    else:
        st.session_state.data["events"].append({
            "id": uid(), "title": item.get("title", item["raw"]), "category": item["kind"],
            "date": item["date"], "start": item["time"],
            "end": (dt.datetime.combine(item["date"], item["time"]) + dt.timedelta(minutes=item["duration"])).time(),
            "owner": CURRENT_USER_NAME, "participants": [item["person"]] if item["person"] != "A identificar" else [],
            "room": False, "teams": "teams" in item["raw"].lower(), "status": "Confirmado", "note": item["raw"],
            "recurrence": "Sem recorrência",
        })


@st.dialog("Remarcar retorno")
def reschedule_dialog(return_id, no_answer=False):
    item = find_return(return_id)
    if not item:
        st.warning("Retorno não encontrado.")
        return
    st.caption(item["title"])
    if no_answer:
        st.info("A tentativa sem resposta será registrada. Escolha quando o sistema deve lembrar novamente.")
    suggested_date = max(TODAY + dt.timedelta(days=1) if no_answer else TODAY, item["date"])
    default_mode = 1 if no_answer or item["date"] < TODAY else 0
    mode = st.radio("Quando?", ["Mesmo dia", "Outro dia"], horizontal=True, index=default_mode)
    new_date = item["date"] if mode == "Mesmo dia" else st.date_input("Nova data", value=suggested_date, min_value=TODAY)
    suggested_time = item["time"]
    if not no_answer and due_datetime(item) <= local_now():
        current = local_now().replace(second=0, microsecond=0)
        suggested_time = (current + dt.timedelta(minutes=15 - current.minute % 15)).time()
    new_time = st.time_input("Novo horário", value=suggested_time, step=900)
    note = st.text_area("Observação da remarcação", placeholder="Motivo ou orientação para o próximo contato")
    invalid_schedule = dt.datetime.combine(new_date, new_time) <= local_now()
    if invalid_schedule:
        st.warning("Escolha um horário futuro para que o lembrete possa ser enviado.")
    if st.button("Confirmar remarcação", type="primary", use_container_width=True, disabled=invalid_schedule):
        snapshot("remarcar retorno")
        old = f"{fmt_date(item['date'])} às {item['time'].strftime('%H:%M')}"
        item["date"], item["time"] = new_date, new_time
        if no_answer:
            item["status"] = "Sem resposta"
            item["last_contact"] = f"Tentativa sem resposta em {local_now().strftime('%d/%m/%Y às %H:%M')}."
            item["history"].append(f"Sem resposta. Nova tentativa em {fmt_date(new_date)} às {new_time.strftime('%H:%M')}. {note}".strip())
            st.session_state.notice = "Sem resposta registrado e nova tentativa agendada."
        else:
            item["status"] = "Remarcado"
            item["history"].append(f"Remarcado de {old} para {fmt_date(new_date)} às {new_time.strftime('%H:%M')}. {note}".strip())
            st.session_state.notice = "Retorno remarcado."
        save_data()
        st.rerun()


@st.dialog("Novo compromisso", width="large")
def new_event_dialog(prefill_date=None, duplicate_id=None, prefill_category=None):
    source = find_event(duplicate_id) if duplicate_id else None
    title = st.text_input("Título", value=(f"Cópia — {source['title']}" if source else ""))
    c1, c2, c3 = st.columns(3)
    categories = ["Reunião", "Foco", "Pessoal", "Reserva"]
    initial_category = source["category"] if source else (prefill_category or "Reunião")
    category = c1.selectbox("Categoria", categories, index=categories.index(initial_category))
    date = c2.date_input("Dia", value=prefill_date or (source["date"] if source else TODAY))
    recurrence = c3.selectbox("Recorrência", ["Sem recorrência", "Diária", "Semanal", "Mensal"], index=0)
    t1, t2 = st.columns(2)
    start = t1.time_input("Início", value=source["start"] if source else dt.time(9, 0), step=900)
    end = t2.time_input("Fim", value=source["end"] if source else dt.time(10, 0), step=900)
    owner = st.selectbox("Responsável", PEOPLE, index=PEOPLE.index(source["owner"]) if source else 0)
    p1, p2 = st.columns(2)
    team = p1.selectbox("Adicionar equipe inteira", ["Nenhuma", *TEAMS.keys()])
    selected = p2.multiselect("Participantes", PEOPLE, default=source["participants"] if source else [])
    participants = expand_people(team, selected)
    c1, c2 = st.columns(2)
    room = c1.checkbox("Usará a sala de reunião", value=source["room"] if source else category in ["Reunião", "Reserva"])
    teams = c2.checkbox("Terá chamada no Teams", value=source["teams"] if source else category == "Reunião")
    note = st.text_area("Observações", value=source["note"] if source else "", placeholder="Pauta, contexto, decisões esperadas…")
    if recurrence != "Sem recorrência":
        until = st.date_input("Repetir até", value=date + dt.timedelta(days=28), min_value=date)
    else:
        until = date
    conflict = room_conflict(date, start, end) if room else None
    if end <= start:
        st.warning("O horário final precisa ser posterior ao horário inicial.")
    if conflict:
        st.error(f"A sala já está reservada para “{conflict['title']}”, das {conflict['start'].strftime('%H:%M')} às {conflict['end'].strftime('%H:%M')}.")
    if st.button("Criar compromisso", type="primary", use_container_width=True, disabled=not title or end <= start or bool(conflict)):
        snapshot("criar compromisso")
        dates = [date]
        step = {"Diária": 1, "Semanal": 7}.get(recurrence)
        if step:
            cursor = date + dt.timedelta(days=step)
            while cursor <= until:
                dates.append(cursor)
                cursor += dt.timedelta(days=step)
        elif recurrence == "Mensal":
            cursor = date
            while True:
                month = cursor.month + 1
                year = cursor.year + (month - 1) // 12
                month = (month - 1) % 12 + 1
                day = min(date.day, month_calendar.monthrange(year, month)[1])
                cursor = dt.date(year, month, day)
                if cursor > until:
                    break
                dates.append(cursor)
        series = uid() if len(dates) > 1 else None
        created_count = 0
        skipped_count = 0
        for event_date in dates:
            if room and room_conflict(event_date, start, end):
                skipped_count += 1
                continue
            st.session_state.data["events"].append({"id": uid(), "series": series, "title": title, "category": category, "date": event_date, "start": start, "end": end, "owner": owner, "participants": participants, "room": room, "teams": teams, "status": "Confirmado", "note": note, "recurrence": recurrence})
            created_count += 1
        suffix = f"; {skipped_count} ocorrência(s) com conflito não foram criada(s)" if skipped_count else ""
        st.session_state.notice = f"{created_count} compromisso(s) criado(s){suffix}."
        save_data()
        st.rerun()


def calendar_events():
    result = []
    for event in st.session_state.data["events"]:
        if event["status"] == "Cancelado":
            continue
        start = dt.datetime.combine(event["date"], event["start"])
        end = dt.datetime.combine(event["date"], event["end"])
        result.append({
            "id": event["id"], "title": event["title"], "start": start.isoformat(), "end": end.isoformat(),
            "backgroundColor": CATEGORY_COLORS[event["category"]], "borderColor": CATEGORY_COLORS[event["category"]],
            "extendedProps": {"category": event["category"], "owner": event["owner"]},
        })
    for item in st.session_state.data["returns"]:
        if item["status"] == "Concluído":
            continue
        start = dt.datetime.combine(item["date"], item["time"])
        result.append({"id": f"r-{item['id']}", "title": f"↩ {item['title']}", "start": start.isoformat(), "end": (start + dt.timedelta(minutes=30)).isoformat(), "backgroundColor": CATEGORY_COLORS["Retorno"], "borderColor": CATEGORY_COLORS["Retorno"]})
    return result


show_in_app_reminders()


st.markdown(
    f"""<div class="hero"><div><h1>⚡ Agenda Sem Fricção <span style="color:#777;font-weight:500">v7</span></h1>
    <p>Capturar sem interromper • salvar sem risco • lembrar até resolver</p></div>
    <span class="live">● {NOW.strftime('%H:%M')} · salvo automaticamente</span></div>""",
    unsafe_allow_html=True,
)


if st.session_state.notice:
    st.success(st.session_state.notice, icon="✅")
    st.session_state.notice = ""
if st.session_state.error_notice:
    st.error(st.session_state.error_notice, icon="⚠️")
    st.session_state.error_notice = ""


top1, top2, top3 = st.columns([2.4, 1.1, 1])
with top1:
    search = st.text_input("Busca global", placeholder="Buscar cliente, observação, reunião ou participante…", label_visibility="collapsed")
with top2:
    scope_options = ["Minha agenda", "Visão do gestor"] if CURRENT_ROLE == "manager" else ["Minha agenda"]
    scope = st.selectbox("Escopo", scope_options, label_visibility="collapsed")
with top3:
    if st.session_state.undo:
        st.button(
            f"↶ Desfazer: {st.session_state.undo[-1][0]}",
            use_container_width=True,
            on_click=undo,
        )
    else:
        st.button("↶ Nada para desfazer", disabled=True, use_container_width=True)


if search:
    needle = search.lower().strip()
    hits = []
    for item in st.session_state.data["returns"]:
        hay = " ".join([item["title"], item["client"], item["note"], item["owner"], item["status"], item.get("last_contact", ""), item.get("next_action", ""), item.get("crm_status", "")]).lower()
        if needle in hay and (scope == "Visão do gestor" or item["owner"] == CURRENT_USER_NAME):
            hits.append(("Retorno", item["title"], f"{item['client']} · {fmt_date(item['date'])} · {item['owner']}", item["note"]))
    for item in st.session_state.data["events"]:
        hay = " ".join([item["title"], item["note"], item["owner"], *item["participants"]]).lower()
        if needle in hay and (scope == "Visão do gestor" or item["owner"] == CURRENT_USER_NAME or CURRENT_USER_NAME in item["participants"]):
            hits.append((item["category"], item["title"], f"{fmt_date(item['date'])} · {item['owner']}", item["note"]))
    st.markdown(f'<div class="section-label">{len(hits)} resultado(s) na busca</div>', unsafe_allow_html=True)
    for kind, title, meta, note in hits:
        st.markdown(f'<div class="search-hit"><b>{esc(kind)} · {esc(title)}</b><div class="card-meta">{esc(meta)}</div><div class="small-note">{esc(note)}</div></div>', unsafe_allow_html=True)
    if not hits:
        st.markdown('<div class="empty">Nenhum item encontrado neste escopo.</div>', unsafe_allow_html=True)
    st.stop()


returns = st.session_state.data["returns"]
overdue_count = sum(1 for x in returns if is_overdue(x))
today_count = sum(1 for x in returns if x["date"] == TODAY and x["status"] != "Concluído")
waiting_count = sum(1 for x in returns if x["status"] == "Aguardando resposta")
room_today = sum(1 for x in st.session_state.data["events"] if x["date"] == TODAY and x["room"] and x["status"] != "Cancelado")
inbox_count = len(st.session_state.data.get("inbox", []))
st.markdown(f"""<div class="metric-row">
<div class="metric"><span class="n" style="color:#ff6b64">{overdue_count}</span><span class="l">Retornos esquecidos</span></div>
<div class="metric"><span class="n">{today_count}</span><span class="l">Retornos de hoje</span></div>
<div class="metric"><span class="n" style="color:#ffd060">{waiting_count}</span><span class="l">Aguardando resposta</span></div>
<div class="metric"><span class="n" style="color:#bf5af2">{inbox_count}</span><span class="l">Para revisar na caixa</span></div>
</div>""", unsafe_allow_html=True)


page = st.radio(
    "Navegação",
    ["✦ Captura rápida", "↩ Retornos", "▦ Calendário", "▣ Sala de reunião"],
    horizontal=True,
    label_visibility="collapsed",
    key="main_navigation",
)
st.divider()


if page == "↩ Retornos":
    f1, f2, f3, f4, f5 = st.columns([1.25, 1.15, 1.1, .9, 1.25])
    status_filter = f1.multiselect("Status", ["Pendente", "Aguardando resposta", "Sem resposta", "Remarcado", "Concluído"], default=["Pendente", "Aguardando resposta", "Sem resposta", "Remarcado"])
    owner_filter = f2.multiselect("Responsável", PEOPLE, default=[] if scope == "Visão do gestor" else [CURRENT_USER_NAME])
    client_filter = f3.text_input("Cliente contém", placeholder="Todos")
    period_filter = f4.selectbox("Período", ["Todos", "Atrasados", "Hoje", "Próximos"])
    crm_filter = f5.multiselect("CRM", ["Fora do CRM", "Precisa atualizar o CRM", "CRM atualizado"], default=[])
    filtered = []
    for item in returns:
        if item["status"] not in status_filter:
            continue
        if owner_filter and item["owner"] not in owner_filter:
            continue
        if client_filter and client_filter.lower() not in item["client"].lower():
            continue
        if period_filter == "Atrasados" and not is_overdue(item):
            continue
        if period_filter == "Hoje" and item["date"] != TODAY:
            continue
        if period_filter == "Próximos" and item["date"] <= TODAY:
            continue
        if crm_filter and item.get("crm_status") not in crm_filter:
            continue
        filtered.append(item)
    filtered.sort(key=lambda x: (x["date"], x["time"]))
    st.markdown(f'<div class="section-label">{len(filtered)} retorno(s)</div>', unsafe_allow_html=True)
    for item in filtered:
        late = is_overdue(item)
        color = "#ff453a" if late else "#ffd60a" if item["status"] == "Aguardando resposta" else "#0a84ff"
        badge_bg = "#552a29" if late else "#353326"
        if late:
            delay = local_now() - due_datetime(item)
            badge = f"ATRASADO · {delay.days}D" if delay.days else f"ATRASADO · {max(1, delay.seconds // 3600)}H"
        else:
            badge = item["status"].upper()
        st.markdown(f"""<div class="return-card {'overdue' if late else ''}" style="--accent:{color}">
        <div class="card-top"><div class="card-title">{esc(item['title'])}</div><span class="pill" style="background:{badge_bg};color:{color}">{esc(badge)}</span></div>
        <div class="card-meta">{esc(fmt_date(item['date']))} · {item['time'].strftime('%H:%M')} &nbsp; | &nbsp; {esc(item['client'])} &nbsp; | &nbsp; Responsável: {esc(item['owner'])}</div>
        <div class="card-note"><b>Último contato:</b> {esc(item.get('last_contact') or 'Ainda não registrado')}<br><b>Próxima ação:</b> {esc(item.get('next_action') or item['note'])}<br><span style="color:#8e8e93">{esc(item.get('crm_status', 'Fora do CRM'))}</span></div></div>""", unsafe_allow_html=True)
        b1, b2, b3, b4, b5 = st.columns([1, 1.15, 1.1, 1, 2.5])
        if b1.button("✓ Feito", key=f"done-{item['id']}", disabled=item["status"] == "Concluído", use_container_width=True):
            snapshot("concluir retorno")
            item["status"] = "Concluído"
            item["history"].append(f"Concluído em {NOW.strftime('%d/%m/%Y %H:%M')}.")
            st.session_state.notice = "Retorno concluído."
            save_data()
            st.rerun()
        if b2.button("Sem resposta", key=f"no-{item['id']}", use_container_width=True):
            reschedule_dialog(item["id"], no_answer=True)
        if b3.button("Remarcar", key=f"move-{item['id']}", use_container_width=True):
            reschedule_dialog(item["id"])
        if b4.button("+15 min", key=f"delay-{item['id']}", use_container_width=True):
            snapshot("adiar retorno em 15 minutos")
            stamp = max(local_now(), due_datetime(item)) + dt.timedelta(minutes=15)
            item["date"], item["time"], item["status"] = stamp.date(), stamp.time(), "Remarcado"
            item["history"].append("Adiado em 15 minutos.")
            st.session_state.notice = "Retorno adiado em 15 minutos."
            save_data()
            st.rerun()
        with st.expander("Observação e histórico", expanded=False):
            new_last = st.text_area("Último contato — o que foi falado", value=item.get("last_contact", ""), key=f"last-{item['id']}")
            new_next = st.text_area("Próxima ação — o que ainda precisa ser feito", value=item.get("next_action", ""), key=f"next-{item['id']}")
            new_note = st.text_area("Observações adicionais", value=item["note"], key=f"note-{item['id']}")
            new_crm = st.selectbox("Situação no CRM", ["Fora do CRM", "Precisa atualizar o CRM", "CRM atualizado"], index=["Fora do CRM", "Precisa atualizar o CRM", "CRM atualizado"].index(item.get("crm_status", "Fora do CRM")), key=f"crm-{item['id']}")
            if st.button("Salvar informações", key=f"save-note-{item['id']}"):
                snapshot("editar observação")
                item["note"] = new_note
                item["last_contact"] = new_last
                item["next_action"] = new_next
                item["crm_status"] = new_crm
                item["history"].append("Observação atualizada.")
                st.session_state.notice = "Contato, próxima ação e CRM atualizados."
                save_data()
                st.rerun()
            st.caption(f"Anotação original: {item['original']}")
            if scope == "Visão do gestor":
                st.markdown("**Histórico visível para o gestor**")
                for entry in reversed(item["history"]):
                    st.write(f"• {entry}")


elif page == "▦ Calendário":
    h1, h2 = st.columns([4, 1])
    h1.caption("Arraste um evento para remarcar. A linha vermelha indica o horário atual.")
    if h2.button("＋ Novo compromisso", type="primary", use_container_width=True):
        new_event_dialog()
    options = {
        "editable": True,
        "selectable": True,
        "nowIndicator": True,
        "locale": "pt-br",
        "initialDate": TODAY.isoformat(),
        "initialView": "timeGridWeek",
        "slotMinTime": "07:00:00",
        "slotMaxTime": "20:00:00",
        "height": 690,
        "allDaySlot": False,
        "headerToolbar": {"left": "today prev,next", "center": "title", "right": "timeGridDay,timeGridWeek,dayGridMonth"},
        "buttonText": {"today": "Hoje", "day": "Dia", "week": "Semana", "month": "Mês"},
    }
    calendar_key = f"agenda-v7-calendar-{st.session_state.get('calendar_revision', 0)}"
    state = calendar(events=calendar_events(), options=options, custom_css=".fc-event-title{font-weight:600}.fc-timegrid-slot{height:2.4em}", callbacks=["eventClick", "eventChange", "dateClick"], key=calendar_key)
    if state.get("dateClick"):
        clicked_date = state["dateClick"].get("dateStr") or state["dateClick"].get("date")
        click_signature = str(clicked_date)
        if clicked_date and st.session_state.get("last_date_click") != click_signature:
            st.session_state.last_date_click = click_signature
            clicked_day = dt.datetime.fromisoformat(str(clicked_date).replace("Z", "+00:00")).date()
            new_event_dialog(prefill_date=clicked_day)
    if state.get("eventClick"):
        clicked = state["eventClick"].get("event", state["eventClick"])
        st.session_state.selected_calendar_event = clicked.get("id")
    if state.get("eventChange"):
        changed = state["eventChange"].get("event", state["eventChange"])
        signature = f"{changed.get('id')}-{changed.get('start')}-{changed.get('end')}"
        if st.session_state.get("last_calendar_change") != signature:
            event_id = changed.get("id", "")
            start_value = changed.get("start")
            end_value = changed.get("end")
            if start_value and event_id:
                start_dt = dt.datetime.fromisoformat(start_value.replace("Z", "+00:00"))
                end_dt = dt.datetime.fromisoformat(end_value.replace("Z", "+00:00")) if end_value else start_dt + dt.timedelta(hours=1)
                change_saved = False
                if event_id.startswith("r-"):
                    item = find_return(event_id[2:])
                    if item:
                        snapshot("arrastar retorno no calendário")
                        item["date"], item["time"], item["status"] = start_dt.date(), start_dt.time().replace(tzinfo=None), "Remarcado"
                        item["history"].append("Remarcado por arrastar no calendário.")
                        change_saved = True
                else:
                    event = find_event(event_id)
                    if event:
                        conflict = room_conflict(start_dt.date(), start_dt.time().replace(tzinfo=None), end_dt.time().replace(tzinfo=None), event["id"]) if event["room"] else None
                        if conflict:
                            st.session_state.error_notice = f"Alteração não salva: a sala conflita com “{conflict['title']}”."
                            st.session_state.calendar_revision = st.session_state.get("calendar_revision", 0) + 1
                        else:
                            snapshot("arrastar compromisso no calendário")
                            event["date"] = start_dt.date()
                            event["start"], event["end"] = start_dt.time().replace(tzinfo=None), end_dt.time().replace(tzinfo=None)
                            change_saved = True
                st.session_state.last_calendar_change = signature
                if change_saved:
                    st.session_state.notice = "Novo horário salvo."
                    save_data()
                st.rerun()
    selected_id = st.session_state.selected_calendar_event
    if selected_id:
        if selected_id.startswith("r-"):
            item = find_return(selected_id[2:])
            if item:
                st.info(f"**{item['title']}** · {fmt_date(item['date'])} às {item['time'].strftime('%H:%M')}\n\n{item['note']}")
        else:
            event = find_event(selected_id)
            if event:
                st.markdown(f"**{event['title']}** · {event['category']} · {fmt_date(event['date'])}, {event['start'].strftime('%H:%M')}–{event['end'].strftime('%H:%M')}")
                st.caption(f"Responsável: {event['owner']} · Sala: {'sim' if event['room'] else 'não'} · Teams: {'sim' if event['teams'] else 'não'} · Participantes: {', '.join(event['participants']) or 'nenhum'}")
                st.write(event["note"])
                e1, e2 = st.columns(2)
                if e1.button("Duplicar evento", use_container_width=True):
                    new_event_dialog(duplicate_id=event["id"])
                cancel_label = "Cancelar e liberar sala" if event["room"] else "Cancelar compromisso"
                if e2.button(cancel_label, type="secondary", use_container_width=True):
                    snapshot("cancelar compromisso")
                    event["status"] = "Cancelado"
                    event["room"] = False
                    st.session_state.selected_calendar_event = None
                    st.session_state.notice = "Compromisso cancelado e sala liberada."
                    save_data()
                    st.rerun()


elif page == "✦ Captura rápida":
    left, right = st.columns([1.05, 1.2], gap="large")
    with left:
        st.markdown('<div class="section-label">Anote agora — organize depois</div>', unsafe_allow_html=True)
        with st.form("quick-capture", clear_on_submit=True):
            note_text = st.text_area(
                "Captura rápida",
                placeholder="Ex.: ligar para Isabella amanhã às 14h sobre a vaga\nVocê pode escrever várias linhas.",
                height=220,
                label_visibility="collapsed",
            )
            always_review = st.checkbox("Quero revisar tudo antes de agendar", value=False)
            submitted = st.form_submit_button("Salvar agora", type="primary", use_container_width=True)
        st.caption("⌘ Enter para concluir o texto. Tudo é salvo no banco; informações incompletas vão para a caixa de entrada.")
        external_channel = notification_channel()
        reminder_label = "no aplicativo" if external_channel == "não configurado" else f"no aplicativo e por {external_channel}"
        with st.expander(f"🔔 Lembretes {reminder_label}", expanded=False):
            st.caption("Com esta página aberta, o alerta aparece aqui a cada 30 minutos enquanto o retorno estiver pendente. O envio fora do aplicativo exige configurar e-mail.")
            if st.button("Enviar notificação de teste", use_container_width=True):
                st.toast("🔔 Notificação de teste: os lembretes dentro da agenda estão funcionando.")
                if external_channel != "não configurado" and send_notification("Agenda Sem Fricção", "Notificações ativas. Seus retornos serão lembrados até serem resolvidos."):
                    st.success(f"Teste exibido no aplicativo e enviado por {external_channel}.")
                else:
                    st.success("Teste exibido. Mantenha a agenda aberta para receber os alertas do piloto.")
        if submitted and note_text.strip():
            snapshot("capturar anotações")
            parsed_items = natural_preview(note_text)
            auto_count = 0
            inbox_added = 0
            review_items = []
            for item in parsed_items:
                if always_review:
                    review_items.append(item)
                elif item["confidence"] >= 0.8 and not item["ambiguous"]:
                    create_from_parsed(item)
                    auto_count += 1
                else:
                    st.session_state.data["inbox"].append({
                        "id": uid(), "raw": item["raw"], "created_at": local_now(),
                        "confidence": item["confidence"],
                        "reason": "Data ou horário ambíguo" if item["ambiguous"] else "Informações incompletas",
                    })
                    inbox_added += 1
            st.session_state.data["review_queue"] = review_items
            st.session_state.notice = f"{auto_count} item(ns) agendado(s) e {inbox_added} guardado(s) para revisão."
            save_data()
            st.rerun()

        st.markdown('<div class="section-label">Como o sistema decidiu</div>', unsafe_allow_html=True)
        st.markdown("""
        <div class="small-note">● <b style="color:#61dc84">Alta confiança</b>: agenda imediatamente.<br>
        ● <b style="color:#ffd060">Alguma dúvida</b>: salva na caixa de entrada.<br>
        ● A anotação original nunca é descartada.</div>
        """, unsafe_allow_html=True)

    with right:
        st.markdown(f'<div class="section-label">Caixa de entrada · {len(st.session_state.data["inbox"])} para revisar</div>', unsafe_allow_html=True)
        if not st.session_state.data["inbox"] and not st.session_state.data["review_queue"]:
            st.markdown('<div class="empty">Tudo organizado. Você pode continuar anotando sem interromper o que está fazendo.</div>', unsafe_allow_html=True)

        review_queue = st.session_state.data["review_queue"]
        for index, item in enumerate(review_queue):
            with st.container(border=True):
                st.caption("REVISÃO SOLICITADA")
                c1, c2, c3 = st.columns([1.2, 1, 1])
                item["kind"] = c1.selectbox("Tipo", ["Retorno", "Reunião", "Foco", "Pessoal"], index=["Retorno", "Reunião", "Foco", "Pessoal"].index(item["kind"]), key=f"pv-kind-{index}")
                item["date"] = c2.date_input("Data", value=item["date"], key=f"pv-date-{index}")
                item["time"] = c3.time_input("Horário", value=item["time"], key=f"pv-time-{index}")
                item["person"] = st.text_input("Pessoa/cliente", value=item["person"], key=f"pv-person-{index}")
                item["title"] = st.text_input("Título", value=item["raw"], key=f"pv-title-{index}")
        if review_queue and st.button("Confirmar itens revisados", type="primary", use_container_width=True):
            for item in review_queue:
                create_from_parsed(item, reviewed=True)
            st.session_state.data["review_queue"] = []
            st.session_state.notice = f"{len(review_queue)} item(ns) revisado(s) e agendado(s)."
            save_data()
            st.rerun()

        for inbox_item in list(st.session_state.data["inbox"]):
            with st.container(border=True):
                st.markdown(f"**{esc(inbox_item['raw'])}**")
                confidence_pct = round(inbox_item.get("confidence", 0) * 100)
                st.caption(f"{inbox_item.get('reason', 'Revisão necessária')} · confiança {confidence_pct}% · salvo {inbox_item['created_at'].strftime('%d/%m %H:%M')}")
                parsed = natural_preview(inbox_item["raw"])[0]
                c1, c2, c3 = st.columns([1.2, 1, 1])
                kind = c1.selectbox("Tipo", ["Retorno", "Reunião", "Foco", "Pessoal"], index=["Retorno", "Reunião", "Foco", "Pessoal"].index(parsed["kind"]), key=f"in-kind-{inbox_item['id']}")
                date = c2.date_input("Data", value=parsed["date"], key=f"in-date-{inbox_item['id']}")
                due_time = c3.time_input("Horário", value=parsed["time"], key=f"in-time-{inbox_item['id']}")
                person = st.text_input("Pessoa/cliente", value=parsed["person"], key=f"in-person-{inbox_item['id']}")
                if st.button("Agendar e retirar da caixa", key=f"process-in-{inbox_item['id']}", use_container_width=True):
                    snapshot("processar caixa de entrada")
                    parsed.update({"kind": kind, "date": date, "time": due_time, "person": person, "title": inbox_item["raw"], "confidence": 1.0})
                    create_from_parsed(parsed, reviewed=True)
                    st.session_state.data["inbox"].remove(inbox_item)
                    st.session_state.notice = "Item processado sem perder a anotação original."
                    save_data()
                    st.rerun()


elif page == "▣ Sala de reunião":
    h1, h2 = st.columns([3, 1])
    selected_date = h1.date_input("Dia da sala", value=TODAY, min_value=TODAY - dt.timedelta(days=30))
    if h2.button("＋ Fazer reserva", type="primary", use_container_width=True):
        new_event_dialog(prefill_date=selected_date, prefill_category="Reserva")
    room_events = sorted([x for x in st.session_state.data["events"] if x["date"] == selected_date and x["room"] and x["status"] != "Cancelado"], key=lambda x: x["start"])
    st.markdown(f'<div class="section-label">Sala de reunião · {fmt_date(selected_date)}</div>', unsafe_allow_html=True)
    if not room_events:
        st.markdown('<div class="empty">Sala disponível durante todo o dia.</div>', unsafe_allow_html=True)
    for event in room_events:
        st.markdown(f"""<div class="return-card" style="--accent:#30d158"><div class="card-top"><div class="card-title">{event['start'].strftime('%H:%M')}–{event['end'].strftime('%H:%M')} · {esc(event['title'])}</div><span class="pill" style="background:#1d4a2a;color:#61dc84">RESERVADA</span></div>
        <div class="card-meta">Responsável: {esc(event['owner'])} · Teams: {'Sim' if event['teams'] else 'Não'} · Recorrência: {esc(event['recurrence'])}</div>
        <div class="card-note">Participantes: {esc(', '.join(event['participants']) or 'não informados')}<br>✎ {esc(event['note'])}</div></div>""", unsafe_allow_html=True)
        c1, c2 = st.columns([1, 4])
        release_label = "Cancelar reserva" if event["category"] == "Reserva" else "Liberar sala"
        if c1.button(release_label, key=f"cancel-room-{event['id']}"):
            snapshot("cancelar reserva")
            event["room"] = False
            event["status"] = "Cancelado" if event["category"] == "Reserva" else event["status"]
            st.session_state.notice = "Reserva cancelada e sala liberada."
            save_data()
            st.rerun()
        c2.caption("Se a reunião for cancelada no calendário, a sala também será liberada automaticamente.")
