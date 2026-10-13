# Quick valuation

Type a ticker and get a DCF, trading comps, and a football field in seconds. Built with Python, Streamlit, pandas, Plotly, and yfinance.

By [Owen Caccavelli](https://owenc.netlify.app/#/projects).

## What it does

- **Pulls real data.** Price, share count, debt, cash, and four years of financial statements come from Yahoo Finance. The risk-free rate is the latest 10-year Treasury yield.
- **Builds a five-year DCF.** Revenue growth fades from year 1 to year 5. Unlevered free cash flow is EBIT after tax, plus D&A, minus capex and working capital. Cash flows are discounted at a CAPM-based WACC with a mid-year convention. The terminal value uses an exit multiple (default: today's EV / EBITDA) or perpetual growth, and each method cross-checks the other.
- **Runs trading comps.** Starting peer sets for common industries, editable in the app. Peer multiples (25th percentile, median, 75th percentile) are applied to the company to get a price range.
- **Pulls it together.** A football field compares the DCF, each comps multiple, the 52-week range, and analyst targets against today's price.
- **Handles edge cases.** Banks and insurers get a warning and P / E comps only, since a free cash flow DCF doesn't fit them.

Every assumption is a slider, defaults come from the company's own history, and the URL updates with the ticker (for example `?ticker=COST`), so you can share a link straight to a company.

## Project layout

| File | What's in it |
| --- | --- |
| `app.py` | The Streamlit interface |
| `valuation.py` | The finance: WACC, DCF, sensitivity tables, implied prices from comps. No network calls, so it's easy to test |
| `data.py` | Pulls and cleans Yahoo Finance data, sets starting assumptions, and holds the default peer sets |
| `tests/` | Unit tests for the valuation math |

## Run it on your computer

```bash
pip install -r requirements.txt
streamlit run app.py
```

Run the tests with `pip install pytest` and then `pytest`.

## Put it online for free (Streamlit Community Cloud)

1. Create a free GitHub account if you don't have one, then create a new public repository and upload every file in this folder (keep the `.streamlit` folder).
2. Go to share.streamlit.io, sign in with GitHub, and click **Create app**.
3. Pick your repository, set the main file to `app.py`, and choose a short custom URL.
4. Click **Deploy**. The first build takes a few minutes.

Then add the link to the Projects page on your website.

## Limits

This is a quick screen, not a full model. It ignores minority interest, preferred stock, leases, and options, and Yahoo Finance data can be incomplete or delayed. Free apps on Streamlit Community Cloud go to sleep after a while without visitors and take about 30 seconds to wake up. Not investment advice.
