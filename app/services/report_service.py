import logging
from datetime import date
from typing import Optional

from google import genai

from app.core.config import settings
from app.core.constants import CHALLENGE_START, CHALLENGE_END, CHALLENGE_DAYS, GOAL
from app.db.client import get_supabase
from app.db.repositories import report_repo

logger = logging.getLogger(__name__)


def _calculate_goal(joined_at: date, medical_leave_days: int) -> int:
    participant_days = (CHALLENGE_END - max(joined_at, CHALLENGE_START)).days + 1
    effective_days = max(participant_days - medical_leave_days, 1)
    return max(round(GOAL * effective_days / CHALLENGE_DAYS), 1)


def _get_ranking() -> list[dict]:
    supabase = get_supabase()

    participants_result = (
        supabase.table("participants")
        .select("id, name, phone, joined_at, medical_leave_days")
        .eq("is_active", True)
        .execute()
    )
    participants = participants_result.data or []

    counts_result = supabase.rpc("get_workout_counts").execute()
    counts: dict[str, int] = {}
    last_seqs: dict[str, int] = {}
    for row in (counts_result.data or []):
        pid = row["participant_id"]
        counts[pid] = row["count"]
        if row.get("last_seq") is not None:
            last_seqs[pid] = row["last_seq"]

    ranking = []
    for p in participants:
        joined = date.fromisoformat(p["joined_at"])
        goal = _calculate_goal(joined, p.get("medical_leave_days", 0))
        pid = p["id"]
        count = counts.get(pid, 0)
        last_seq = last_seqs.get(pid)
        needs_check = last_seq is not None and count != last_seq
        ranking.append({
            "name": p["name"],
            "phone": p["phone"],
            "count": count,
            "goal": goal,
            "needs_check": needs_check,
        })

    ranking.sort(key=lambda x: x["count"], reverse=True)
    return ranking


MILESTONES = {25: "25% da meta", 50: "metade da meta!", 75: "75% da meta", 100: "meta batida! 🏆"}


def _detect_new_milestones(ranking: list[dict], last_snapshot: Optional[list]) -> list[str]:
    prev = {r["name"]: r["count"] for r in last_snapshot} if last_snapshot else {}
    achievements = []
    for r in ranking:
        prev_count = prev.get(r["name"], 0)
        for pct, label in MILESTONES.items():
            threshold = max(round(r["goal"] * pct / 100), 1)
            if r["count"] >= threshold and prev_count < threshold:
                achievements.append(f"- {r['name']} chegou aos {label} ({r['count']}/{r['goal']})")
    return achievements


def _build_prompt(ranking: list[dict], last_snapshot: Optional[list]) -> str:
    today = date.today()

    ranking_lines = []
    for i, r in enumerate(ranking):
        pct = round(r["count"] / r["goal"] * 100) if r["goal"] else 0
        flag = " (! Validar contagem)" if r.get("needs_check") else ""
        ranking_lines.append(f"{i + 1}. {r['name']}{flag}: {r['count']}/{r['goal']} ({pct}%)")
    ranking_text = "\n".join(ranking_lines)

    pelotoes_text = ""
    if last_snapshot:
        prev = {r["name"]: r["count"] for r in last_snapshot}
        deltas = [(r, r["count"] - prev.get(r["name"], 0)) for r in ranking]
        deltas_sorted = sorted(deltas, key=lambda x: x[1], reverse=True)

        on_fire = [r["name"] for r, d in deltas_sorted if d >= 2][:5]

        if on_fire:
            pelotoes_text += f"\nPELOTÃO ON FIRE (mais treinos desde o último relatório): {', '.join(on_fire)}\n"

    milestones = _detect_new_milestones(ranking, last_snapshot)
    milestones_text = ""
    if milestones:
        milestones_text = "\nConquistas desde o último relatório:\n" + "\n".join(milestones) + "\n"

    return (
        f"Você é o agente do Fitness 2026, um grupo de amigos numa aposta fitness no WhatsApp. "
        f"Gere o relatório do grupo. Hoje é {today.strftime('%d/%m/%Y')}.\n\n"
        f"PROGRESSO ATUAL (use EXATAMENTE esses números, sem alterar nenhum valor):\n{ranking_text}\n"
        f"{pelotoes_text}"
        f"{milestones_text}\n"
        f"REGRAS (siga à risca):\n"
        f"- Mostre a lista completa com os números EXATOS acima — nunca adicione a palavra 'treinos' após os números\n"
        f"- Se houver 'PELOTÃO ON FIRE' acima, crie uma seção animada celebrando quem mais treinou no período\n"
        f"- Se houver conquistas listadas acima, inclua seção '🏅 Conquistas' no final\n"
        f"- NÃO adicione frases de lembrete sobre jornada individual, comparação ou motivação genérica\n"
        f"- Foque no ranking e nas conquistas — sem seções extras além dessas\n"
        f"- Tom descontraído, engraçado e motivador — humor sutil e carinhoso\n"
        f"- Máximo 35 linhas, use emojis com moderação\n"
        f"- Não mencione valores em dinheiro\n"
        f"- Se mencionar o prêmio ou motivação final, é um churrasco — nunca mencione pizza ou outro alimento\n"
        f"- Escreva em português brasileiro informal\n"
        f"- Termine com uma frase motivacional curta e engraçada\n\n"
        f"Gere o relatório agora:"
    )


class ReportError(Exception):
    def __init__(self, service: str, message: str):
        self.service = service
        super().__init__(message)


async def generate_report(
    trigger: str,
    triggered_by_id: Optional[str] = None,
) -> tuple[str, Optional[dict]]:
    client = genai.Client(api_key=settings.gemini_api_key)

    try:
        ranking = _get_ranking()
        last_report = report_repo.get_last_report()
    except Exception as e:
        raise ReportError("banco de dados", str(e)) from e

    last_snapshot = last_report["snapshot"] if last_report else None

    prompt = _build_prompt(ranking, last_snapshot)
    logger.info("Ranking snapshot: %s", [(r["name"], r["count"]) for r in ranking])
    logger.info("Generating report via Gemini (trigger=%s)", trigger)

    try:
        response = await client.aio.models.generate_content(
            model=settings.gemini_model,
            contents=prompt,
        )
    except Exception as e:
        raise ReportError("Gemini (IA)", str(e)) from e
    report_text = response.text

    last_period_end = last_report["period_end"] if last_report else None
    if isinstance(last_period_end, str):
        period_start = date.fromisoformat(last_period_end)
    else:
        period_start = CHALLENGE_START

    period_end = date.today()

    saved = report_repo.insert(
        trigger=trigger,
        triggered_by_id=triggered_by_id,
        period_start=period_start,
        period_end=period_end,
        snapshot=ranking,
        report_text=report_text,
    )

    logger.info("Report saved (id=%s)", saved["id"] if saved else "None")
    return report_text, saved
