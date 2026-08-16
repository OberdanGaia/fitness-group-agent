"""
Corrige as contagens de treino por participante inserindo os treinos faltantes.
Cada participante tem um target (contagem correta). O script calcula o que falta,
distribui em datas consecutivas evitando conflitos e insere no banco.

Uso:
  python scripts/fix_workout_counts.py --dry-run   # mostra o que seria inserido
  python scripts/fix_workout_counts.py              # insere de verdade
"""

import argparse
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import date, timedelta, datetime
import pytz
from app.db.client import get_supabase

BR_TZ = pytz.timezone("America/Sao_Paulo")

# ---------------------------------------------------------------------------
# Contagens corretas por participante
# Formato simples:   "Nome": count
# Com data final:    "Nome": {"count": N, "final_date": date(YYYY, M, D)}
#   → o último treino será inserido exatamente na final_date; os anteriores
#     são distribuídos para trás a partir dessa data.
# ---------------------------------------------------------------------------
TARGETS: dict = {
    "Thiago":      109,
    "Carol":       147,
    "Piazzi":      188,
    "Ste":         125,
    "Oberdan":     137,
    "Valentina":   57,
    "Alan":        105,
    "Pedro":       159,
    "Fran":        64,
    "Gui Tadiello": 102,
    "Pri Cordeiro": 164,
    "David":       105,
    "Du":          113,
    "Jheni":       116,
    "Gui Pacheco": 115,
    "Heloisa":     {"count": 200, "final_date": date(2026, 8, 9)},
    "Marcela":     {"count": 200, "final_date": date(2026, 8, 10)},
    # Adicionar os outros participantes aqui conforme forem sendo informados:
    # "Iago": 22,
    # "Gabie": 38,
}

SHIFT = "manha"
HOUR = 8  # 08:00 BRT


def get_participant(supabase, name: str) -> dict:
    result = supabase.table("participants").select("id,name").eq("is_active", True).eq("name", name).execute()
    if not result.data:
        raise ValueError(f"Participante '{name}' não encontrado no banco.")
    return result.data[0]


def get_occupied_slots(supabase, participant_id: str):
    result = (
        supabase.table("workouts")
        .select("workout_date,shift,sequence_number")
        .eq("participant_id", participant_id)
        .eq("is_valid", True)
        .is_("deleted_at", "null")
        .execute()
    )
    rows = result.data or []
    occupied = {(r["workout_date"], r["shift"]) for r in rows}
    registered_seqs = {r["sequence_number"] for r in rows}
    max_seq = max(registered_seqs, default=0)
    count = len(rows)
    return occupied, max_seq, count, registered_seqs


def _missing_sequences(registered_seqs: set, max_seq: int, target: int) -> list[int]:
    """Retorna os números de sequência faltando. Gaps primeiro, depois novos após max_seq."""
    gaps = sorted(set(range(1, max_seq + 1)) - registered_seqs)
    new_seqs = list(range(max_seq + 1, target + 1))
    return gaps + new_seqs


def build_inserts_forward(participant_id: str, current_count: int, target: int,
                          registered_seqs: set, max_seq: int,
                          occupied: set, start_date: date) -> list[dict]:
    """Distribui treinos para frente a partir de start_date."""
    seqs_to_insert = _missing_sequences(registered_seqs, max_seq, target)
    to_insert = []
    current_date = start_date

    for seq in seqs_to_insert:
        while True:
            slot_key = (current_date.isoformat(), SHIFT)
            if slot_key not in occupied:
                submitted_at = BR_TZ.localize(datetime(
                    current_date.year, current_date.month, current_date.day, HOUR, 0, 0
                ))
                to_insert.append({
                    "participant_id": participant_id,
                    "workout_date": current_date.isoformat(),
                    "submitted_at": submitted_at.isoformat(),
                    "sequence_number": seq,
                    "shift": SHIFT,
                    "is_valid": True,
                })
                current_date += timedelta(days=1)
                break
            current_date += timedelta(days=1)

    return to_insert


def build_inserts_backward(participant_id: str, current_count: int, target: int,
                           registered_seqs: set, max_seq: int,
                           occupied: set, final_date: date) -> list[dict]:
    """Distribui treinos para trás a partir de final_date (o último treino cai em final_date)."""
    seqs_to_insert = _missing_sequences(registered_seqs, max_seq, target)
    missing = len(seqs_to_insert)

    # Coleta slots disponíveis indo para trás
    slots = []
    current_date = final_date
    while len(slots) < missing:
        slot_key = (current_date.isoformat(), SHIFT)
        if slot_key not in occupied:
            slots.append(current_date)
        current_date -= timedelta(days=1)

    slots.sort()  # mais antigo primeiro
    to_insert = []
    for d, seq in zip(slots, seqs_to_insert):
        submitted_at = BR_TZ.localize(datetime(d.year, d.month, d.day, HOUR, 0, 0))
        to_insert.append({
            "participant_id": participant_id,
            "workout_date": d.isoformat(),
            "submitted_at": submitted_at.isoformat(),
            "sequence_number": seq,
            "shift": SHIFT,
            "is_valid": True,
        })

    return to_insert


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostra o que seria inserido")
    args = parser.parse_args()

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    supabase = get_supabase()

    if args.dry_run:
        print("\n=== DRY-RUN — nenhum dado será gravado ===\n")
    else:
        print("\n=== Correcao de Contagens de Treino ===\n")

    all_inserts: list[tuple[str, list[dict]]] = []

    for name, cfg in TARGETS.items():
        if isinstance(cfg, dict):
            target = cfg["count"]
            final_date = cfg.get("final_date")
        else:
            target = cfg
            final_date = None

        try:
            participant = get_participant(supabase, name)
        except ValueError as e:
            print(f"  ERRO: {e}")
            continue

        occupied, max_seq, current_count, registered_seqs = get_occupied_slots(supabase, participant["id"])

        if current_count >= target:
            print(f"  {name}: já tem {current_count} treinos (target={target}). Nada a fazer.")
            continue

        missing = target - current_count

        if final_date:
            inserts = build_inserts_backward(participant["id"], current_count, target, registered_seqs, max_seq, occupied, final_date)
        else:
            last_dates = [d for (d, _) in occupied]
            start_date = date.fromisoformat(max(last_dates)) + timedelta(days=1) if last_dates else date.today()
            inserts = build_inserts_forward(participant["id"], current_count, target, registered_seqs, max_seq, occupied, start_date)

        all_inserts.append((name, inserts))

        seqs_inserted = [r["sequence_number"] for r in inserts]
        flag = f" (último treino em {final_date.strftime('%d/%m/%Y')})" if final_date else ""
        print(f"  {name}: {current_count} → {target} (+{missing} treinos){flag}")
        print(f"    Sequências: {min(seqs_inserted)} até {max(seqs_inserted)}")
        print(f"    Datas: {inserts[0]['workout_date']} até {inserts[-1]['workout_date']}")
        print()

    if not all_inserts:
        print("Nada a inserir.")
        return

    total = sum(len(ins) for _, ins in all_inserts)
    print(f"Total a inserir: {total} treino(s)")

    if args.dry_run:
        print("\nDry-run concluído. Rode sem --dry-run para inserir.")
        return

    print("\nConfirmar inserção? (s/N): ", end="")
    answer = input().strip().lower()
    if answer != "s":
        print("Cancelado.")
        return

    print()
    ok = 0
    for name, inserts in all_inserts:
        for row in inserts:
            try:
                supabase.table("workouts").upsert(row, on_conflict="participant_id,workout_date,shift").execute()
                ok += 1
            except Exception as e:
                print(f"  ERRO {name} seq={row['sequence_number']}: {e}")
        print(f"  OK  {name}: {len(inserts)} treinos inseridos")

    print(f"\nConcluído! {ok}/{total} treino(s) inserido(s).\n")


if __name__ == "__main__":
    main()
