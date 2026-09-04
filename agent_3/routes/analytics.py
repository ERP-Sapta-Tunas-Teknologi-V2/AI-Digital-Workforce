from flask import Blueprint, Response, request, jsonify
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sync.export_logs import export_query_logs
from utils.permissions import require_role
from utils.supabase_admin import supabase
from utils.budget_monitor import check_budget

analytics_bp = Blueprint("analytics", __name__)

JAKARTA_TZ = ZoneInfo("Asia/Jakarta")

def parse_date(value):
    if not value:
        return None

    try:
        return datetime.strptime(value, "%Y-%m-%d").replace(tzinfo=JAKARTA_TZ)
    except ValueError:
        raise ValueError("date must use YYYY-MM-DD format")

@analytics_bp.route("/logs/export", methods=["GET"])
@require_role("Marketing", "Product")
def export_logs():
    try:
        start = parse_date(request.args.get("start"))
        end = parse_date(request.args.get("end"))

        if start and end and start > end:
            return {"error": "start must not be after end"}, 400

        end = end + timedelta(days=1) if end else None

        csv_data = export_query_logs(
            start.isoformat() if start else None,
            end.isoformat() if end else None
        )

        return Response(
            csv_data,
            status=200,
            content_type="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": "attachment; filename=query_logs.csv"
            }
        )

    except ValueError as e:
        return {"error": str(e)}, 400

@analytics_bp.route("/logs/top-faq", methods=["GET"])
@require_role("Marketing", "Product")
def top_faq():
    days = request.args.get("days", 30, type=int)
    limit = request.args.get("limit", 5, type=int)

    result = supabase.rpc(
        "get_top_faq",
        {
            "days": days,
            "result_limit": limit
        }
    ).execute()

    return jsonify(result.data or [])

@analytics_bp.route("/cost/daily", methods=["GET"])
def daily_cost():
    report_date = request.args.get("date")
    params = {}

    if report_date:
        params["report_date"] = report_date

    result = (
        supabase
        .rpc("get_daily_cost_report", params)
        .execute()
    )

    data = result.data[0] if result.data else {}
    return jsonify(data)

@analytics_bp.route("/cost/weekly", methods=["GET"])
def weekly_cost():
    end_date = request.args.get("date")
    params = {}

    if end_date:
        params["end_date"] = end_date

    result = (
        supabase
        .rpc("get_weekly_cost_report", params)
        .execute()
    )

    return jsonify({"data": result.data or []})

@analytics_bp.route("/cost/budget", methods=["GET"])
def cost_budget():
    return jsonify(check_budget())