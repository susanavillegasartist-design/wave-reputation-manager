from __future__ import annotations

import hashlib
import hmac
import html
import io
import json
import logging
import os
import re
import secrets
import smtplib
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from email.message import EmailMessage
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from fastapi import Cookie, Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
import stripe

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")
POLICIES_PATH = BASE_DIR / "google_policies.json"
DB_PATH = BASE_DIR / "claims.db"
SESSION_COOKIE = "wave_session"
PASSWORD_ITERATIONS = 260_000
SESSION_SECRET = os.environ.get("WAVE_SESSION_SECRET", "wave-dev-session-secret-change-me")
PLAN_NAMES = {"free": "Free", "basic": "Basic", "pro": "Pro"}
PLAN_LIMITS = {"free": 1, "basic": 10, "pro": None}
STRIPE_PRICE_TO_PLAN = {
    os.environ.get("STRIPE_PRICE_ID_BASIC", ""): "basic",
    os.environ.get("STRIPE_PRICE_ID_PRO", ""): "pro",
}
STRIPE_PRICE_TO_PLAN = {price_id: plan for price_id, plan in STRIPE_PRICE_TO_PLAN.items() if price_id}
APP_BASE_URL = os.environ.get("APP_BASE_URL", "http://localhost:8000").rstrip("/")
SMTP_FROM_EMAIL = os.environ.get("SMTP_FROM_EMAIL", "soporte@wavemusicbusiness.com")
SMTP_FROM_NAME = os.environ.get("SMTP_FROM_NAME", "Wave Music Business")
WELCOME_EMAIL_RECIPIENT_PLANS = {"basic", "pro"}
WELCOME_EMAIL_SUBJECTS = {
    "basic": "Bienvenida a Wave Reputation Manager — Plan Basic activado",
    "pro": "Bienvenida a Wave Reputation Manager — Plan Pro activado",
}
WELCOME_EMAIL_BODIES = {
    "basic": """Hola,

Gracias por suscribirte a Wave Reputation Manager.

Tu Plan Basic mensual de 9,99 €/mes ya está activo.

Desde tu panel podrás analizar reseñas negativas, detectar posibles incumplimientos de políticas y generar reclamaciones profesionales adaptadas a tu caso.

Accede aquí:
https://reputation.wavemusicbusiness.com

Si necesitas ayuda, puedes escribirnos a:
soporte@wavemusicbusiness.com

Gracias por confiar en Wave Music Business.

Un saludo,
Equipo de Wave Music Business""",
    "pro": """Hola,

Gracias por suscribirte a Wave Reputation Manager.

Tu Plan Pro mensual de 24,99 €/mes ya está activo.

Desde tu panel podrás analizar reseñas negativas, detectar posibles incumplimientos de políticas y generar reclamaciones profesionales adaptadas a tu caso, con acceso ilimitado según las condiciones del plan.

Accede aquí:
https://reputation.wavemusicbusiness.com

Si necesitas ayuda, puedes escribirnos a:
soporte@wavemusicbusiness.com

Gracias por confiar en Wave Music Business.

Un saludo,
Equipo de Wave Music Business""",
}
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY")
logger = logging.getLogger("wave.billing")

app = FastAPI(title="Wave Reputation Manager", version="1.1.0")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@dataclass(frozen=True)
class DetectionRule:
    policy_id: str
    keywords: tuple[str, ...]
    weight: int
    evidence_prompt: str


RULES = (
    DetectionRule(
        "experiencia_no_genuina",
        ("nunca fui", "no he ido", "no fui", "me contaron", "me han dicho", "dicen que", "sin visitar", "fake", "falso cliente"),
        3,
        "Registros de reservas, tickets, cámaras, agenda o CRM que permitan verificar si hubo visita o interacción real.",
    ),
    DetectionRule(
        "conflicto_intereses",
        ("competidor", "ex empleado", "exempleado", "trabajé allí", "proveedor", "socio", "familiar", "despedido", "despido"),
        3,
        "Pruebas del vínculo laboral, comercial, familiar o competitivo que pueda comprometer la imparcialidad.",
    ),
    DetectionRule(
        "manipulacion_valoracion",
        ("si no", "más reseñas", "varias cuentas", "pagar", "dinero", "descuento", "chantaje", "compensación", "campaña", "boicot"),
        3,
        "Capturas de amenazas, patrones de reseñas similares, fechas de publicación y comunicaciones previas.",
    ),
    DetectionRule(
        "contenido_ofensivo",
        ("idiota", "estafa", "estafador", "basura", "asco", "mierda", "imbécil", "ladrón", "ladrones", "amenaza", "odio"),
        2,
        "Captura de las expresiones ofensivas o amenazantes y explicación de por qué exceden una crítica legítima.",
    ),
    DetectionRule(
        "suplantacion",
        ("soy el dueño", "represento", "oficial", "empleado de", "en nombre de", "suplant", "identidad", "marca"),
        3,
        "Documentos o capturas que acrediten que el perfil usa una identidad, marca o representación no autorizada.",
    ),
    DetectionRule(
        "informacion_falsa_enganosa",
        ("cerrado", "nunca abre", "sin licencia", "ilegal", "denunciado", "sanción", "plaga", "enfermedad", "roban", "fraude"),
        2,
        "Horarios oficiales, facturas, comunicaciones, licencias, registros o documentos que refuten afirmaciones verificables.",
    ),
    DetectionRule(
        "datos_personales",
        ("teléfono", "telefono", "dirección", "direccion", "dni", "correo", "email", "médico", "salud", "apellido", "vive en", "cuenta bancaria"),
        4,
        "Captura señalando datos personales o sensibles publicados sin consentimiento, evitando replicarlos más de lo necesario.",
    ),
    DetectionRule(
        "contenido_irrelevante",
        ("política", "politica", "gobierno", "religión", "religion", "spam", "publicidad", "mi canal", "visita mi", "noticia", "viral"),
        2,
        "Explicación de por qué el texto no describe una experiencia de cliente ni guarda relación con el negocio.",
    ),
)

LEGAL_OWNER = {
    "name": "Wave Music Business",
    "tax_id": "77590331S",
    "address": "Calle Arjona, Local Bajo, 41001 Sevilla",
    "email": "soporte@wavemusicbusiness.com",
    "web": "www.wavemusicbusiness.com",
}
LEGAL_CONTACT_HTML = (
    'Wave Music Business, NIF/CIF 77590331S, domicilio en Calle Arjona, Local Bajo, 41001 Sevilla, '
    'email <a href="mailto:soporte@wavemusicbusiness.com">soporte@wavemusicbusiness.com</a> y web '
    '<a href="https://www.wavemusicbusiness.com" target="_blank" rel="noopener noreferrer">www.wavemusicbusiness.com</a>.'
)

LEGAL_PAGES = {
    "aviso-legal": {
        "title": "Aviso legal",
        "intro": "Información de identificación y condiciones de uso del sitio Wave Reputation Manager.",
        "sections": [
            ("Titularidad", f"Este sitio y el servicio digital Wave Reputation Manager son gestionados por {LEGAL_CONTACT_HTML}"),
            ("Objeto", "La web ofrece una herramienta de apoyo para analizar textos de reseñas y preparar borradores de reclamación orientativos basados en posibles infracciones de políticas de plataformas."),
            ("Responsabilidad", "Los contenidos generados son orientativos y deben ser revisados por el usuario antes de su uso. La titular no garantiza resultados concretos ni la eliminación de reseñas."),
        ],
    },
    "privacidad": {
        "title": "Política de privacidad",
        "intro": "Información sobre el tratamiento de datos en un servicio digital de análisis de reseñas.",
        "sections": [
            ("Responsable", f"Responsable del tratamiento: {LEGAL_CONTACT_HTML}"),
            ("Datos tratados", "Podemos tratar datos como email, datos necesarios para gestionar la cuenta, plan contratado, datos del negocio, texto de reseñas, contexto aportado, historial de reclamaciones, identificadores de cliente o suscripción de Stripe y datos técnicos necesarios para prestar el servicio."),
            ("Finalidades", "Gestionar el registro e inicio de sesión, prestar el análisis de reseñas, conservar el historial asociado a la cuenta, generar informes PDF, atender soporte y gestionar suscripciones de pago mediante Stripe."),
            ("Conservación y derechos", 'Los datos se conservarán mientras exista la cuenta o sean necesarios para obligaciones legales. El usuario podrá solicitar acceso, rectificación, supresión, oposición, limitación o portabilidad escribiendo a <a href="mailto:soporte@wavemusicbusiness.com">soporte@wavemusicbusiness.com</a>.'),
        ],
    },
    "cookies": {
        "title": "Política de cookies",
        "intro": "Información sobre cookies técnicas y cookies necesarias para operar la aplicación.",
        "sections": [
            ("Titular", f"Esta política corresponde a {LEGAL_CONTACT_HTML}"),
            ("Cookies técnicas", "La aplicación puede usar cookies técnicas imprescindibles para mantener la sesión de usuario y proteger el acceso a funcionalidades privadas."),
            ("Cookies de pago", "Stripe puede utilizar tecnologías necesarias para procesar pagos y prevenir fraude cuando el usuario inicia una suscripción desde los botones de checkout."),
            ("Gestión", "Puedes configurar o bloquear cookies desde tu navegador, aunque las cookies técnicas pueden ser necesarias para iniciar sesión y usar el servicio."),
        ],
    },
    "terminos": {
        "title": "Términos y condiciones",
        "intro": "Condiciones básicas de uso de Wave Reputation Manager.",
        "sections": [
            ("Titular", f"El servicio es prestado por {LEGAL_CONTACT_HTML}"),
            ("Naturaleza del servicio", "La herramienta ayuda a preparar reclamaciones basadas en posibles infracciones de políticas, pero no garantiza la eliminación de reseñas ni sustituye asesoramiento legal especializado."),
            ("Revisión por el usuario", "El usuario es responsable de revisar, completar y validar el texto antes de enviarlo a Google o a cualquier plataforma."),
            ("Uso permitido", "No se debe usar el servicio para reclamaciones falsas, abusivas, engañosas, automatizadas de forma indebida o destinadas a silenciar críticas legítimas."),
            ("Planes", "Los planes disponibles son Free (1 análisis gratuito), Basic (10 análisis al mes por 9,99 €/mes) y Pro (análisis ilimitados por 24,99 €/mes). Las suscripciones de pago se procesan mediante Stripe."),
        ],
    },
    "reembolsos": {
        "title": "Política de reembolsos",
        "intro": "Condiciones orientativas de facturación, cancelación e incidencias de suscripciones digitales.",
        "sections": [
            ("Titular y soporte", f"Para incidencias de facturación o suscripción, contacta con {LEGAL_CONTACT_HTML}"),
            ("Suscripciones", "Basic y Pro son suscripciones mensuales gestionadas mediante Stripe. La contratación muestra el precio antes de confirmar el pago."),
            ("Cancelaciones y reembolsos", "El usuario puede solicitar revisión de incidencias de cobro escribiendo al email de soporte. Los reembolsos se evaluarán caso por caso según el estado del servicio prestado, la normativa aplicable y los registros de uso."),
        ],
    },
}


def load_policies() -> dict[str, Any]:
    with POLICIES_PATH.open(encoding="utf-8") as file:
        data = json.load(file)
    return {category["id"]: category for category in data["categories"]}


POLICIES = load_policies()


def init_db() -> None:
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                email TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                plan TEXT NOT NULL DEFAULT 'free',
                stripe_customer_id TEXT,
                stripe_subscription_id TEXT,
                subscription_status TEXT NOT NULL DEFAULT 'free',
                current_period_end TEXT,
                updated_at TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                created_at TEXT NOT NULL,
                business_name TEXT NOT NULL,
                review_text TEXT NOT NULL,
                stars INTEGER NOT NULL,
                reviewer_name TEXT NOT NULL,
                review_date TEXT NOT NULL,
                additional_context TEXT NOT NULL,
                viability TEXT NOT NULL,
                result_json TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS welcome_email_notifications (
                stripe_subscription_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                plan TEXT NOT NULL,
                status TEXT NOT NULL,
                reserved_at TEXT NOT NULL,
                sent_at TEXT,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
            """
        )
        claim_columns = {row[1] for row in connection.execute("PRAGMA table_info(claims)").fetchall()}
        if "user_id" not in claim_columns:
            connection.execute("ALTER TABLE claims ADD COLUMN user_id INTEGER REFERENCES users(id)")
        user_columns = {row[1] for row in connection.execute("PRAGMA table_info(users)").fetchall()}
        user_migrations = {
            "stripe_customer_id": "TEXT",
            "stripe_subscription_id": "TEXT",
            "subscription_status": "TEXT NOT NULL DEFAULT 'free'",
            "current_period_end": "TEXT",
            "updated_at": "TEXT",
        }
        for column, definition in user_migrations.items():
            if column not in user_columns:
                connection.execute(f"ALTER TABLE users ADD COLUMN {column} {definition}")
        connection.commit()


@app.on_event("startup")
def on_startup() -> None:
    init_db()


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), PASSWORD_ITERATIONS)
    return f"pbkdf2_sha256${PASSWORD_ITERATIONS}${salt}${digest.hex()}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, iterations, salt, expected = password_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != "pbkdf2_sha256":
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations))
    return hmac.compare_digest(digest.hex(), expected)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_user(email: str, password: str) -> int:
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as connection:
        cursor = connection.execute(
            """
            INSERT INTO users (email, password_hash, plan, created_at)
            VALUES (?, ?, 'free', ?)
            """,
            (normalize_email(email), hash_password(password), datetime.now(timezone.utc).isoformat(timespec="seconds")),
        )
        connection.commit()
        return int(cursor.lastrowid)


def fetch_user_by_email(email: str) -> dict[str, Any] | None:
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM users WHERE email = ?", (normalize_email(email),)).fetchone()
    return dict(row) if row else None


def fetch_user(user_id: int | None) -> dict[str, Any] | None:
    if not user_id:
        return None
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        return None
    return enrich_user(dict(row))


def enrich_user(user: dict[str, Any]) -> dict[str, Any]:
    plan = user.get("plan") or "free"
    user["plan"] = plan
    user["plan_label"] = PLAN_NAMES.get(plan, plan.title())
    user["analyses_used_month"] = count_monthly_analyses(int(user["id"]))
    user["analysis_limit"] = PLAN_LIMITS.get(plan, 1)
    user["analysis_limit_label"] = "Ilimitados" if user["analysis_limit"] is None else str(user["analysis_limit"])
    return user


def sign_session(user_id: int) -> str:
    signature = hmac.new(SESSION_SECRET.encode("utf-8"), str(user_id).encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{user_id}:{signature}"


def read_session(session: str | None) -> int | None:
    if not session or ":" not in session:
        return None
    user_id_text, signature = session.split(":", 1)
    if not user_id_text.isdigit():
        return None
    expected = sign_session(int(user_id_text)).split(":", 1)[1]
    if not hmac.compare_digest(signature, expected):
        return None
    return int(user_id_text)


def current_user(session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any] | None:
    return fetch_user(read_session(session))


def require_user(session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> dict[str, Any]:
    user = current_user(session)
    if not user:
        raise HTTPException(status_code=401, detail="Inicia sesión o regístrate para analizar reseñas.")
    return user


def template_context(request: Request, **extra: Any) -> dict[str, Any]:
    return {"request": request, "user": current_user(request.cookies.get(SESSION_COOKIE)), **extra}


def login_response(user_id: int) -> RedirectResponse:
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(SESSION_COOKIE, sign_session(user_id), httponly=True, samesite="lax", max_age=60 * 60 * 24 * 30)
    return response


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.lower()).strip()


def score_to_viability(score: int, detected_count: int, stars: int) -> str:
    adjusted = score + (1 if stars <= 2 else 0) + (1 if detected_count >= 2 else 0)
    if adjusted >= 6:
        return "alta"
    if adjusted >= 3:
        return "media"
    return "baja"


def build_claim_text(payload: dict[str, Any], detected: list[dict[str, Any]], viability: str) -> str:
    policies = ", ".join(item["policy"]["name"] for item in detected) or "posible contenido no ajustado a las políticas"
    motives = "\n".join(f"- {item['policy']['name']}: {item['reason']}" for item in detected)
    if not motives:
        motives = "- No se han identificado señales fuertes; se recomienda aportar contexto y evidencias objetivas antes de solicitar revisión."

    evidence = "\n".join(f"- {item['evidence']}" for item in detected)
    if not evidence:
        evidence = "- Documentación verificable sobre la visita, reserva, atención prestada o comunicaciones con el usuario."

    return (
        f"Estimado equipo de Google Business Profile / Google Maps:\n\n"
        f"Solicito la revisión de una reseña publicada sobre {payload['business_name']} por el usuario visible "
        f"\"{payload['reviewer_name']}\", con fecha {payload['review_date']} y valoración de {payload['stars']} estrella(s).\n\n"
        f"Tras analizar el contenido, consideramos que la reseña podría infringir políticas relacionadas con {policies}. "
        f"La viabilidad estimada de la reclamación es {viability}; esta estimación no implica ni garantiza la retirada.\n\n"
        f"Motivos detectados:\n{motives}\n\n"
        f"Contexto adicional aportado por el negocio:\n{payload['additional_context'] or 'No se aportó contexto adicional.'}\n\n"
        f"Evidencias recomendadas para adjuntar:\n{evidence}\n\n"
        f"Texto de la reseña objeto de revisión:\n\"{payload['review_text']}\"\n\n"
        f"Solicitamos respetuosamente que se evalúe si esta contribución cumple las políticas aplicables de contenido generado por usuarios de Google Maps. "
        f"En caso de confirmarse la infracción, rogamos que se adopten las medidas de moderación correspondientes.\n\n"
        f"Atentamente,\n{payload['business_name']}"
    )


def analyze_review(payload: dict[str, Any]) -> dict[str, Any]:
    combined_text = normalize(" ".join([payload["review_text"], payload.get("additional_context", ""), payload.get("reviewer_name", "")]))
    detected: list[dict[str, Any]] = []
    score = 0

    for rule in RULES:
        matches = [keyword for keyword in rule.keywords if keyword in combined_text]
        if matches:
            policy = POLICIES[rule.policy_id]
            score += rule.weight + min(len(matches) - 1, 2)
            detected.append(
                {
                    "policy": policy,
                    "matches": matches[:5],
                    "reason": f"Se han detectado indicios asociados a: {', '.join(matches[:5])}.",
                    "evidence": rule.evidence_prompt,
                }
            )

    if payload["stars"] <= 2 and len(payload["review_text"].strip()) < 25:
        policy = POLICIES["experiencia_no_genuina"]
        score += 1
        detected.append(
            {
                "policy": policy,
                "matches": ["valoración muy baja con poco texto"],
                "reason": "La reseña tiene una valoración baja y aporta pocos detalles verificables sobre la experiencia.",
                "evidence": "Historial interno de atención y cualquier dato que permita demostrar la ausencia o presencia de experiencia real.",
            }
        )

    unique: dict[str, dict[str, Any]] = {}
    for item in detected:
        unique[item["policy"]["id"]] = item
    detected = list(unique.values())
    viability = score_to_viability(score, len(detected), payload["stars"])

    applicable_policies = [
        {
            "name": item["policy"]["name"],
            "description": item["policy"]["description"],
            "arguments": item["policy"]["arguments"],
        }
        for item in detected
    ]

    result = {
        "viability": viability,
        "detected_motives": [
            {"category": item["policy"]["name"], "reason": item["reason"], "matches": item["matches"]} for item in detected
        ],
        "applicable_policies": applicable_policies,
        "recommended_evidence": [item["evidence"] for item in detected]
        or ["Aporta pruebas objetivas: reserva, ticket, factura, comunicaciones, historial de atención o capturas relevantes."],
        "claim_text": build_claim_text(payload, detected, viability),
        "legal_notice": "Esta herramienta no garantiza la retirada de reseñas; solo ayuda a preparar reclamaciones basadas en políticas.",
    }
    return result


def save_claim(payload: dict[str, Any], result: dict[str, Any], user_id: int) -> int:
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as connection:
        cursor = connection.execute(
            """
            INSERT INTO claims (
                user_id, created_at, business_name, review_text, stars, reviewer_name, review_date,
                additional_context, viability, result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                datetime.now(timezone.utc).isoformat(timespec="seconds"),
                payload["business_name"],
                payload["review_text"],
                payload["stars"],
                payload["reviewer_name"],
                payload["review_date"],
                payload["additional_context"],
                result["viability"],
                json.dumps(result, ensure_ascii=False),
            ),
        )
        connection.commit()
        return int(cursor.lastrowid)


def fetch_history(user_id: int, limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, created_at, business_name, stars, reviewer_name, review_date, viability
            FROM claims
            WHERE user_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, limit),
        ).fetchall()
    return [dict(row) for row in rows]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def current_month_range() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if start.month == 12:
        end = start.replace(year=start.year + 1, month=1)
    else:
        end = start.replace(month=start.month + 1)
    return start.isoformat(timespec="seconds"), end.isoformat(timespec="seconds")


def count_monthly_analyses(user_id: int) -> int:
    init_db()
    start, end = current_month_range()
    with closing(sqlite3.connect(DB_PATH)) as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM claims WHERE user_id = ? AND created_at >= ? AND created_at < ?",
            (user_id, start, end),
        ).fetchone()[0]
    return int(count)


def can_analyze(user: dict[str, Any]) -> tuple[bool, str | None]:
    plan = user.get("plan") or "free"
    limit = PLAN_LIMITS.get(plan, 1)
    if limit is None:
        return True, None
    used = count_monthly_analyses(int(user["id"]))
    if used < limit:
        return True, None
    if plan == "basic":
        return False, "Has alcanzado el límite mensual de tu plan Basic. Actualiza a Pro para análisis ilimitados."
    return False, "Has alcanzado el límite de tu plan Free. Actualiza a Basic o Pro para continuar."


def plan_from_price_id(price_id: str | None) -> str:
    if price_id and price_id in STRIPE_PRICE_TO_PLAN:
        return STRIPE_PRICE_TO_PLAN[price_id]
    return "free"


def subscription_price_id(subscription: Any) -> str | None:
    items = subscription.get("items", {}).get("data", []) if hasattr(subscription, "get") else []
    if not items:
        return None
    price = items[0].get("price", {})
    return price.get("id")


def period_end_to_iso(subscription: Any) -> str | None:
    period_end = subscription.get("current_period_end") if hasattr(subscription, "get") else None
    if not period_end:
        return None
    return datetime.fromtimestamp(int(period_end), tz=timezone.utc).isoformat(timespec="seconds")


def update_user_subscription(
    user_id: int,
    *,
    plan: str | None = None,
    subscription_status: str | None = None,
    stripe_customer_id: str | None = None,
    stripe_subscription_id: str | None = None,
    current_period_end: str | None = None,
) -> None:
    fields: dict[str, Any] = {"updated_at": utc_now()}
    if plan is not None:
        fields["plan"] = plan
    if subscription_status is not None:
        fields["subscription_status"] = subscription_status
    if stripe_customer_id is not None:
        fields["stripe_customer_id"] = stripe_customer_id
    if stripe_subscription_id is not None:
        fields["stripe_subscription_id"] = stripe_subscription_id
    if current_period_end is not None:
        fields["current_period_end"] = current_period_end
    assignments = ", ".join(f"{column} = ?" for column in fields)
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.execute(f"UPDATE users SET {assignments} WHERE id = ?", [*fields.values(), user_id])
        connection.commit()


def smtp_is_configured() -> bool:
    required_values = (
        os.environ.get("SMTP_HOST"),
        os.environ.get("SMTP_PORT"),
        os.environ.get("SMTP_USER"),
        os.environ.get("SMTP_PASSWORD"),
        SMTP_FROM_EMAIL,
    )
    return all(bool(value) for value in required_values)


def reserve_welcome_email_notification(subscription_id: str, user_id: int, plan: str) -> bool:
    init_db()
    now = utc_now()
    with closing(sqlite3.connect(DB_PATH)) as connection:
        cursor = connection.execute(
            """
            INSERT OR IGNORE INTO welcome_email_notifications (
                stripe_subscription_id, user_id, plan, status, reserved_at, updated_at
            ) VALUES (?, ?, ?, 'sending', ?, ?)
            """,
            (subscription_id, user_id, plan, now, now),
        )
        connection.commit()
        return cursor.rowcount == 1


def mark_welcome_email_notification(subscription_id: str, status: str, sent_at: str | None = None) -> None:
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.execute(
            """
            UPDATE welcome_email_notifications
            SET status = ?, sent_at = ?, updated_at = ?
            WHERE stripe_subscription_id = ?
            """,
            (status, sent_at, utc_now(), subscription_id),
        )
        connection.commit()


def send_welcome_email(recipient_email: str, plan: str) -> None:
    message = EmailMessage()
    message["Subject"] = WELCOME_EMAIL_SUBJECTS[plan]
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL}>"
    message["To"] = recipient_email
    message.set_content(WELCOME_EMAIL_BODIES[plan])

    smtp_host = os.environ["SMTP_HOST"]
    smtp_port = int(os.environ["SMTP_PORT"])
    smtp_user = os.environ["SMTP_USER"]
    smtp_password = os.environ["SMTP_PASSWORD"]

    use_ssl = smtp_port == 465
    smtp_class = smtplib.SMTP_SSL if use_ssl else smtplib.SMTP
    with smtp_class(smtp_host, smtp_port, timeout=20) as smtp:
        if not use_ssl:
            smtp.starttls()
        smtp.login(smtp_user, smtp_password)
        smtp.send_message(message)


def send_subscription_welcome_email_once(user: dict[str, Any], plan: str, subscription_id: str | None, subscription_status: str | None) -> None:
    if plan not in WELCOME_EMAIL_RECIPIENT_PLANS or subscription_status != "active" or not subscription_id:
        return
    if not smtp_is_configured():
        logger.warning("Email de bienvenida no enviado porque SMTP no está configurado")
        return
    if not reserve_welcome_email_notification(subscription_id, int(user["id"]), plan):
        logger.info("Email de bienvenida omitido para suscripción ya notificada")
        return
    try:
        send_welcome_email(user["email"], plan)
    except Exception as exc:
        mark_welcome_email_notification(subscription_id, "error")
        logger.warning("Error enviando email de bienvenida para user_id=%s subscription_id=%s: %s", user["id"], subscription_id, exc.__class__.__name__)
        return
    sent_at = utc_now()
    mark_welcome_email_notification(subscription_id, "sent", sent_at)
    logger.info("Email de bienvenida enviado correctamente para user_id=%s subscription_id=%s", user["id"], subscription_id)


def fetch_user_by_subscription(subscription_id: str | None) -> dict[str, Any] | None:
    if not subscription_id:
        return None
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM users WHERE stripe_subscription_id = ?", (subscription_id,)).fetchone()
    return dict(row) if row else None


def stripe_checkout_price_id(selected_plan: str) -> str:
    env_name = "STRIPE_PRICE_ID_BASIC" if selected_plan == "basic" else "STRIPE_PRICE_ID_PRO"
    price_id = os.environ.get(env_name)
    if not stripe.api_key or not price_id:
        raise HTTPException(status_code=503, detail="La configuración de Stripe no está completa.")
    return price_id


def pdf_text(value: Any) -> str:
    return html.escape(str(value)).replace("\n", "<br/>")


def fetch_claim(claim_id: int, user_id: int) -> dict[str, Any] | None:
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM claims WHERE id = ? AND user_id = ?", (claim_id, user_id)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["result"] = json.loads(data["result_json"])
    return data


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    user = current_user(request.cookies.get(SESSION_COOKIE))
    history = fetch_history(user["id"]) if user else []
    return templates.TemplateResponse("index.html", template_context(request, user=user, history=history))


@app.get("/register", response_class=HTMLResponse)
def register_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("auth.html", template_context(request, mode="register", title="Crear cuenta", error=None))


@app.post("/register")
def register(request: Request, email: str = Form(...), password: str = Form(...)) -> Response:
    cleaned_email = normalize_email(email)
    if not cleaned_email or "@" not in cleaned_email or len(password) < 8:
        return templates.TemplateResponse(
            "auth.html",
            {"request": request, "user": None, "mode": "register", "title": "Crear cuenta", "error": "Introduce un email válido y una contraseña de al menos 8 caracteres."},
            status_code=400,
        )
    try:
        user_id = create_user(cleaned_email, password)
    except sqlite3.IntegrityError:
        return templates.TemplateResponse(
            "auth.html",
            {"request": request, "user": None, "mode": "register", "title": "Crear cuenta", "error": "Ya existe una cuenta con ese email."},
            status_code=400,
        )
    return login_response(user_id)


@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("auth.html", template_context(request, mode="login", title="Iniciar sesión", error=None))


@app.post("/login")
def login(request: Request, email: str = Form(...), password: str = Form(...)) -> Response:
    user = fetch_user_by_email(email)
    if not user or not verify_password(password, user["password_hash"]):
        return templates.TemplateResponse(
            "auth.html",
            {"request": request, "user": None, "mode": "login", "title": "Iniciar sesión", "error": "Email o contraseña incorrectos."},
            status_code=400,
        )
    return login_response(int(user["id"]))


@app.get("/logout")
def logout() -> RedirectResponse:
    response = RedirectResponse(url="/", status_code=303)
    response.delete_cookie(SESSION_COOKIE)
    return response


@app.get("/pricing", response_class=HTMLResponse)
def pricing_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("pricing.html", template_context(request))


@app.post("/billing/create-checkout-session/{selected_plan}")
def create_checkout_session(selected_plan: str, request: Request, session: str | None = Cookie(default=None, alias=SESSION_COOKIE)) -> RedirectResponse:
    user = current_user(session)
    if not user:
        return RedirectResponse(url="/login", status_code=303)
    if selected_plan not in {"basic", "pro"}:
        raise HTTPException(status_code=404, detail="Plan no encontrado.")
    price_id = stripe_checkout_price_id(selected_plan)
    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=user.get("stripe_customer_id") or None,
            customer_email=None if user.get("stripe_customer_id") else user["email"],
            line_items=[{"price": price_id, "quantity": 1}],
            allow_promotion_codes=True,
            success_url=f'{APP_BASE_URL}/billing/success?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url=f"{APP_BASE_URL}/pricing",
            metadata={"user_id": str(user["id"]), "email": user["email"], "selected_plan": selected_plan},
            subscription_data={"metadata": {"user_id": str(user["id"]), "email": user["email"], "selected_plan": selected_plan}},
        )
    except stripe.error.StripeError as exc:
        logger.warning("Stripe checkout error for user_id=%s plan=%s: %s", user["id"], selected_plan, exc.user_message or exc.__class__.__name__)
        raise HTTPException(status_code=502, detail="No se pudo iniciar Stripe Checkout. Inténtalo de nuevo.") from exc
    return RedirectResponse(url=session.url, status_code=303)


@app.get("/billing/success", response_class=HTMLResponse)
def billing_success(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "billing_status.html",
        template_context(
            request,
            title="Suscripción activada",
            message="Suscripción activada correctamente. Tu plan se actualizará en unos segundos.",
            button_href="/",
            button_text="Volver al dashboard",
        ),
    )


@app.get("/billing/cancel", response_class=HTMLResponse)
def billing_cancel(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        "billing_status.html",
        template_context(
            request,
            title="Pago cancelado",
            message="El proceso de pago se ha cancelado. Puedes intentarlo de nuevo cuando quieras.",
            button_href="/pricing",
            button_text="Volver a precios",
        ),
    )


@app.get("/billing/portal", response_class=HTMLResponse)
def billing_portal(request: Request, user: dict[str, Any] = Depends(require_user)) -> HTMLResponse:
    return templates.TemplateResponse(
        "billing_status.html",
        template_context(
            request,
            title="Portal de cliente",
            message="Portal de cliente próximamente disponible",
            button_href="/",
            button_text="Volver al dashboard",
        ),
    )


@app.post("/stripe/webhook")
async def stripe_webhook(request: Request) -> JSONResponse:
    webhook_secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        raise HTTPException(status_code=503, detail="Webhook de Stripe no configurado.")
    payload = await request.body()
    signature = request.headers.get("stripe-signature")
    try:
        event = stripe.Webhook.construct_event(payload, signature, webhook_secret)
    except (ValueError, stripe.error.SignatureVerificationError) as exc:
        logger.warning("Stripe webhook rejected: %s", exc.__class__.__name__)
        raise HTTPException(status_code=400, detail="Firma de webhook inválida.") from exc

    event_type = event["type"]
    obj = event["data"]["object"]
    logger.info("Stripe webhook received: %s", event_type)

    if event_type == "checkout.session.completed":
        metadata = obj.get("metadata", {})
        user = fetch_user(int(metadata["user_id"])) if metadata.get("user_id", "").isdigit() else fetch_user_by_email(metadata.get("email", ""))
        if user:
            subscription_id = obj.get("subscription")
            customer_id = obj.get("customer")
            selected_plan = metadata.get("selected_plan") if metadata.get("selected_plan") in {"basic", "pro"} else None
            plan = selected_plan or user.get("plan") or "free"
            current_period_end = None
            if subscription_id:
                try:
                    subscription = stripe.Subscription.retrieve(subscription_id)
                    plan = plan_from_price_id(subscription_price_id(subscription))
                    current_period_end = period_end_to_iso(subscription)
                except stripe.error.StripeError as exc:
                    logger.warning("Could not retrieve Stripe subscription %s: %s", subscription_id, exc.__class__.__name__)
            status = "active" if obj.get("payment_status") in {"paid", "no_payment_required"} else obj.get("status", "active")
            update_user_subscription(
                int(user["id"]),
                plan=plan,
                subscription_status=status,
                stripe_customer_id=customer_id,
                stripe_subscription_id=subscription_id,
                current_period_end=current_period_end,
            )
            send_subscription_welcome_email_once(user, plan, subscription_id, status)
            logger.info("Stripe checkout completed for user_id=%s plan=%s", user["id"], plan)
        else:
            logger.warning("Stripe checkout completed without matching local user")
    elif event_type in {"customer.subscription.created", "customer.subscription.updated"}:
        subscription_id = obj.get("id")
        user = fetch_user_by_subscription(subscription_id)
        metadata = obj.get("metadata", {})
        if not user and metadata.get("user_id", "").isdigit():
            user = fetch_user(int(metadata["user_id"]))
        if not user and metadata.get("email"):
            user = fetch_user_by_email(metadata["email"])
        if user:
            price_id = subscription_price_id(obj)
            plan = plan_from_price_id(price_id)
            status = obj.get("status")
            update_user_subscription(
                int(user["id"]),
                plan=plan,
                subscription_status=status,
                stripe_customer_id=obj.get("customer"),
                stripe_subscription_id=subscription_id,
                current_period_end=period_end_to_iso(obj),
            )
            send_subscription_welcome_email_once(user, plan, subscription_id, status)
            logger.info("Stripe subscription synced for user_id=%s status=%s", user["id"], obj.get("status"))
    elif event_type == "customer.subscription.deleted":
        user = fetch_user_by_subscription(obj.get("id"))
        if user:
            update_user_subscription(
                int(user["id"]),
                plan="free",
                subscription_status="canceled",
                current_period_end=period_end_to_iso(obj),
            )
            logger.info("Stripe subscription canceled for user_id=%s", user["id"])
    elif event_type == "invoice.payment_failed":
        subscription_id = obj.get("subscription")
        user = fetch_user_by_subscription(subscription_id)
        if user:
            update_user_subscription(int(user["id"]), subscription_status="past_due")
            logger.info("Stripe invoice payment failed for user_id=%s", user["id"])

    return JSONResponse({"received": True})


@app.get("/legal/{slug}", response_class=HTMLResponse)
def legal_page(slug: str, request: Request) -> HTMLResponse:
    page = LEGAL_PAGES.get(slug)
    if not page:
        raise HTTPException(status_code=404, detail="Página legal no encontrada.")
    return templates.TemplateResponse("legal.html", template_context(request, page=page))


@app.post("/analyze")
def analyze(
    user: dict[str, Any] = Depends(require_user),
    business_name: str = Form(...),
    review_text: str = Form(...),
    stars: int = Form(...),
    reviewer_name: str = Form(...),
    review_date: str = Form(...),
    additional_context: str = Form(""),
) -> JSONResponse:
    if stars < 1 or stars > 5:
        raise HTTPException(status_code=400, detail="El número de estrellas debe estar entre 1 y 5.")
    payload = {
        "business_name": business_name.strip(),
        "review_text": review_text.strip(),
        "stars": stars,
        "reviewer_name": reviewer_name.strip(),
        "review_date": review_date.strip(),
        "additional_context": additional_context.strip(),
    }
    if not payload["business_name"] or not payload["review_text"] or not payload["reviewer_name"] or not payload["review_date"]:
        raise HTTPException(status_code=400, detail="Completa todos los campos obligatorios.")
    allowed, limit_message = can_analyze(user)
    if not allowed:
        raise HTTPException(status_code=403, detail=limit_message)
    result = analyze_review(payload)
    claim_id = save_claim(payload, result, int(user["id"]))
    analyses_used = count_monthly_analyses(int(user["id"]))
    return JSONResponse({"id": claim_id, "analyses_used_month": analyses_used, **result})


@app.get("/history")
def history(user: dict[str, Any] = Depends(require_user)) -> JSONResponse:
    enriched = enrich_user(user)
    return JSONResponse({
        "items": fetch_history(int(user["id"])),
        "usage": {
            "analyses_used_month": enriched["analyses_used_month"],
            "analysis_limit": enriched["analysis_limit"],
            "analysis_limit_label": enriched["analysis_limit_label"],
        },
    })


@app.get("/claims/{claim_id}/pdf")
def export_pdf(claim_id: int, user: dict[str, Any] = Depends(require_user)) -> StreamingResponse:
    claim = fetch_claim(claim_id, int(user["id"]))
    if not claim:
        raise HTTPException(status_code=404, detail="Reclamación no encontrada.")

    buffer = io.BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=2 * cm, leftMargin=2 * cm, topMargin=2 * cm, bottomMargin=2 * cm)
    styles = getSampleStyleSheet()
    story: list[Any] = []
    result = claim["result"]

    story.append(Paragraph("Wave Reputation Manager", styles["Title"]))
    story.append(Paragraph("Informe de análisis y reclamación", styles["Heading2"]))
    story.append(Spacer(1, 0.4 * cm))
    table = Table(
        [
            ["Negocio", pdf_text(claim["business_name"])],
            ["Usuario", pdf_text(claim["reviewer_name"])],
            ["Fecha reseña", pdf_text(claim["review_date"])],
            ["Estrellas", str(claim["stars"])],
            ["Viabilidad", result["viability"].upper()],
        ],
        colWidths=[4 * cm, 11 * cm],
    )
    table.setStyle(TableStyle([("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#141827")), ("TEXTCOLOR", (0, 0), (0, -1), colors.white), ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#d7dcff")), ("VALIGN", (0, 0), (-1, -1), "TOP")]))
    story.append(table)
    story.append(Spacer(1, 0.5 * cm))
    story.append(Paragraph("Motivos detectados", styles["Heading3"]))
    for motive in result["detected_motives"]:
        story.append(Paragraph(pdf_text(f"• {motive['category']}: {motive['reason']}"), styles["BodyText"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Evidencias recomendadas", styles["Heading3"]))
    for evidence in result["recommended_evidence"]:
        story.append(Paragraph(pdf_text(f"• {evidence}"), styles["BodyText"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph("Texto de reclamación", styles["Heading3"]))
    for paragraph in result["claim_text"].split("\n"):
        story.append(Paragraph(pdf_text(paragraph) or " ", styles["BodyText"]))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(pdf_text(result["legal_notice"]), styles["Italic"]))
    document.build(story)
    buffer.seek(0)
    filename = f"wave-reputation-claim-{claim_id}.pdf"
    return StreamingResponse(buffer, media_type="application/pdf", headers={"Content-Disposition": f"attachment; filename={filename}"})
