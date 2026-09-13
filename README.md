# FCT daily digest

Daily email for Frasers Centrepoint Trust (SGX: J69U): today's move, the 5-day move, recent closes and the latest news. Subject gets an `ALERT` prefix when either move is 2% or more.

Prices from Yahoo Finance via `yfinance`, news from [NewsAPI](https://newsapi.org), email via Gmail SMTP. Runs on GitHub Actions at 6 pm Singapore time on weekdays.

Secrets: `MY_EMAIL`, `MY_PASSWORD`, `NEWS_API_KEY`. Set `DRY_RUN=1` to print instead of send.
