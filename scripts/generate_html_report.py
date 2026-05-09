"""
Gera um relatório HTML completo com indicadores do grupo Fitness 2026.
O arquivo gerado é salvo em reports/relatorio_fitness2026.html

Uso: python scripts/generate_html_report.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
from calendar import monthrange
from datetime import date, timedelta
from collections import defaultdict

from supabase import create_client, Client
from app.core.constants import CHALLENGE_START, CHALLENGE_END, CHALLENGE_DAYS, GOAL


def get_supabase() -> Client:
    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY devem estar definidos")
    return create_client(url, key)

OUTPUT_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "reports", "relatorio_fitness2026.html")

BOT_START_DATE = date(2026, 4, 25)

MONTHS_PT = {
    1: "Janeiro", 2: "Fevereiro", 3: "Março", 4: "Abril",
    5: "Maio", 6: "Junho", 7: "Julho", 8: "Agosto",
    9: "Setembro", 10: "Outubro", 11: "Novembro", 12: "Dezembro",
}


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

    workouts = []
    offset = 0
    while True:
        batch = (
            supabase.table("workouts")
            .select("participant_id,workout_date,shift,photo_message_id,text_message_id")
            .eq("is_valid", True)
            .is_("deleted_at", "null")
            .range(offset, offset + 999)
            .execute().data or []
        )
        workouts.extend(batch)
        if len(batch) < 1000:
            break
        offset += 1000

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


def get_prev_month_range(today: date) -> tuple[date, date, str]:
    prev_month = today.month - 1 if today.month > 1 else 12
    prev_year = today.year if today.month > 1 else today.year - 1
    last_day = monthrange(prev_year, prev_month)[1]
    return date(prev_year, prev_month, 1), date(prev_year, prev_month, last_day), MONTHS_PT[prev_month]


def process_data(participants, counts, consecutive, workouts):
    today = date.today()
    days_elapsed = (today - CHALLENGE_START).days + 1
    days_remaining = (CHALLENGE_END - today).days
    eight_weeks_ago = today - timedelta(weeks=8)
    total_recent_weeks = {(today - timedelta(weeks=i)).isocalendar()[:2] for i in range(8)}

    prev_month_start, prev_month_end, prev_month_name = get_prev_month_range(today)

    workouts_by_pid = defaultdict(list)
    monthly_counts_by_pid = defaultdict(int)
    for w in workouts:
        wd = date.fromisoformat(w["workout_date"])
        has_msg_id = bool(w.get("photo_message_id") or w.get("text_message_id"))
        workouts_by_pid[w["participant_id"]].append((wd, w["shift"], has_msg_id))
        if prev_month_start <= wd <= prev_month_end:
            monthly_counts_by_pid[w["participant_id"]] += 1

    # Atleta do mês
    pid_lookup = {p["id"]: p["name"] for p in participants}
    athlete_pid = max(monthly_counts_by_pid, key=monthly_counts_by_pid.get) if monthly_counts_by_pid else None
    athlete_name = pid_lookup.get(athlete_pid, "—") if athlete_pid else "—"
    athlete_count = monthly_counts_by_pid.get(athlete_pid, 0) if athlete_pid else 0

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

        for wd, shift, has_msg_id in workouts_by_pid.get(pid, []):
            if has_msg_id:
                shift_counts[shift] += 1
            dates_list.append(wd)
            week = wd.isocalendar()[:2]
            if week in total_recent_weeks:
                recent_weeks.add(week)

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
    best_streak = max(ranking, key=lambda x: x["max_streak"])
    on_pace_count = sum(1 for r in ranking if r["on_pace"])

    # Weekly trend — last 8 weeks
    weekly_counts = defaultdict(int)
    for w in workouts:
        wd = date.fromisoformat(w["workout_date"])
        if wd >= eight_weeks_ago:
            week_start = wd - timedelta(days=wd.weekday())
            weekly_counts[week_start] += 1
    weeks_sorted = sorted(weekly_counts)
    weekly_labels = [w.strftime("%d/%m") for w in weeks_sorted]
    weekly_values = [weekly_counts[w] for w in weeks_sorted]

    # Shift distribution — apenas treinos capturados pelo bot (com message_id)
    shift_total = defaultdict(int)
    for w in workouts:
        if w.get("photo_message_id") or w.get("text_message_id"):
            shift_total[w["shift"]] += 1
    shift_map = {"manha": "Manhã", "tarde": "Tarde", "noite": "Noite", "madrugada": "Madrugada"}
    shift_labels = [shift_map.get(s, s) for s in shift_total]
    shift_values = list(shift_total.values())

    # Day of week — percentages from BOT_START_DATE, bot-captured only
    dow_occurrences = [0] * 7
    cur = BOT_START_DATE
    while cur <= today:
        dow_occurrences[cur.weekday()] += 1
        cur += timedelta(days=1)

    n_participants = len(participants)
    dow_counts_group = defaultdict(int)
    dow_counts_by_pid = defaultdict(lambda: defaultdict(int))
    for w in workouts:
        wd = date.fromisoformat(w["workout_date"])
        has_msg_id = bool(w.get("photo_message_id") or w.get("text_message_id"))
        if has_msg_id and wd >= BOT_START_DATE:
            dow = wd.weekday()
            dow_counts_group[dow] += 1
            dow_counts_by_pid[w["participant_id"]][dow] += 1

    dow_labels = ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]
    dow_pct_group = [
        round(dow_counts_group[i] / (dow_occurrences[i] * n_participants) * 100)
        if dow_occurrences[i] > 0 else 0
        for i in range(7)
    ]
    dow_by_participant = {}
    for p in participants:
        pid = p["id"]
        dow_by_participant[p["name"]] = [
            round(dow_counts_by_pid[pid][i] / dow_occurrences[i] * 100)
            if dow_occurrences[i] > 0 else 0
            for i in range(7)
        ]

    return {
        "today": today.strftime("%d/%m/%Y"),
        "days_remaining": days_remaining,
        "total_workouts": total_workouts,
        "total_goal": total_goal,
        "group_pct": group_pct,
        "on_pace_count": on_pace_count,
        "behind_count": len(ranking) - on_pace_count,
        "best_streak_name": best_streak["name"],
        "best_streak_days": best_streak["max_streak"],
        "athlete_name": athlete_name,
        "athlete_count": athlete_count,
        "athlete_month": prev_month_name,
        "ranking": ranking,
        "weekly_labels": weekly_labels,
        "weekly_values": weekly_values,
        "shift_labels": shift_labels,
        "shift_values": shift_values,
        "dow_labels": dow_labels,
        "dow_pct_group": dow_pct_group,
        "dow_by_participant": dow_by_participant,
        "participant_names": [p["name"] for p in participants],
    }


# ── HTML generation ───────────────────────────────────────────────────────────

SHIFT_ICON = {"manha": "🌅 Manhã", "tarde": "☀️ Tarde", "noite": "🌙 Noite", "madrugada": "🌑 Madrugada"}


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
    rows = build_ranking_rows(data["ranking"])

    weekly_json    = json.dumps(data["weekly_labels"])
    weekly_val     = json.dumps(data["weekly_values"])
    shift_json     = json.dumps(data["shift_labels"])
    shift_val      = json.dumps(data["shift_values"])
    dow_json           = json.dumps(data["dow_labels"])
    dow_pct_group_json = json.dumps(data["dow_pct_group"])
    dow_by_part_json   = json.dumps(data["dow_by_participant"])
    participant_names_json = json.dumps(data["participant_names"])

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Fitness 2026 — Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<style>
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Segoe UI',system-ui,sans-serif;background:#f1f5f9;color:#1e293b}}

  header{{background:linear-gradient(135deg,#1e3a5f,#0ea5e9);color:#fff;padding:28px 40px;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:12px}}
  header h1{{font-size:24px;font-weight:700}}
  header p{{opacity:.85;font-size:13px;margin-top:4px}}
  header .date-badge{{background:rgba(255,255,255,.15);border-radius:99px;padding:6px 16px;font-size:13px;white-space:nowrap}}
  .view-toggle{{background:rgba(255,255,255,.15);border:1.5px solid rgba(255,255,255,.4);color:#fff;border-radius:99px;padding:8px 18px;font-size:13px;font-weight:600;cursor:pointer;display:flex;align-items:center;gap:8px;transition:background .2s;white-space:nowrap}}
  .view-toggle:hover{{background:rgba(255,255,255,.25)}}

  /* Mobile view */
  body.mobile-view .container{{max-width:430px;padding:16px 12px}}
  body.mobile-view .kpis{{grid-template-columns:repeat(2,1fr);gap:10px;margin-bottom:16px}}
  body.mobile-view .kpi{{padding:16px 12px}}
  body.mobile-view .kpi .kpi-val{{font-size:22px}}
  body.mobile-view .kpi .kpi-lbl{{font-size:10px}}
  body.mobile-view .kpi .kpi-sub{{font-size:11px}}
  body.mobile-view .kpi .kpi-desc{{font-size:9px}}
  body.mobile-view section{{padding:16px 12px;margin-bottom:14px}}
  body.mobile-view section h2{{font-size:12px;margin-bottom:14px}}
  body.mobile-view .charts{{grid-template-columns:1fr;gap:14px;margin-bottom:14px}}
  body.mobile-view .chart-box{{padding:16px 12px}}
  body.mobile-view .chart-box h2{{font-size:12px;margin-bottom:12px}}
  body.mobile-view .table-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch}}
  body.mobile-view table{{font-size:12px;min-width:600px}}
  body.mobile-view th,body.mobile-view td{{padding:9px 8px}}
  body.mobile-view td.name{{position:sticky;left:0;background:#fff;z-index:1;box-shadow:2px 0 4px rgba(0,0,0,.06)}}
  body.mobile-view tr:hover td.name{{background:#f8fafc}}
  body.mobile-view .bar-wrap{{min-width:70px}}
  body.mobile-view header{{padding:20px 16px}}
  body.mobile-view header h1{{font-size:18px}}
  body.mobile-view footer{{font-size:11px;padding:14px}}

  .container{{max-width:1300px;margin:0 auto;padding:28px 20px}}

  /* KPIs */
  .kpis{{display:grid;grid-template-columns:repeat(5,1fr);gap:14px;margin-bottom:28px}}
  .kpi{{background:#fff;border-radius:14px;padding:22px 18px;box-shadow:0 1px 4px rgba(0,0,0,.07);display:flex;flex-direction:column;gap:6px;border-top:4px solid transparent}}
  .kpi.blue{{border-color:#0ea5e9}}.kpi.green{{border-color:#22c55e}}.kpi.purple{{border-color:#8b5cf6}}.kpi.orange{{border-color:#f59e0b}}.kpi.pink{{border-color:#ec4899}}
  .kpi .kpi-icon{{font-size:22px;line-height:1}}
  .kpi .kpi-lbl{{font-size:11px;text-transform:uppercase;letter-spacing:.6px;color:#64748b;font-weight:600}}
  .kpi .kpi-val{{font-size:28px;font-weight:800;color:#1e293b;line-height:1.1}}
  .kpi .kpi-sub{{font-size:12px;color:#94a3b8}}
  .kpi .kpi-desc{{font-size:10px;color:#cbd5e1;font-style:italic;line-height:1.4;margin-top:2px}}

  /* Sections */
  section{{background:#fff;border-radius:14px;padding:24px;box-shadow:0 1px 4px rgba(0,0,0,.07);margin-bottom:22px}}
  section h2{{font-size:13px;font-weight:700;color:#334155;margin-bottom:20px;text-transform:uppercase;letter-spacing:.5px;border-left:3px solid #0ea5e9;padding-left:10px}}

  /* Table */
  table{{width:100%;border-collapse:collapse;font-size:13px}}
  th{{padding:9px 12px;background:#f8fafc;color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:.4px;border-bottom:1px solid #e2e8f0;text-align:left;white-space:nowrap}}
  td{{padding:11px 12px;border-bottom:1px solid #f1f5f9;vertical-align:middle}}
  tr:last-child td{{border-bottom:none}}
  tr:hover td{{background:#f8fafc}}
  td.center{{text-align:center}}
  td.name{{font-weight:600}}
  .bar-wrap{{position:relative;background:#f1f5f9;border-radius:99px;height:18px;min-width:100px;overflow:hidden}}
  .bar{{height:100%;border-radius:99px}}
  .bar-label{{position:absolute;right:6px;top:50%;transform:translateY(-50%);font-size:11px;font-weight:600;color:#334155}}
  .badge{{display:inline-block;padding:3px 9px;border-radius:99px;font-size:11px;font-weight:500}}
  .badge.on-pace{{background:#dcfce7;color:#166534}}
  .badge.behind{{background:#fef9c3;color:#854d0e}}

  /* Charts */
  .charts{{display:grid;grid-template-columns:2fr 1fr;gap:22px;margin-bottom:22px}}
  .chart-box{{background:#fff;border-radius:14px;padding:24px;box-shadow:0 1px 4px rgba(0,0,0,.07)}}
  .chart-box h2{{font-size:13px;font-weight:700;color:#334155;margin-bottom:18px;text-transform:uppercase;letter-spacing:.5px;border-left:3px solid #0ea5e9;padding-left:10px}}

  footer{{text-align:center;font-size:12px;color:#94a3b8;padding:20px}}

  @media(max-width:1024px){{.kpis{{grid-template-columns:repeat(3,1fr)}}}}
  @media(max-width:768px){{
    header{{padding:18px 16px}}
    header h1{{font-size:18px}}
    .view-toggle{{display:none}}
    .container{{padding:14px 10px}}
    .kpis{{grid-template-columns:repeat(2,1fr);gap:8px;margin-bottom:14px}}
    .kpi{{padding:12px 10px;gap:3px}}
    .kpi .kpi-icon{{font-size:16px}}
    .kpi .kpi-lbl{{font-size:9px;letter-spacing:.3px}}
    .kpi .kpi-val{{font-size:20px}}
    .kpi .kpi-sub{{font-size:10px}}
    .kpi .kpi-desc{{font-size:9px}}
    section{{padding:14px 10px;margin-bottom:12px}}
    section h2{{font-size:11px;margin-bottom:12px}}
    .charts{{grid-template-columns:1fr;gap:12px;margin-bottom:12px}}
    .chart-box{{padding:14px 10px}}
    .chart-box h2{{font-size:11px;margin-bottom:10px}}
    .table-wrap{{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:0 -10px;padding:0 10px}}
    table{{font-size:12px;min-width:640px}}
    th{{padding:8px 10px;font-size:10px}}
    td{{padding:9px 10px;white-space:nowrap}}
    td.name{{position:sticky;left:0;background:#fff;z-index:1;box-shadow:2px 0 6px rgba(0,0,0,.08)}}
    tr:hover td.name{{background:#f8fafc}}
    .bar-wrap{{min-width:70px}}
    .badge{{padding:2px 7px;font-size:10px}}
    footer{{font-size:11px;padding:14px}}
  }}
</style>
</head>
<body>

<header>
  <div>
    <h1>🏋️ Perde treino, perde dinheiro 2026</h1>
    <p>Dashboard do grupo — atualizado em {data['today']}</p>
  </div>
  <div style="display:flex;align-items:center;gap:10px">
    <div class="date-badge">📅 {data['days_remaining']} dias restantes</div>
    <button class="view-toggle" id="viewToggleBtn" onclick="toggleView()">📱 Ver no celular</button>
  </div>
</header>

<div class="container">

  <!-- KPIs -->
  <div class="kpis">
    <div class="kpi blue">
      <span class="kpi-icon">🏋️</span>
      <span class="kpi-lbl">Treinos do grupo</span>
      <span class="kpi-val">{data['total_workouts']}</span>
      <span class="kpi-sub">de {data['total_goal']} no total</span>
    </div>
    <div class="kpi green">
      <span class="kpi-icon">📈</span>
      <span class="kpi-lbl">Progresso coletivo</span>
      <span class="kpi-val">{data['group_pct']}%</span>
      <span class="kpi-sub">da meta total do grupo</span>
    </div>
    <div class="kpi purple">
      <span class="kpi-icon">📅</span>
      <span class="kpi-lbl">Dias restantes</span>
      <span class="kpi-val">{data['days_remaining']}</span>
      <span class="kpi-sub">até 20/12/2026</span>
    </div>
    <div class="kpi orange">
      <span class="kpi-icon">🔥</span>
      <span class="kpi-lbl">Maior streak histórico</span>
      <span class="kpi-val">{data['best_streak_days']} dias</span>
      <span class="kpi-sub">{data['best_streak_name']}</span>
      <span class="kpi-desc">Maior sequência de dias consecutivos treinados</span>
    </div>
    <div class="kpi pink">
      <span class="kpi-icon">🏆</span>
      <span class="kpi-lbl">Atleta de {data['athlete_month']}</span>
      <span class="kpi-val">{data['athlete_count']} treinos</span>
      <span class="kpi-sub">{data['athlete_name']}</span>
      <span class="kpi-desc">Quem mais treinou no mês anterior</span>
    </div>
  </div>

  <!-- Ranking -->
  <section>
    <h2>Ranking dos participantes</h2>
    <div class="table-wrap">
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
    </div>
  </section>

  <!-- Charts row 1 -->
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

  <!-- Charts row 2 -->
  <section>
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:18px">
      <h2 style="margin-bottom:0">Treinos por dia da semana</h2>
      <select id="dowFilter" onchange="updateDowChart()" style="font-size:13px;padding:6px 12px;border-radius:8px;border:1px solid #e2e8f0;color:#334155;background:#f8fafc;cursor:pointer">
        <option value="__grupo__">Grupo inteiro</option>
        {''.join(f'<option value="{name}">{name}</option>' for name in data['participant_names'])}
      </select>
    </div>
    <canvas id="dowChart" height="70"></canvas>
  </section>

</div>

<footer>Fitness 2026 · Gerado em {data['today']}</footer>

<script>
const weeklyLabels = {weekly_json};
const weeklyValues = {weekly_val};
const shiftLabels  = {shift_json};
const shiftValues  = {shift_val};
const dowLabels        = {dow_json};
const dowPctGroup      = {dow_pct_group_json};
const dowByParticipant = {dow_by_part_json};

new Chart(document.getElementById('weeklyChart'), {{
  type: 'bar',
  data: {{ labels: weeklyLabels, datasets: [{{ label: 'Treinos', data: weeklyValues, backgroundColor: '#0ea5e9', borderRadius: 6 }}] }},
  options: {{ plugins: {{ legend: {{ display: false }} }}, scales: {{ y: {{ beginAtZero: true, ticks: {{ stepSize: 1 }} }} }} }}
}});

new Chart(document.getElementById('shiftChart'), {{
  type: 'doughnut',
  data: {{ labels: shiftLabels, datasets: [{{ data: shiftValues, backgroundColor: ['#f59e0b','#0ea5e9','#6366f1','#94a3b8'], borderWidth: 0 }}] }},
  options: {{ plugins: {{ legend: {{ position: 'bottom' }} }}, cutout: '60%' }}
}});

const dowChart = new Chart(document.getElementById('dowChart'), {{
  type: 'bar',
  data: {{ labels: dowLabels, datasets: [{{ label: '% de aproveitamento', data: dowPctGroup, backgroundColor: '#6366f1', borderRadius: 6 }}] }},
  options: {{
    plugins: {{ legend: {{ display: false }} }},
    scales: {{ y: {{ beginAtZero: true, max: 100, ticks: {{ callback: v => v + '%' }} }} }}
  }}
}});

function updateDowChart() {{
  const key = document.getElementById('dowFilter').value;
  const data = key === '__grupo__' ? dowPctGroup : (dowByParticipant[key] || dowPctGroup);
  dowChart.data.datasets[0].data = data;
  dowChart.update();
}}

function toggleView() {{
  const isMobile = document.body.classList.toggle('mobile-view');
  document.getElementById('viewToggleBtn').textContent = isMobile ? '🖥️ Ver no computador' : '📱 Ver no celular';
}}
</script>
</body>
</html>"""


# ── Entry point ───────────────────────────────────────────────────────────────

def main():
    print("\n=== Dashboard HTML — Fitness 2026 ===\n")
    print("Buscando dados do banco...")
    participants, counts, consecutive, workouts = fetch_data()
    print(f"{len(participants)} participantes | {len(workouts)} treinos\n")

    print("Processando indicadores...")
    data = process_data(participants, counts, consecutive, workouts)

    print("Gerando HTML...")
    html = generate_html(data)

    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\n✅ Dashboard gerado: {OUTPUT_PATH}")
    print("Abra o arquivo no navegador para visualizar.\n")


if __name__ == "__main__":
    main()
