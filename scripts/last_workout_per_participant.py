"""
Mostra o último treino registrado por participante e quantos dias faz.

Uso: python scripts/last_workout_per_participant.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date
from app.db.client import get_supabase


def main():
    supabase = get_supabase()

    result = (
        supabase.table("workouts")
        .select("participant_id, workout_date, sequence_number, participants!workouts_participant_id_fkey(name)")
        .eq("is_valid", True)
        .is_("deleted_at", "null")
        .order("workout_date", desc=True)
        .execute()
    )

    latest = {}
    for row in (result.data or []):
        pid = row["participant_id"]
        if pid not in latest:
            latest[pid] = {
                "name": row["participants"]["name"],
                "last_date": row["workout_date"],
                "max_seq": row["sequence_number"],
            }

    today = date.today()
    print(f"\n=== Último treino por participante (hoje: {today.strftime('%d/%m/%Y')}) ===\n")
    print(f"  {'Nome':<20} {'Último treino':<15} {'Dias atrás':<12} {'Seq'}")
    print("  " + "-" * 55)

    for pid, info in sorted(latest.items(), key=lambda x: x[1]["last_date"]):
        last = date.fromisoformat(info["last_date"])
        days_ago = (today - last).days
        alert = " ⚠️" if days_ago > 14 else ""
        print(f"  {info['name']:<20} {last.strftime('%d/%m/%Y'):<15} {days_ago:<12} {info['max_seq']}/200{alert}")

    print()


if __name__ == "__main__":
    main()
