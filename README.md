# FCT daily digest

Emails a once-a-day summary of Frasers Centrepoint Trust (SGX: J69U): today's price move, the move over the last five trading days, the recent closes, and the latest news. An `ALERT` prefix is added to the subject when either move is 2% or more.

Adapted from Day 36 of 100 Days of Code (Angela Yu). Prices come from Yahoo Finance via `yfinance` because Alpha Vantage does not cover SGX; news from [NewsAPI](https://newsapi.org); email via Gmail SMTP.

Runs on GitHub Actions at 6 pm Singapore time on weekdays. Secrets required: `MY_EMAIL`, `MY_PASSWORD` (Gmail app password), `NEWS_API_KEY`.

Local test without sending: set `DRY_RUN=1`.
