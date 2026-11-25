# FCT daily digest

Daily email for Frasers Centrepoint Trust (SGX: J69U): today's move, the 5-day move, recent closes, the current dividend (amount, ex/record/payable dates) and the latest news. Subject gets an `ALERT` prefix when either move is 2% or more, and an `EX-DIV` / `DIV PAID` tag on the ex-dividend and payment dates.

Prices from Yahoo Finance via `yfinance` (daily bars, topped up with intraday data when Yahoo's daily history lags), dividends scraped from the [FCT financial calendar](https://fct.frasersproperty.com/financial_information.html#calendar), news from Google News RSS, email via Gmail SMTP.

Runs on GitHub Actions at 6 pm SGT (weekdays). Secrets needed: `MY_EMAIL`, `MY_PASSWORD`.
