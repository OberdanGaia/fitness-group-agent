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
        stagnated = [r["name"] for r, d in deltas if d == 0 and r["count"] > 0]
        comparison_text = (
            f"\nDesde o último relatório:\n"
            f"- 🔥 On Fire: {on_fire[0]['name']} (+{on_fire[1]} treinos)\n"
            f"- 😴 Sem treinos no período: {', '.join(stagnated) if stagnated else 'ninguém (incrível!)'}\n"
        )

    return (
        f"Você é o agente do Fitness 2026, um grupo de amigos numa aposta fitness no WhatsApp. "
        f"Gere o relatório mensal do grupo. Hoje é {today.strftime('%d/%m/%Y')}. "
        f"A meta é completar os treinos marcados até 20/12/2026.\n\n"
        f"Ranking atual:\n{ranking_text}\n"
        f"{comparison_text}\n"
        f"Regras de formato:\n"
        f"- Tom leve, engraçado e motivacional — o objetivo é animar, não envergonhar\n"
        f"- Use emojis com moderação\n"
        f"- Máximo 35 linhas\n"
        f"- Não mencione valores em dinheiro\n"
        f"- Escreva em português brasileiro informal\n"
        f"- Termine com uma frase motivacional curta para o mês\n\n"
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
