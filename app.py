from __future__ import annotations

import html
import io
import json
import re
import sqlite3
from contextlib import closing
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

BASE_DIR = Path(__file__).parent
POLICIES_PATH = BASE_DIR / "google_policies.json"
DB_PATH = BASE_DIR / "claims.db"

app = FastAPI(title="Wave Reputation Manager", version="1.0.0")
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


def load_policies() -> dict[str, Any]:
    with POLICIES_PATH.open(encoding="utf-8") as file:
        data = json.load(file)
    return {category["id"]: category for category in data["categories"]}


POLICIES = load_policies()


def init_db() -> None:
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS claims (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                business_name TEXT NOT NULL,
                review_text TEXT NOT NULL,
                stars INTEGER NOT NULL,
                reviewer_name TEXT NOT NULL,
                review_date TEXT NOT NULL,
                additional_context TEXT NOT NULL,
                viability TEXT NOT NULL,
                result_json TEXT NOT NULL
            )
            """
        )
        connection.commit()


@app.on_event("startup")
def on_startup() -> None:
    init_db()


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


def save_claim(payload: dict[str, Any], result: dict[str, Any]) -> int:
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as connection:
        cursor = connection.execute(
            """
            INSERT INTO claims (
                created_at, business_name, review_text, stars, reviewer_name, review_date,
                additional_context, viability, result_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
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


def fetch_history(limit: int = 20) -> list[dict[str, Any]]:
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """
            SELECT id, created_at, business_name, stars, reviewer_name, review_date, viability
            FROM claims
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(row) for row in rows]


def pdf_text(value: Any) -> str:
    return html.escape(str(value)).replace("\n", "<br/>")


def fetch_claim(claim_id: int) -> dict[str, Any] | None:
    init_db()
    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.row_factory = sqlite3.Row
        row = connection.execute("SELECT * FROM claims WHERE id = ?", (claim_id,)).fetchone()
    if not row:
        return None
    data = dict(row)
    data["result"] = json.loads(data["result_json"])
    return data


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request, "history": fetch_history()})


@app.post("/analyze")
def analyze(
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
    result = analyze_review(payload)
    claim_id = save_claim(payload, result)
    return JSONResponse({"id": claim_id, **result})


@app.get("/history")
def history() -> JSONResponse:
    return JSONResponse({"items": fetch_history()})


@app.get("/claims/{claim_id}/pdf")
def export_pdf(claim_id: int) -> StreamingResponse:
    claim = fetch_claim(claim_id)
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
