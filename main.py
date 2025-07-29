from fastapi import FastAPI, Query
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
import psycopg2
from datetime import date, timedelta

app = FastAPI()

def get_db_connection():
    return psycopg2.connect(
        dbname="curify_local",
        user="postgres",
        password="2000914yy",
        host="localhost",
        port="5432"
    )

@app.get("/admin/metrics/business")
def get_metrics(query_date: date = Query(default=date(2025, 6, 30))):
    conn = get_db_connection()
    cursor = conn.cursor()

    today = query_date
    week_ago = today - timedelta(days=6)
    month_start = date(today.year, today.month, 1)

    # For revenue_by_day chart, show past 7 days
    start_date = today - timedelta(days=6)
    end_date = today

    # 1. Daily Active Users (DAU): Number of distinct users who created a project today
    cursor.execute("""
        SELECT COUNT(DISTINCT user_id)
        FROM project
        WHERE created_at::date = %s
    """, (today,))
    dau = cursor.fetchone()[0]

    # 2. Weekly Active Users (WAU): Number of distinct users who created a project in the last 7 days
    cursor.execute("""
        SELECT COUNT(DISTINCT user_id)
        FROM project
        WHERE created_at::date BETWEEN %s AND %s
    """, (week_ago, today))
    wau = cursor.fetchone()[0]

    # 3. New Registrations Today
    cursor.execute("""
        SELECT COUNT(*)
        FROM "user"
        WHERE created_at::date = %s
    """, (today,))
    new_users = cursor.fetchone()[0]

    # 4. Daily Revenue
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0)
        FROM transaction
        WHERE created_at::date = %s
    """, (today,))
    daily_revenue = float(cursor.fetchone()[0])

   # 5. Monthly Revenue (lastest 30 days of selected days)
    start_30_days_ago = today - timedelta(days=30)  

    cursor.execute("""
    SELECT COALESCE(SUM(amount), 0)
    FROM transaction
    WHERE created_at::date BETWEEN %s AND %s
    """, (start_30_days_ago, today))

    monthly_revenue = float(cursor.fetchone()[0])


    # 6. Paying User Count (paid users count in selected date)
    cursor.execute("""
    SELECT COUNT(DISTINCT user_id)
    FROM transaction
    WHERE created_at::date = %s
    """, (today,))
    paying_users = cursor.fetchone()[0]


    # 7. User Bucket Distribution
    cursor.execute("""
    SELECT 'Free' AS bucket, COUNT(*) FROM "user"
    WHERE user_id NOT IN (
        SELECT DISTINCT user_id
        FROM subscription
        WHERE is_active = TRUE AND plan_name = 'Pro')
    UNION
    SELECT 'Pro' AS bucket, COUNT(*) FROM "user"
    WHERE user_id IN (
        SELECT DISTINCT user_id
        FROM subscription
        WHERE is_active = TRUE AND plan_name = 'Pro')
    """)
    buckets = cursor.fetchall()
    user_bucket_distribution = {row[0]: row[1] for row in buckets}

    # 8. Revenue by day (bar chart)
    cursor.execute("""
    SELECT created_at::date, SUM(amount)
    FROM transaction
    WHERE created_at::date BETWEEN %s AND %s
    GROUP BY created_at::date
    ORDER BY created_at::date
    """, (start_date, end_date))
    rows = cursor.fetchall()
    revenue_by_day = {row[0].isoformat(): float(row[1]) for row in rows}

    cursor.close()
    conn.close()

    return {
        "date": today.isoformat(),
        "daily_active_users": dau,
        "weekly_active_users": wau,
        "new_registrations_today": new_users,
        "daily_revenue": daily_revenue,
        "monthly_revenue": monthly_revenue,
        "paying_user_count": paying_users,
        "user_bucket_distribution": user_bucket_distribution,
        "revenue_by_day": revenue_by_day
    }

app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")
