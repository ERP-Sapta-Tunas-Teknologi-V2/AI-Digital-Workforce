import csv
import io
from utils.supabase_admin import supabase

def export_query_logs(start_date=None, end_date=None):
    query = (
        supabase.table("query_logs")
        .select("id,query,timestamp")
        .order("timestamp", desc=True)
    )

    if start_date:
        query = query.gte("timestamp", start_date)

    if end_date:
        query = query.lt("timestamp", end_date)

    result = query.execute()

    output = io.StringIO()
    output.write("\ufeff")
    
    writer = csv.writer(output)
    writer.writerow(["id", "query", "timestamp"])

    for row in result.data or []:
        writer.writerow([
            row["id"],
            row["query"],
            row["timestamp"]
        ])

    return output.getvalue()