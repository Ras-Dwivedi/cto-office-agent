# src/pomodoro_recorder.py

from datetime import datetime


def record_pomodoro(pomodoros_col, cf_id, task_text, start, end, duration):
    pomodoros_col.insert_one({
        "cf_id": cf_id,
        "task_hint": task_text,
        "started_at": start,
        "ended_at": end,
        "duration_minutes": duration,
        "created_at": datetime.now()
    })
