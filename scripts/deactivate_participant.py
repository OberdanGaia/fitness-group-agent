"""
Desativa um participante que saiu do grupo.
O histórico de treinos é preservado, mas o participante
sai dos relatórios e não terá novos treinos contabilizados.

Uso: python scripts/deactivate_participant.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.client import get_supabase

NAME = "Natan"


def main():
    print(f"\n=== Desativar participante: {NAME} ===\n")

    supabase = get_supabase()

    result = supabase.table("participants").select("id,name,phone,lid,is_active").ilike("name", f"%{NAME}%").execute()
    participants = result.data or []

    if not participants:
        print(f"Nenhum participante encontrado com nome '{NAME}'.")
        sys.exit(1)

    if len(participants) > 1:
        print("Mais de um participante encontrado:")
        for p in participants:
            print(f"  {p['name']} (id={p['id']}, ativo={p['is_active']})")
        print("\nAjuste o filtro NAME para ser mais específico.")
        sys.exit(1)

    p = participants[0]
    print(f"Participante encontrado:")
    print(f"  Nome:   {p['name']}")
    print(f"  Fone:   {p['phone']}")
    print(f"  LID:    {p['lid']}")
    print(f"  Ativo:  {p['is_active']}")

    if not p["is_active"]:
        print(f"\n{p['name']} já está desativado.")
        return

    print(f"\nAção: setar is_active = False (histórico de treinos preservado)")
    confirm = input("Confirma? (s/n): ").strip().lower()
    if confirm != "s":
        print("Cancelado.")
        return

    supabase.table("participants").update({"is_active": False}).eq("id", p["id"]).execute()

    print(f"\n  OK  {p['name']} desativado com sucesso!")
    print(f"      Treinos anteriores preservados no banco.")
    print(f"      Não aparecerá mais nos relatórios.\n")


if __name__ == "__main__":
    main()
