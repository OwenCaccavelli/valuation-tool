"""Pulls company data from Yahoo Finance (via yfinance) and turns it into tidy numbers."""
from __future__ import annotations

import math
import time
import numpy as np
import pandas as pd
import yfinance as yf


class DataError(Exception):
    pass


def _num(x):
    try:
        x = float(x)
        return None if math.isnan(x) or math.isinf(x) else x
    except (TypeError, ValueError):
        return None


def _row(df: pd.DataFrame, names: list[str]) -> pd.Series | None:
    if df is None or df.empty:
        return None
    for n in names:
        if n in df.index:
            return pd.to_numeric(df.loc[n], errors="coerce")
    return None


def _retry(fn, tries=3):
    last = None
    for i in range(tries):
        try:
            return fn()
        except Exception as e:  # yfinance raises a mix of exception types
            last = e
            time.sleep(1.2 * (i + 1))
    raise DataError(f"Yahoo Finance did not respond ({last}). Try again in a minute.")


def fetch_company(ticker: str) -> dict:
    """Everything the app needs for one company, as plain Python types."""
    t = yf.Ticker(ticker)
    info = _retry(lambda: t.info) or {}
    if not info or (_num(info.get("currentPrice")) is None and _num(info.get("regularMarketPrice")) is None):
        raise DataError(f"Couldn't find a listed company for “{ticker}”. Check the ticker and try again.")

    fin = _retry(lambda: t.financials)
    cf = _retry(lambda: t.cashflow)

    rows = {
        "Revenue": _row(fin, ["Total Revenue", "Operating Revenue"]),
        "EBITDA": _row(fin, ["EBITDA", "Normalized EBITDA"]),
        "EBIT": _row(fin, ["EBIT", "Operating Income"]),
        "Net income": _row(fin, ["Net Income", "Net Income Common Stockholders"]),
        "D&A": _row(fin, ["Reconciled Depreciation"]) if _row(fin, ["Reconciled Depreciation"]) is not None
        else _row(cf, ["Depreciation And Amortization", "Depreciation Amortization Depletion"]),
        "Capex": _row(cf, ["Capital Expenditure"]),
        "Operating cash flow": _row(cf, ["Operating Cash Flow"]),
        "Free cash flow": _row(cf, ["Free Cash Flow"]),
        "Change in working capital": _row(cf, ["Change In Working Capital"]),
        "Tax rate": _row(fin, ["Tax Rate For Calcs"]),
        "Interest expense": _row(fin, ["Interest Expense", "Interest Expense Non Operating"]),
    }
    hist = pd.DataFrame({k: v for k, v in rows.items() if v is not None})
    if hist.empty or "Revenue" not in hist:
        raise DataError("Yahoo Finance doesn't have annual financial statements for this company.")
    hist.index = pd.to_datetime(hist.index)
    hist = hist.sort_index().dropna(subset=["Revenue"]).tail(4)
    hist.index = hist.index.year
    if "Capex" in hist:
        hist["Capex"] = hist["Capex"].abs()

    price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
    shares = _num(info.get("sharesOutstanding")) or _num(info.get("impliedSharesOutstanding"))
    if not shares:
        mcap = _num(info.get("marketCap"))
        shares = mcap / price if mcap and price else None
    if not shares:
        raise DataError("Couldn't find the share count for this company.")

    return {
        "ticker": ticker.upper(),
        "name": info.get("longName") or info.get("shortName") or ticker.upper(),
        "sector": info.get("sector") or "",
        "industry": info.get("industry") or "",
        "currency": info.get("financialCurrency") or info.get("currency") or "USD",
        "price": price,
        "shares": shares,
        "market_cap": _num(info.get("marketCap")) or price * shares,
        "debt": _num(info.get("totalDebt")) or 0.0,
        "cash": _num(info.get("totalCash")) or 0.0,
        "beta": _num(info.get("beta")),
        "ebitda_ttm": _num(info.get("ebitda")),
        "revenue_ttm": _num(info.get("totalRevenue")),
        "forward_eps": _num(info.get("forwardEps")),
        "trailing_eps": _num(info.get("trailingEps")),
        "low_52w": _num(info.get("fiftyTwoWeekLow")),
        "high_52w": _num(info.get("fiftyTwoWeekHigh")),
        "target_low": _num(info.get("targetLowPrice")),
        "target_mean": _num(info.get("targetMeanPrice")),
        "target_high": _num(info.get("targetHighPrice")),
        "analysts": info.get("numberOfAnalystOpinions"),
        "summary": info.get("longBusinessSummary") or "",
        "hist": hist,
    }


def fetch_peer(ticker: str) -> dict | None:
    """Trading multiples for one peer. Returns None if Yahoo has nothing useful."""
    try:
        info = yf.Ticker(ticker).info or {}
    except Exception:
        return None
    price = _num(info.get("currentPrice")) or _num(info.get("regularMarketPrice"))
    if price is None:
        return None
    return {
        "ticker": ticker.upper(),
        "name": info.get("shortName") or ticker.upper(),
        "price": price,
        "market_cap": _num(info.get("marketCap")),
        "ev_revenue": _num(info.get("enterpriseToRevenue")),
        "ev_ebitda": _num(info.get("enterpriseToEbitda")),
        "pe_forward": _num(info.get("forwardPE")),
        "pe_trailing": _num(info.get("trailingPE")),
    }


def risk_free_rate(default: float = 0.0425) -> float:
    """Latest 10-year Treasury yield from Yahoo (^TNX), with a fallback."""
    try:
        h = yf.Ticker("^TNX").history(period="5d")
        v = float(h["Close"].dropna().iloc[-1]) / 100
        return v if 0.005 < v < 0.12 else default
    except Exception:
        return default


# Starting peer sets for common industries. Users can always edit these in the app.
PEERS = {
    "Utilities - Independent Power Producers": ["CEG", "NRG", "TLN"],
    "Utilities - Regulated Electric": ["DUK", "SO", "NEE", "AEP"],
    "Consumer Electronics": ["SONY", "DELL", "HPQ"],
    "Software - Infrastructure": ["MSFT", "ORCL", "ADBE", "CRM"],
    "Software - Application": ["CRM", "NOW", "INTU", "ADBE"],
    "Semiconductors": ["NVDA", "AMD", "AVGO", "QCOM", "INTC"],
    "Internet Content & Information": ["GOOGL", "META", "PINS", "SNAP"],
    "Internet Retail": ["AMZN", "EBAY", "ETSY", "W"],
    "Discount Stores": ["WMT", "COST", "TGT", "DG"],
    "Restaurants": ["MCD", "SBUX", "CMG", "YUM", "QSR"],
    "Auto Manufacturers": ["TSLA", "GM", "F", "TM"],
    "Oil & Gas Integrated": ["XOM", "CVX", "SHEL", "BP"],
    "Waste Management": ["WM", "RSG", "WCN", "GFL", "CWST"],
    "Rental & Leasing Services": ["URI", "HRI", "AL", "R"],
    "Banks - Diversified": ["JPM", "BAC", "C", "WFC"],
    "Insurance - Life": ["MFC", "SLF", "MET", "PRU"],
    "Railroads": ["UNP", "CSX", "NSC", "CNI", "CP"],
    "Drug Manufacturers - General": ["PFE", "MRK", "LLY", "ABBV", "JNJ"],
    "Beverages - Non-Alcoholic": ["KO", "PEP", "KDP", "MNST"],
    "Aerospace & Defense": ["LMT", "RTX", "GD", "NOC", "BA"],
}


def default_peers(company: dict) -> list[str]:
    peers = PEERS.get(company.get("industry", ""), [])
    return [p for p in peers if p != company["ticker"]][:5]


def defaults_from_history(hist: pd.DataFrame) -> dict:
    """Starting assumptions based on the last few years, clamped to sensible ranges."""
    def avg_share(col):
        if col not in hist or hist[col].isna().all():
            return None
        s = (hist[col] / hist["Revenue"]).replace([np.inf, -np.inf], np.nan).dropna().tail(3)
        return float(s.mean()) if len(s) else None

    rev = hist["Revenue"].dropna()
    if len(rev) >= 2 and rev.iloc[0] > 0:
        cagr = (rev.iloc[-1] / rev.iloc[0]) ** (1 / (len(rev) - 1)) - 1
    else:
        cagr = 0.04
    g1 = float(np.clip(cagr, -0.05, 0.30))

    ebit_m = avg_share("EBIT")
    da = avg_share("D&A")
    capex = avg_share("Capex")
    nwc = None
    if "Change in working capital" in hist:
        s = (-hist["Change in working capital"] / hist["Revenue"]).dropna().tail(3)
        nwc = float(s.mean()) if len(s) else None
    tax = None
    if "Tax rate" in hist:
        s = hist["Tax rate"].dropna().tail(3)
        tax = float(s.mean()) if len(s) else None

    def clip(v, lo, hi, d):
        return float(np.clip(v, lo, hi)) if v is not None else d

    return {
        "growth_y1": round(g1 * 200) / 200,
        "ebit_margin": round(clip(ebit_m, -0.2, 0.6, 0.15), 3),
        "da_pct": round(clip(da, 0, 0.3, 0.04), 3),
        "capex_pct": round(clip(capex, 0, 0.4, 0.05), 3),
        "nwc_pct": round(clip(nwc, -0.05, 0.05, 0.0), 3),
        "tax_rate": round(clip(tax, 0.0, 0.35, 0.21), 3),
    }
