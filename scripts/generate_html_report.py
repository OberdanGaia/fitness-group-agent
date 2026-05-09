"""
Gera um relatório HTML completo com indicadores do grupo Fitness 2026.
O arquivo gerado é salvo em reports/relatorio_fitness2026.html

Uso: python scripts/generate_html_report.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from datetime import date, timedelta
from collections import defaultdict

from app.core.config import settings
from app.core.constants import CHALLENGE_START, CHALLENGE_END, CHALLENGE_DAYS, GOAL
from app.db.client import get_supabase

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports", "relatorio_fitness2026.html")


# ── Data fetching ─────────────────────────────────────────────────────────────

def fetch_data():
    supabase = get_supabase()

    participants = (
        supabase.table("participants")
        .select("id,name,joined_at,medical_leave_days")
        .eq("is_active", True)
        .execute().data or []
    )
    counts_raw = supabase.rpc("get_workout_counts").execute().data or []
    counts = {r["participant_id"]: r["count"] for r in counts_raw}

    consecutive_raw = supabase.rpc("get_consecutive_days").execute().data or []
    consecutive = {r["participant_id"]: r["consecutive_days"] for r in consecutive_raw}

    workouts = (
        supabase.table("workouts")
        .select("participant_id,workout_date,shift")
        .eq("is_valid", True)
        .is_("deleted_at", "null")
        .limit(5000)
        .execute().data or []
    )
    return participants, counts, consecutive, workouts


# ── Calculations ──────────────────────────────────────────────────────────────

def calculate_goal(joined_at: date, medical_leave_days: int) -> int:
    participant_days = (CHALLENGE_END - max(joined_at, CHALLENGE_START)).days + 1
    effective_days = max(participant_days - medical_leave_days, 1)
    return max(round(GOAL * effective_days / CHALLENGE_DAYS), 1)


def calculate_max_streak(dates: list) -> int:
    if not dates:
        return 0
    sorted_dates = sorted(set(dates))
    max_streak = current = 1
    for i in range(1, len(sorted_dates)):
        if (sorted_dates[i] - sorted_dates[i - 1]).days == 1:
            current += 1
            max_streak = max(max_streak, current)
        else:
            current = 1
    return max_streak


def process_data(participants, counts, consecutive, workouts):
    today = date.today()
    days_elapsed = (today - CHALLENGE_START).days + 1
    days_remaining = (CHALLENGE_END - today).days

    workouts_by_pid = defaultdict(list)
    for w in workouts:
        workouts_by_pid[w["participant_id"]].append((date.fromisoformat(w["workout_date"]), w["shift"]))

    eight_weeks_ago = today - timedelta(weeks=8)
    total_recent_weeks = {(today - timedelta(weeks=i)).isocalendar()[:2] for i in range(8)}

    ranking = []
    for p in participants:
        pid = p["id"]
        joined = date.fromisoformat(p["joined_at"])
        goal = calculate_goal(joined, p.get("medical_leave_days", 0))
        count = counts.get(pid, 0)
        pct = round(count / goal * 100) if goal else 0
        expected = round(goal * days_elapsed / CHALLENGE_DAYS)

        shift_counts = defaultdict(int)
        dates_list = []
        recent_weeks = set()

        for workout_date, shift in workouts_by_pid.get(pid, []):
            shift_counts[shift] += 1
            dates_list.append(workout_date)
            if workout_date >= eight_weeks_ago:
                recent_weeks.add(workout_date.isocalendar()[:2])

        preferred_shift = max(shift_counts, key=shift_counts.get) if shift_counts else "-"
        max_streak = calculate_max_streak(dates_list)
        consistency = round(len(recent_weeks) / len(total_recent_weeks) * 100) if total_recent_weeks else 0

        ranking.append({
            "name": p["name"],
            "count": count,
            "goal": goal,
            "pct": pct,
            "on_pace": count >= expected,
            "preferred_shift": preferred_shift,
            "current_streak": consecutive.get(pid, 0),
            "max_streak": max_streak,
            "consistency": consistency,
        })

    ranking.sort(key=lambda x: x["count"], reverse=True)

    total_workouts = sum(r["count"] for r in ranking)
    total_goal = sum(r["goal"] for r in ranking)
    group_pct = round(total_workouts / total_goal * 100) if total_goal else 0
    on_pace_count = sum(1 for r in ranking if r["on_pace"])

    # Weekly trend — last 8 weeks
    weekly_counts = defaultdict(int)
    for w in workouts:
        d = date.fromisoformat(w["workout_date"])
        if d >= eight_weeks_ago:
            week_start = d - timedelta(days=d.weekday())
            weekly_counts[week_start] += 1
    weeks_sorted = sorted(weekly_counts)
    weekly_labels = [f"{w.strftime('%d/%m')}" for w in weeks_sorted]
    weekly_values = [weekly_counts[w] for w in weeks_sorted]

    # Shift distribution (group)
    shift_total = defaultdict(int)
    for w in workouts:
        shift_total[w["shift"]] += 1
    shift_map = {"manha": "Manhã", "tarde": "Tarde", "noite": "Noite"}
    shift_labels = [shift_map.get(s, s) for s in shift_total]
    shift_values = list(shift_total.values())

    # Day of week distribution
    dow_counts = defaultdict(int)
    for w in workouts:
        dow_counts[date.fromisoformat(w["workout_date"]).weekday()] += 1
    dow_labels = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    dow_values = [dow_counts[i] for i in range(7)]

    return {
        "today": today.strftime("%d/%m/%Y"),
        "days_remaining": days_remaining,
        "total_workouts": total_workouts,
        "total_goal": total_goal,
        "group_pct": group_pct,
        "on_pace_count": on_pace_count,
        "behind_count": len(ranking) - on_pace_count,
        "ranking": ranking,
        "weekly_labels": weekly_labels,
        "weekly_values": weekly_values,
        "shift_labels": shift_labels,
        "shift_values": shift_values,
        "dow_labels": dow_labels,
        "dow_values": dow_values,
    }


# ── HTML generation ───────────────────────────────────────────────────────────

SHIFT_ICON = {"manha": "🌅 Manhã", "tarde": "☀️ Tarde", "noite": "🌙 Noite"}


def build_ranking_rows(ranking: list) -> str:
    rows = ""
    medals = ["🥇", "🥈", "🥉"]
    for i, r in enumerate(ranking):
        pos = medals[i] if i < 3 else f"{i + 1}."
        pace = ('<span class="badge on-pace">✅ No ritmo</span>' if r["on_pace"]
                else '<span class="badge behind">⚠️ Atrasado</span>')
        bar_color = "#22c55e" if r["pct"] >= 75 else "#f59e0b" if r["pct"] >= 40 else "#ef4444"
        streak = f"{r['current_streak']} dias" if r["current_streak"] >= 2 else "—"
        rows += f"""
      <tr>
        <td class="center">{pos}</td>
        <td class="name">{r['name']}</td>
        <td class="center">{r['count']}/{r['goal']}</td>
        <td>
          <div class="bar-wrap">
            <div class="bar" style="width:{min(r['pct'], 100)}%;background:{bar_color}"></div>
            <span class="bar-label">{r['pct']}%</span>
          </div>
        </td>
        <td class="center">{pace}</td>
        <td class="center">{SHIFT_ICON.get(r['preferred_shift'], r['preferred_shift'])}</td>
        <td class="center">{streak}</td>
        <td class="center">{r['max_streak']} dias</td>
        <td class="center">{r['consistency']}%</td>
      </tr>"""
    return rows


def generate_html(data: dict) -> str:
    ranking = data["ranking"]
    best_streak = max(ranking, key=lambda x: x["max_streak"])
    most_consistent = max(ranking, key=lambda x: x["consistency"])
    rows = build_ranking_rows(ranking)

    weekly_json = json.dumps(data["weekly_labels"])
    weekly_val_json = json.dumps(data["weekly_values"])
    shift_json = json.dumps(data["shift_labels"])
    shift_val_json = json.dumps(data["shift_values"])
    dow_json = json.dumps(data["dow_labels"])
    dow_val_json = json.dumps(data["dow_values"])

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fitness 2026 — Relatório</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',system-ui,sans-serif;background:#f1f5f9;color:#1e293b}}
  header{{background:linear-gradient(135deg,#1e3a5f,#0ea5e9);color:#fff;padding:32px 40px}}
  header h1{{font-size:26px;font-weight:700}}
  header p{{opacity:.85;margin-top:6px;font-size:13px}}
  .container{{max-width:1200px;margin:0 auto;padding:28px 20px}}
  .cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:14px;margin-bottom:24px}}
  .card{{background:#fff;border-radius:12px;padding:22px;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
  .card .lbl{{font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:#64748b;margin-bottom:8px}}
  .card .val{{font-size:30px;font-weight:700;color:#0ea5e9}}
  .card .sub{{font-size:12px;color:#94a3b8;margin-top:4px}}
  section{{background:#fff;border-radius:12px;padding:22px;box-shadow:0 1px 4px rgba(0,0,0,.07);margin-bottom:22px}}
  section h2{{font-size:14px;font-weight:600;color:#334155;margin-bottom:18px;border-left:3px solid #0ea5e9;padding-left:10px;text-transform:uppercase;letter-spacing:.4px}}
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th{{padding:9px 11px;background:#f8fafc;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.4px;border-bottom:1px solid #e2e8f0;text-align:left}}
  td{{padding:11px;border-bottom:1px solid #f1f5f9;vertical-align:middle}}
  tr:last-child td{{border-bottom:none}}
  tr:hover td{{background:#f8fafc}}
  td.center{{text-align:center}}
  td.name{{font-weight:600}}
  .bar-wrap{{position:relative;background:#f1f5f9;border-radius:99px;height:18px;min-width:90px;overflow:hidden}}
  .bar{{height:100%;border-radius:99px}}
  .bar-label{{position:absolute;right:6px;top:50%;transform:translateY(-50%);font-size:11px;font-weight:600;color:#334155}}
  .badge{{display:inline-block;padding:3px 9px;border-radius:99px;font-size:11px;font-weight:500}}
  .badge.on-pace{{background:#dcfce7;color:#166534}}
  .badge.behind{{background:#fef9c3;color:#854d0e}}
  .charts{{display:grid;grid-template-columns:2fr 1fr;gap:22px;margin-bottom:22px}}
  .chart-box{{background:#fff;border-radius:12px;padding:22px;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
  .chart-box h2{{font-size:14px;font-weight:600;color:#334155;margin-bottom:18px;border-left:3px solid #0ea5e9;padding-left:10px;text-transform:uppercase;letter-spacing:.4px}}
  .highlights{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:14px;margin-bottom:22px}}
  .hl{{background:#fff;border-radius:12px;padding:20px;box-shadow:0 1px 4px rgba(0,0,0,.07);text-align:center}}
  .hl .icon{{font-size:28px;margin-bottom:8px}}
  .hl .hl-lbl{{font-size:11px;color:#64748b;text-transform:uppercase;letter-spacing:.4px}}
  .hl .hl-val{{font-size:22px;font-weight:700;color:#1e293b;margin-top:4px}}
  .hl .hl-sub{{font-size:12px;color:#94a3b8;margin-top:2px}}
  footer{{text-align:center;font-size:12px;color:#94a3b8;padding:20px}}
  @media(max-width:768px){{.charts{{grid-template-columns:1fr}}th,td{{padding:7px 6px}}}}
</style>
</head>
<body>

<header>
  <h1>🏋️ Perde treino, perde dinheiro 2026</h1>
  <p>Relatório gerado em {data['today']} &nbsp;·&nbsp; {data['days_remaining']} dias restantes na aposta</p>
</header>

<div class="container">

  <div class="cards">
    <div class="card">
      <div class="lbl">Treinos no grupo</div>
      <div class="val">{data['total_workouts']}</div>
      <div class="sub">de {data['total_goal']} no total</div>
    </div>
    <div class="card">
      <div class="lbl">Progresso coletivo</div>
      <div class="val">{data['group_pct']}%</div>
      <div class="sub">da meta total do grupo</div>
    </div>
    <div class="card">
      <div class="lbl">No ritmo</div>
      <div class="val">{data['on_pace_count']}</div>
      <div class="sub">{data['behind_count']} atrasados</div>
    </div>
    <div class="card">
      <div class="lbl">Dias restantes</div>
      <div class="val">{data['days_remaining']}</div>
      <div class="sub">até 20/12/2026</div>
    </div>
  </div>

  <section>
    <h2>Ranking dos participantes</h2>
    <table>
      <thead>
        <tr>
          <th class="center">#</th>
          <th>Nome</th>
          <th class="center">Treinos</th>
          <th>Progresso</th>
          <th class="center">Ritmo</th>
          <th class="center">Turno fav.</th>
          <th class="center">Streak atual</th>
          <th class="center">Maior streak</th>
          <th class="center">Consistência</th>
        </tr>
      </thead>
      <tbody>{rows}
      </tbody>
    </table>
  </section>

  <div class="highlights">
    <div class="hl">
      <div class="icon">🔥</div>
      <div class="hl-lbl">Maior streak histórico</div>
      <div class="hl-val">{best_streak['max_streak']} dias</div>
      <div class="hl-sub">{best_streak['name']}</div>
    </div>
    <div class="hl">
      <div class="icon">🏆</div>
      <div class="hl-lbl">Mais consistente (8 sem.)</div>
      <div class="hl-val">{most_consistent['consistency']}%</div>
      <div class="hl-sub">{most_consistent['name']}</div>
    </div>
    <div class="hl">
      <div class="icon">✅</div>
      <div class="hl-lbl">No ritmo para a meta</div>
      <div class="hl-val">{data['on_pace_count']} de {len(ranking)}</div>
      <div class="hl-sub">participantes</div>
    </div>
    <div class="hl">
      <div class="icon">📅</div>
      <div class="hl-lbl">Dias restantes</div>
      <div class="hl-val">{data['days_remaining']}</div>
      <div class="hl-sub">até 20/12/2026</div>
    </div>
  </div>

  <div class="charts">
    <div class="chart-box">
      <h2>Treinos por semana — últimas 8 semanas</h2>
      <canvas id="weeklyChart" height="110"></canvas>
    </div>
    <div class="chart-box">
      <h2>Distribuição por turno</h2>
      <canvas id="shiftChart"></canvas>
    </div>
  </div>

  <section>
    <h2>Treinos por dia da semana</h2>
    <canvas id="dowChart" height="70"></canvas>
  </section>

</div>

<footer>Fitness 2026 · Gerado automaticamente em {data['today']}</footer>

<script>
const weeklyLabels = {weekly_json};
const weeklyValues = {weekly_val_json};
const shiftLabels  = {shift_json};
const shiftValues  = {shift_val_json};
const dowLabels    = {dow_json};
const dowValues    = {dow_val_json};

new Chart(document.getElementById('weeklyChart'), {{
  type: 'bar',
  data: {{ labels: weeklyLabels, datasets: [{{ label: 'Treinos', data: weeklyValues, backgroundColor: '#0ea5e9', borderRadius: 6 }}] }},
  options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }} }} }}
}});

new Chart(document.getElementById('shiftChart'), {{
  type: 'doughnut',
  data: {{ labels: shiftLabels, datasets: [{{ data: shiftValues, backgroundColor: ['#f59e0b','#0ea5e9','#6366f1'], borderWidth: 0 }}] }},
  options: {{ plugins: {{ legend: {{ position: 'bottom' }} }}, cutout: '60%' }}
}});

new Chart(document.getElementById('dowChart'), {{
  type: 'bar',
  data: {{ labels: dowLabels, datasets: [{{ label: 'Treinos', data: dowValues, backgroundColor: '#6366f1', borderRadius: 6 }}] }},
  options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }} }} }}
}});
</script>
</body>
</html>"""


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("\n=== Relatório HTML — Fitness 2026 ===\n")
    print("Buscando dados do banco...")
    participants, counts, consecutive, workouts = fetch_data()
    print(f"{len(participants)} participantes | {len(workouts)} treinos\n")

    print("Processando indicadores...")
    data = process_data(participants, counts, consecutive, workouts)

    print("Gerando HTML...")
    html = generate_html(data)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Relatório gerado: {OUTPUT_PATH}")
    print("Abra o arquivo no navegador para visualizar.\n")


if __name__ == "__main__":
    main()
