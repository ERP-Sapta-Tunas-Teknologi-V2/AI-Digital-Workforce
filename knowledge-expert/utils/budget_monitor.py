from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from utils.supabase_admin import supabase

DAILY_BUDGET = 1.0
WEEKLY_BUDGET = 5.0
BUDGET_WARNING_PERCENT = 80

JAKARTA = ZoneInfo("Asia/Jakarta")

def get_cost(start_date, end_date):
    chat = (
        supabase
        .table("chat_usage_logs")
        .select("total_cost")
        .gte("created_at", start_date)
        .lt("created_at", end_date)
        .execute()
    )

    index = (
        supabase
        .table("index_usage_logs")
        .select("embedding_cost")
        .gte("created_at", start_date)
        .lt("created_at", end_date)
        .execute()
    )

    chat_cost = sum(float(row["total_cost"] or 0) for row in chat.data or [])
    index_cost = sum(float(row["embedding_cost"] or 0) for row in index.data or [])

    return chat_cost + index_cost

def percentage(cost, budget):
    if budget <= 0:
        return 0

    return round(cost / budget * 100, 2)

def get_status(cost, budget):
    if budget <= 0:
        return "EXCEEDED"

    usage = cost / budget * 100

    if usage >= 100:
        return "EXCEEDED"
    if usage >= BUDGET_WARNING_PERCENT:
        return "WARNING"

    return "OK"

def create_alert(period_type, period_date, alert, data):
    if alert == "OK":
        return

    try:
        supabase.table("budget_alerts").insert({
            "period_type": period_type,
            "period_date": period_date.isoformat(),
            "alert_type": alert,
            "cost": data["cost"],
            "budget": data["budget"],
            "usage_percent": data["usage_percent"]
        }).execute()

        print(
            f"[BUDGET ALERT] "
            f"{period_type}={alert} "
            f"percentage={(data['cost'] / data['budget']):.0f} "
            f"cost={data['cost']:.10f} "
            f"budget={data['budget']:.10f}"
        )

    except Exception as e:
        # Duplicate alert dianggap sudah pernah dikirim.
        print(
            f"[BUDGET ALERT] failed: "
            f"{type(e).__name__}: {e}"
        )

def check_budget():
    today = datetime.now(JAKARTA).date()
    tomorrow = today + timedelta(days=1)

    daily_cost = get_cost(today.isoformat(), tomorrow.isoformat())

    week_start = today - timedelta(days=6)
    weekly_cost = get_cost(week_start.isoformat(), tomorrow.isoformat())

    daily_status = get_status(daily_cost, DAILY_BUDGET)
    weekly_status = get_status(weekly_cost, WEEKLY_BUDGET)

    daily = {
        "cost": daily_cost,
        "budget": DAILY_BUDGET,
        "usage_percent": percentage(daily_cost, DAILY_BUDGET),
        "status": daily_status
    }

    weekly = {
        "cost": weekly_cost,
        "budget": WEEKLY_BUDGET,
        "usage_percent": percentage(weekly_cost, WEEKLY_BUDGET),
        "status": weekly_status
    }

    create_alert("daily", today, daily_status, daily)
    create_alert("weekly", today, weekly_status, weekly)

    return { "daily": daily, "weekly": weekly }