import os
import sys
import smtplib
from email.message import EmailMessage
from datetime import datetime, timezone, timedelta

import re
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from urllib.parse import quote_plus

import requests
import yfinance as yf
from bs4 import BeautifulSoup

STOCK_NAME = "J69U.SI"
COMPANY_NAME = "Frasers Centrepoint Trust"
DAILY_ALERT = 2.0
WEEKLY_ALERT = 2.0
NEWS_COUNT = 3
NEWS_DAYS = 3
DIVIDEND_LOOKAHEAD_DAYS = 45

GOOGLE_NEWS_RSS = "https://news.google.com/rss/search?q={query}&hl=en-SG&gl=SG&ceid=SG:en"
FCT_CALENDAR_URL = "https://fct.frasersproperty.com/financial_information.html"
BROWSER_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                                 "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"}
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
    """Latest articles from Google News RSS: list of dicts with title, source, url, published."""
    query = quote_plus(f'"{COMPANY_NAME}" when:{NEWS_DAYS}d')
    try:
        response = requests.get(GOOGLE_NEWS_RSS.format(query=query), headers=BROWSER_HEADERS, timeout=30)
        response.raise_for_status()
        root = ET.fromstring(response.content)
    except (requests.RequestException, ET.ParseError) as err:
        print(f"Google News request failed: {err}")
        return []
    cutoff = datetime.now(SGT) - timedelta(days=NEWS_DAYS)
    articles = []
    for item in root.iter("item"):
        title = item.findtext("title", "").strip()
        source = item.findtext("source", "").strip()
        if source and title.endswith(f" - {source}"):
            title = title[: -len(f" - {source}")]
        try:
            published = parsedate_to_datetime(item.findtext("pubDate", "")).astimezone(SGT)
        except (TypeError, ValueError):
            continue
        if published < cutoff:
            continue
        articles.append({"title": title, "source": source,
                         "url": item.findtext("link", "").strip(), "published": published})
    articles.sort(key=lambda a: a["published"], reverse=True)
    return articles[:NEWS_COUNT]


DATE_RE = r"\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}"
DIVIDEND_RE = re.compile(
    rf"({DATE_RE})\s*Ex-?\s*Dividend\s*DIVIDEND\s*:?\s*SGD\s*([\d.]+)"
    rf"(?:.{{0,200}}?Record\s+Date\s*:?\s*({DATE_RE}))?"
    rf"(?:.{{0,200}}?Payable\s+Date\s*:?\s*({DATE_RE}))?",
    re.IGNORECASE | re.DOTALL,
)


def parse_date(text):
    if not text:
        return None
    text = " ".join(text.split())
    for fmt in ("%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    return None


def get_dividends() -> list:
    """Dividend events scraped from the FCT financial calendar page."""
    try:
        response = requests.get(FCT_CALENDAR_URL, headers=BROWSER_HEADERS, timeout=30)
        response.raise_for_status()
    except requests.RequestException as err:
        print(f"FCT calendar request failed: {err}")
        return []
    text = BeautifulSoup(response.text, "html.parser").get_text(" ")
    text = " ".join(text.split())
    dividends = []
    for m in DIVIDEND_RE.finditer(text):
        ex_date = parse_date(m.group(1))
        if not ex_date:
            continue
        dividends.append({"amount": float(m.group(2)), "ex": ex_date,
                          "record": parse_date(m.group(3)), "payable": parse_date(m.group(4))})
    if not dividends:
        print("No dividend rows found on the FCT calendar page; the page layout may have changed.")
    return dividends


def pick_dividend(dividends: list, today):
    """The dividend still in progress (not yet paid) or most recently announced."""
    def last_date(d):
        return d["payable"] or d["record"] or d["ex"]
    pending = [d for d in dividends if last_date(d) >= today]
    if pending:
        return min(pending, key=lambda d: d["ex"])
    recent = [d for d in dividends if (today - last_date(d)).days <= DIVIDEND_LOOKAHEAD_DAYS]
    return max(recent, key=lambda d: d["ex"]) if recent else None


def when(day, today) -> str:
    delta = (day - today).days
    if delta == 0:
        return "TODAY"
    if delta == 1:
        return "tomorrow"
    if delta > 1:
        return f"in {delta} days"
    return f"{-delta} days ago"


def get_closes():
    """Daily closes, topped up with intraday data when Yahoo's daily bars lag behind."""
    ticker = yf.Ticker(STOCK_NAME)
    daily = ticker.history(period="1mo", interval="1d")["Close"].dropna()
    closes = {ts.date(): float(p) for ts, p in daily.items()}
    try:
        intraday = ticker.history(period="5d", interval="30m")["Close"].dropna()
        for ts, p in intraday.items():
            day = ts.tz_convert(SGT).date() if ts.tzinfo else ts.date()
            closes[day] = float(p)  # later bars overwrite earlier ones -> last trade of the day
    except Exception as err:
        print(f"Intraday top-up failed: {err}")
    return sorted(closes.items())


def trading_days_between(start, end) -> int:
    """Weekdays after start up to and including end."""
    count, day = 0, start
    while day < end:
        day += timedelta(days=1)
        if day.weekday() < 5:
            count += 1
    return count


close = get_closes()
if len(close) < 6:
    raise SystemExit(f"Only {len(close)} closes returned for {STOCK_NAME}; need at least 6.")

today = datetime.now(SGT).date()
latest_day, latest = close[-1]
previous = close[-2][1]
week_ago = close[-6][1]

daily_move = (latest - previous) / previous * 100
weekly_move = (latest - week_ago) / week_ago * 100

alerts = []
if abs(daily_move) >= DAILY_ALERT:
    alerts.append(f"one-day move of {pct(daily_move)}")
if abs(weekly_move) >= WEEKLY_ALERT:
    alerts.append(f"5-day move of {pct(weekly_move)}")

dividend = pick_dividend(get_dividends(), today)
subject_tags = []
if dividend and dividend["ex"] == today:
    subject_tags.append(f"EX-DIV S${dividend['amount']:.5f}")
if dividend and dividend["payable"] == today:
    subject_tags.append(f"DIV PAID S${dividend['amount']:.5f}")

subject = (f"{'ALERT ' if alerts else ''}{STOCK_NAME}: {pct(daily_move)} today, {pct(weekly_move)} over 5 days"
           + "".join(f" | {tag}" for tag in subject_tags))

lines = [f"{COMPANY_NAME} ({STOCK_NAME})",
         f"Latest close S${latest:.3f} on {latest_day.strftime('%a %d %b %Y')}", ""]
if trading_days_between(latest_day, today) > 1:
    lines += [f"⚠️ Price data may be stale: latest close is {latest_day.strftime('%a %d %b')}, "
              f"but today is {today.strftime('%a %d %b')}.", ""]
if alerts:
    lines += ["ALERT: " + "; ".join(alerts), ""]
lines.append("Last 6 closes:")
for day, price in close[-6:]:
    lines.append(f"  {day.strftime('%a %d %b')}: S${price:.3f}")
lines.append("")

lines.append("Dividend:")
if dividend:
    if dividend["payable"] == today:
        lines.append(f"  💰 Dividend of S${dividend['amount']:.5f} per unit is paid TODAY")
    else:
        lines.append(f"  S${dividend['amount']:.5f} per unit")
    for label, key in (("Ex-dividend", "ex"), ("Record date", "record"), ("Payable", "payable")):
        if dividend[key]:
            lines.append(f"  {label}: {dividend[key].strftime('%a %d %b %Y')} ({when(dividend[key], today)})")
else:
    lines.append(f"  No upcoming dividend found. Check {FCT_CALENDAR_URL}#calendar")
lines.append("")

articles = get_news()
if articles:
    lines.append("Latest news:")
    for article in articles:
        lines += [f"  {article['published'].strftime('%d %b %Y')}  {article['title']}"
                  + (f" ({article['source']})" if article["source"] else ""),
                  f"  {article['url']}", ""]
else:
    lines.append("No recent news articles found.")

send_email(subject, "\n".join(lines))
