"""
Identifica gaps nas sequências de treino de cada participante.
Compara o intervalo 1..max_seq com os números registrados no banco.

Uso: python scripts/find_sequence_gaps.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.client import get_supabase


def main():
    supabase = get_supabase()

    sequences_result = supabase.rpc("get_registered_sequences").execute()
    sequences_by_participant = {
        row["participant_id"]: set(row["sequences"] or [])
        for row in (sequences_result.data or [])
    }

    participants_result = (
        supabase.table("participants")
        .select("id, name")
        .eq("is_active", True)
        .execute()
    )
    participants = {p["id"]: p["name"] for p in (participants_result.data or [])}

    print("\n=== Gaps de Sequência por Participante ===\n")

    total_gaps = 0
    any_gap = False

    for pid, name in sorted(participants.items(), key=lambda x: x[1]):
        seqs = sequences_by_participant.get(pid, set())
        if not seqs:
            print(f"  {name}: nenhum treino registrado")
            continue

        max_seq = max(seqs)
        expected = set(range(1, max_seq + 1))
        gaps = sorted(expected - seqs)

        if gaps:
            any_gap = True
            total_gaps += len(gaps)
            gap_str = ", ".join(str(g) for g in gaps)
            print(f"  {name} (até {max_seq}/200): faltam {len(gaps)} → [{gap_str}]")
        else:
            print(f"  {name} (até {max_seq}/200): sequência OK")

    print(f"\nTotal de treinos faltando: {total_gaps}")
    if any_gap:
        print("\nUse #add-treino no WhatsApp para inserir os faltantes.")
        print("Formato: #add-treino 45/200 para Nome em DD/MM HH:MM")
    print()


if __name__ == "__main__":
    main()
