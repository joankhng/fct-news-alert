import os
import sys
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone, timedelta

import requests
import yfinance as yf

STOCK_NAME = "J69U.SI"
COMPANY_NAME = "Frasers Centrepoint Trust"
DAILY_ALERT = 2.0
WEEKLY_ALERT = 2.0
NEWS_COUNT = 3
NEWS_DOMAINS = "businesstimes.com.sg,straitstimes.com,theedgesingapore.com"

NEWS_ENDPOINT = "https://newsapi.org/v2/everything"
NEWS_API_KEY = os.environ.get("NEWS_API_KEY")
MY_EMAIL = os.environ.get("MY_EMAIL")
MY_PASSWORD = os.environ.get("MY_PASSWORD")
DRY_RUN = os.environ.get("DRY_RUN") == "1"

SGT = timezone(timedelta(hours=8))


def send_email(subject: str, body: str):
    if DRY_RUN:
        sys.stdout.reconfigure(encoding="utf-8")
        print(f"Subject: {subject}\n\n{body}")
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = MY_EMAIL
    msg["To"] = MY_EMAIL
    msg.set_content(body)
    with smtplib.SMTP("smtp.gmail.com", 587) as connection:
        connection.starttls()
        connection.login(MY_EMAIL, MY_PASSWORD)
        connection.send_message(msg)


def pct(change: float) -> str:
    arrow = "🔺" if change > 0 else "🔻" if change < 0 else "▬"
    return f"{arrow}{abs(change):.2f}%"


def get_news() -> list:
    if not NEWS_API_KEY:
        return []
    for domains in (NEWS_DOMAINS, None):
        params = {
            "apiKey": NEWS_API_KEY,
            "q": COMPANY_NAME,
            "language": "en",
            "sortBy": "publishedAt",
        }
        if domains:
            params["domains"] = domains
        try:
            response = requests.get(url=NEWS_ENDPOINT, params=params, timeout=30)
            response.raise_for_status()
        except requests.RequestException as err:
            print(f"News API request failed: {err}")
            return []
        articles = response.json().get("articles", [])
        if articles:
            return articles[:NEWS_COUNT]
    return []


close = yf.Ticker(STOCK_NAME).history(period="1mo")["Close"].dropna()
if len(close) < 6:
    raise SystemExit(f"Only {len(close)} closes returned for {STOCK_NAME}; need at least 6.")

latest = float(close.iloc[-1])
previous = float(close.iloc[-2])
week_ago = float(close.iloc[-6])

daily_move = (latest - previous) / previous * 100
weekly_move = (latest - week_ago) / week_ago * 100

alerts = []
if abs(daily_move) >= DAILY_ALERT:
    alerts.append(f"one-day move of {pct(daily_move)}")
if abs(weekly_move) >= WEEKLY_ALERT:
    alerts.append(f"5-day move of {pct(weekly_move)}")

subject = f"{'ALERT ' if alerts else ''}{STOCK_NAME}: {pct(daily_move)} today, {pct(weekly_move)} over 5 days"

lines = [f"{COMPANY_NAME} ({STOCK_NAME})",
         f"Latest close S${latest:.3f} on {close.index[-1].strftime('%a %d %b %Y')}", ""]
if alerts:
    lines += ["ALERT: " + "; ".join(alerts), ""]
lines.append("Last 6 closes:")
for day, price in close.tail(6).items():
    lines.append(f"  {day.strftime('%a %d %b')}: S${price:.3f}")
lines.append("")

articles = get_news()
if articles:
    lines.append("Latest news:")
    for article in articles:
        published = datetime.fromisoformat(article["publishedAt"]).astimezone(SGT).strftime("%d %b %Y")
        lines += [f"  {published}  {article['title']}",
                  f"  {article.get('description') or ''}",
                  f"  {article['url']}", ""]
else:
    lines.append("No recent news articles found.")

send_email(subject, "\n".join(lines))
