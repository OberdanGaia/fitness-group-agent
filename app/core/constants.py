from datetime import date, time

SHIFTS: dict[str, tuple[time, time]] = {
    "madrugada": (time(0, 0),  time(5, 59, 59)),
    "manha":     (time(6, 0),  time(11, 59, 59)),
    "tarde":     (time(12, 0), time(17, 59, 59)),
    "noite":     (time(18, 0), time(23, 59, 59)),
}

MAX_WORKOUTS_PER_DAY = 2
MIN_INTERVAL_HOURS = 1
DEADLINE_HOURS = 3
CHALLENGE_START = date(2026, 1, 1)
CHALLENGE_END = date(2026, 12, 20)
CHALLENGE_DAYS = 354
GOAL = 200
PENALTY_MAX = 500.0

# Populated at startup from DB — do not hardcode
ADMIN_PHONES: set[str] = set()
MAIN_ADMIN_PHONE: str = ""
