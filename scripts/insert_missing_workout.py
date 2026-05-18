"""
Insere um treino perdido manualmente.
Uso: python scripts/insert_missing_workout.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, datetime
import pytz
from app.db.client import get_supabase

PARTICIPANT_NAME = "Pri Cordeiro"
SEQUENCE_NUMBER = 105
WORKOUT_DATE = date(2026, 5, 15)
WORKOUT_TIME_LOCAL = "08:16:00"  # horário de Brasília
SHIFT = "manha"

BRT = pytz.timezone("America/Sao_Paulo")


def main():
    supabase = get_supabase()

    participants = (
        supabase.table("participants")
        .select("id,name,phone")
        .eq("is_active", True)
        .execute()
        .data or []
    )

    participant = next(
        (p for p in participants if p["name"].lower() == PARTICIPANT_NAME.lower()),
        None,
    )
    if not participant:
        print(f"Participante '{PARTICIPANT_NAME}' não encontrado.")
        sys.exit(1)

    submitted_at = BRT.localize(
        datetime.strptime(f"{WORKOUT_DATE} {WORKOUT_TIME_LOCAL}", "%Y-%m-%d %H:%M:%S")
    ).isoformat()

    print(f"\nParticipante : {participant['name']} ({participant['phone']})")
    print(f"Treino       : {SEQUENCE_NUMBER}/200")
    print(f"Data         : {WORKOUT_DATE} às {WORKOUT_TIME_LOCAL} (Brasília)")
    print(f"Turno        : {SHIFT}")
    print(f"submitted_at : {submitted_at}")
    print()

    confirm = input("Confirma a inserção? (s/n): ").strip().lower()
    if confirm != "s":
        print("Cancelado.")
        return

    result = (
        supabase.table("workouts")
        .upsert(
            {
                "participant_id": participant["id"],
                "workout_date": WORKOUT_DATE.isoformat(),
                "submitted_at": submitted_at,
                "sequence_number": SEQUENCE_NUMBER,
                "shift": SHIFT,
                "is_valid": True,
            },
            on_conflict="participant_id,workout_date,shift",
        )
        .execute()
    )

    if result.data:
        print(f"\n✓ Treino {SEQUENCE_NUMBER}/200 de {participant['name']} inserido com sucesso!")
    else:
        print("\n✗ Falha na inserção. Verifique os logs.")


if __name__ == "__main__":
    main()
