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

    workouts_result = (
        supabase.table("workouts")
        .select("participant_id")
        .eq("is_valid", True)
        .is_("deleted_at", "null")
        .limit(10000)
        .execute()
    )
    workouts = workouts_result.data or []

    counts: dict[str, int] = {}
    for w in workouts:
        pid = w["participant_id"]
        counts[pid] = counts.get(pid, 0) + 1

    ranking = []
    for p in participants:
        joined = date.fromisoformat(p["joined_at"])
        goal = _calculate_goal(joined, p.get("medical_leave_days", 0))
        ranking.append({
            "name": p["name"],
            "phone": p["phone"],
            "count": counts.get(p["id"], 0),
            "goal": goal,
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
        ranking_lines.append(f"{i + 1}. {r['name']}: {r['count']}/{r['goal']} treinos ({pct}%)")
    ranking_text = "\n".join(ranking_lines)

    comparison_text = ""
    if last_snapshot:
        prev = {r["name"]: r["count"] for r in last_snapshot}
        deltas = [(r, r["count"] - prev.get(r["name"], 0)) for r in ranking]
        on_fire = max(deltas, key=lambda x: x[1])
        if on_fire[1] > 0:
            comparison_text = f"\nDestaque do período: {on_fire[0]['name']} foi quem mais treinou (+{on_fire[1]} treinos).\n"

    milestones = _detect_new_milestones(ranking, last_snapshot)
    milestones_text = ""
    if milestones:
        milestones_text = "\nConquistas desde o último relatório:\n" + "\n".join(milestones) + "\n"

    return (
        f"Você é o agente do Fitness 2026, um grupo de amigos numa aposta fitness no WhatsApp. "
        f"Gere o relatório do grupo. Hoje é {today.strftime('%d/%m/%Y')}.\n\n"
        f"RANKING ATUAL (use EXATAMENTE esses números, sem alterar nenhum valor):\n{ranking_text}\n"
        f"{comparison_text}"
        f"{milestones_text}\n"
        f"REGRAS (siga à risca):\n"
        f"- Mostre o ranking completo com os números EXATOS acima — nunca invente ou arredonde\n"
        f"- Tom simples, direto e levemente engraçado — sem exagerar nas piadinhas\n"
        f"- Reconheça positivamente quem está evoluindo\n"
        f"- Se houver conquistas listadas acima, inclua seção '🏅 Conquistas' no final\n"
        f"- Máximo 30 linhas, use emojis com moderação\n"
        f"- Não mencione valores em dinheiro\n"
        f"- Escreva em português brasileiro informal\n"
        f"- Termine com uma frase motivacional curta\n\n"
        f"Gere o relatório agora:"
    )


async def generate_report(
    trigger: str,
    triggered_by_id: Optional[str] = None,
) -> tuple[str, Optional[dict]]:
    client = genai.Client(api_key=settings.gemini_api_key)

    ranking = _get_ranking()
    last_report = report_repo.get_last_report()
    last_snapshot = last_report["snapshot"] if last_report else None

    prompt = _build_prompt(ranking, last_snapshot)
    logger.info("Ranking snapshot: %s", [(r["name"], r["count"]) for r in ranking])
    logger.info("Generating report via Gemini (trigger=%s)", trigger)

    response = await client.aio.models.generate_content(
        model=settings.gemini_model,
        contents=prompt,
    )
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
