"""
Importa treinos do arquivo de exportação do WhatsApp para o banco de dados.
Só considera mensagens com foto + N/200 como treinos válidos.

Uso:
  python scripts/import_whatsapp_workouts.py whatsapp_export.txt --dry-run
  python scripts/import_whatsapp_workouts.py whatsapp_export.txt --from-date 2026-05-19
"""

import argparse
import re
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, date
from collections import defaultdict

import pytz

from app.db.client import get_supabase
from app.services.message_parser import get_shift, WORKOUT_PATTERN

BR_TZ = pytz.timezone("America/Sao_Paulo")

MSG_RE = re.compile(
    r"^(\d{2}/\d{2}/\d{4}) (\d{1,2}:\d{2}) "
    r"(da manh[aã]|da tarde|da noite|da madrugada|meio-dia|meia-noite) "
    r"- (.+?):\s*(.*)",
    re.IGNORECASE,
)
HAS_MEDIA_RE = re.compile(r"<M[íi]dia oculta>|arquivo anexado", re.IGNORECASE)

# Mapeamento de nomes/telefones do export → nome no banco de dados
SENDER_MAP: dict[str, str] = {
    # Nomes (case-insensitive via .lower() abaixo)
    "oberdan hideki": "Oberdan",
    "amor 🤍🌍": "Heloisa",
    "amor": "Heloisa",
    "marcela lima": "Marcela",
    "beatriz itaú": "Bia",
    "carol amiga helo": "Carol",
    "pedro bassi": "Pedro",
    "edu": "Du",
    "gui pacheco": "Gui Pacheco",
    "guilherme tadiello": "Gui Tadiello",
    "alan itaú": "Alan",
    "david infields": "David",
    "pri cordeiro": "Pri Cordeiro",
    "gabie 💛 irmã helo": "Gabie",
    "gabie": "Gabie",
    "stephanie": "Ste",
    "francine frota ✨": "Fran",
    "francine frota": "Fran",
    "iago garcia": "Iago",
    "valentina": "Valentina",
    "jhenifer camargo": "Jheni",
    "~bruno 🏹": "Piazzi",
    "bruno 🏹": "Piazzi",
    "bruno": "Piazzi",
    # Telefones (aparecem quando o contato não está salvo)
    "+55 11 95355-7596": "Marcela",
    "+55 11 91775-1307": "Piazzi",
    "+55 11 96673-9090": "Ste",
    "+55 19 99970-4185": "Valentina",
    "+55 11 95361-3865": "Pri Cordeiro",
    "+55 19 99444-8054": "Jheni",
    "+55 11 98430-4898": "Bia",
}


def parse_export(filepath: str, from_date: date, to_date: date) -> list[dict]:
    """Lê o arquivo de exportação e retorna lista de treinos candidatos."""
    with open(filepath, encoding="utf-8") as f:
        lines = f.readlines()

    candidates = []
    current: dict | None = None

    def flush(msg: dict | None) -> None:
        if not msg:
            return
        body = msg["body"]
        if not HAS_MEDIA_RE.search(body):
            return
        seq = None
        for m in WORKOUT_PATTERN.finditer(body):
            n = int(m.group(1))
            if 1 <= n <= 200:
                seq = n
                break
        if seq is None:
            return
        if not (from_date <= msg["workout_date"] <= to_date):
            return
        sender_key = msg["sender"].lower().strip()
        db_name = SENDER_MAP.get(sender_key)
        if db_name is None:
            return
        candidates.append({
            "sender": msg["sender"],
            "db_name": db_name,
            "workout_date": msg["workout_date"],
            "submitted_at": msg["submitted_at"],
            "sequence_number": seq,
            "shift": msg["shift"],
        })

    for raw_line in lines:
        line = raw_line.rstrip("\n")
        m = MSG_RE.match(line)
        if m:
            flush(current)
            date_str, time_str, _period, sender, text = m.groups()
            try:
                naive_dt = datetime.strptime(f"{date_str} {time_str}", "%d/%m/%Y %H:%M")
            except ValueError:
                current = None
                continue
            local_dt = BR_TZ.localize(naive_dt)
            current = {
                "sender": sender,
                "workout_date": local_dt.date(),
                "submitted_at": local_dt,
                "shift": get_shift(local_dt, "America/Sao_Paulo"),
                "body": text,
            }
        elif current is not None:
            current["body"] += "\n" + line

    flush(current)
    return candidates


def load_participants() -> dict[str, dict]:
    """Retorna {nome: {id, name}} de todos os participantes ativos."""
    result = get_supabase().table("participants").select("id,name").eq("is_active", True).execute()
    return {p["name"]: p for p in (result.data or [])}


def load_registered_sequences() -> dict[str, set[int]]:
    """Retorna {participant_id: {seq_numbers}} via RPC."""
    result = get_supabase().rpc("get_registered_sequences").execute()
    return {
        row["participant_id"]: set(row["sequences"] or [])
        for row in (result.data or [])
    }


def insert_workout(participant: dict, workout: dict) -> None:
    get_supabase().table("workouts").upsert(
        {
            "participant_id": participant["id"],
            "workout_date": workout["workout_date"].isoformat(),
            "submitted_at": workout["submitted_at"].isoformat(),
            "sequence_number": workout["sequence_number"],
            "shift": workout["shift"],
            "is_valid": True,
        },
        on_conflict="participant_id,workout_date,shift",
    ).execute()


def main() -> None:
    parser = argparse.ArgumentParser(description="Importa treinos do export do WhatsApp")
    parser.add_argument("filepath", help="Caminho para o arquivo .txt exportado do WhatsApp")
    parser.add_argument("--dry-run", action="store_true", help="Apenas mostra o que seria inserido, sem gravar")
    parser.add_argument(
        "--from-date",
        default="2026-05-19",
        help="Data inicial (YYYY-MM-DD). Padrão: 2026-05-19",
    )
    parser.add_argument(
        "--to-date",
        default=date.today().isoformat(),
        help="Data final (YYYY-MM-DD). Padrão: hoje",
    )
    args = parser.parse_args()

    from_date = date.fromisoformat(args.from_date)
    to_date = date.fromisoformat(args.to_date)

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(f"\n=== Importacao de Treinos do WhatsApp ===")
    print(f"Periodo: {from_date.strftime('%d/%m/%Y')} ate {to_date.strftime('%d/%m/%Y')}")
    if args.dry_run:
        print("MODO DRY-RUN -- nenhum dado sera gravado\n")

    print("Lendo arquivo de exportação...")
    candidates = parse_export(args.filepath, from_date, to_date)
    print(f"{len(candidates)} mensagens com foto + N/200 encontradas no período.\n")

    print("Carregando participantes e sequências registradas do banco...")
    participants = load_participants()
    registered_seqs = load_registered_sequences()

    # Filtra treinos já registrados e deduplica por (participante, seq)
    to_import: list[dict] = []
    seen: set[tuple] = set()
    skipped_registered = 0
    skipped_no_participant = 0

    for c in candidates:
        participant = participants.get(c["db_name"])
        if not participant:
            skipped_no_participant += 1
            continue
        pid = participant["id"]
        seq = c["sequence_number"]
        if seq in registered_seqs.get(pid, set()):
            skipped_registered += 1
            continue
        key = (pid, seq)
        if key in seen:
            continue
        seen.add(key)
        c["participant"] = participant
        to_import.append(c)

    print(f"Já registrados no banco (pulados): {skipped_registered}")
    print(f"Participante não encontrado (pulados): {skipped_no_participant}")
    print(f"Treinos novos para importar: {len(to_import)}\n")

    if not to_import:
        print("Nada a importar. Banco já está atualizado.")
        return

    # Exibe preview agrupado por participante
    by_participant: dict[str, list] = defaultdict(list)
    for w in sorted(to_import, key=lambda x: (x["db_name"], x["sequence_number"])):
        by_participant[w["db_name"]].append(w)

    print(f"{'#':<5} {'Participante':<20} {'Seq':<6} {'Data':<12} {'Turno'}")
    print("-" * 60)
    idx = 1
    for name, workouts in sorted(by_participant.items()):
        for w in workouts:
            print(
                f"{idx:<5} {name:<20} {w['sequence_number']:<6} "
                f"{w['workout_date'].strftime('%d/%m/%Y'):<12} {w['shift']}"
            )
            idx += 1

    print()

    if args.dry_run:
        print(f"Dry-run concluído. {len(to_import)} treino(s) seriam inseridos.")
        return

    print("Inserir todos os treinos acima? (s/N): ", end="")
    answer = input().strip().lower()
    if answer != "s":
        print("Cancelado. Nenhum treino inserido.")
        return

    print()
    ok = 0
    for w in to_import:
        try:
            insert_workout(w["participant"], w)
            print(f"  OK  {w['db_name']:<20} {w['sequence_number']}/200 em {w['workout_date'].strftime('%d/%m/%Y')} ({w['shift']})")
            ok += 1
        except Exception as e:
            print(f"  ERRO  {w['db_name']}: {e}")

    print(f"\nConcluído! {ok}/{len(to_import)} treino(s) inserido(s).\n")


if __name__ == "__main__":
    main()
