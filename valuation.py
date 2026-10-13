"""Valuation math: WACC, a five-year unlevered DCF, sensitivity tables, and trading comps.

Everything here is plain Python and pandas with no network calls, so it is easy to test.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import numpy as np
import pandas as pd


@dataclass
class Assumptions:
    growth_y1: float          # revenue growth in year 1, as a decimal
    growth_y5: float          # revenue growth in year 5 (growth fades linearly between the two)
    ebit_margin: float        # EBIT as a share of revenue
    tax_rate: float
    da_pct: float             # depreciation and amortization, share of revenue
    capex_pct: float          # capital expenditure, share of revenue
    nwc_pct: float            # investment in working capital, share of revenue
    wacc: float
    terminal_method: str = "growth"   # "growth" or "multiple"
    terminal_growth: float = 0.025
    exit_multiple: float = 10.0       # EV / EBITDA applied to year 5


@dataclass
class DCFResult:
    projection: pd.DataFrame
    pv_fcf: float
    pv_terminal: float
    enterprise_value: float
    equity_value: float
    per_share: float
    terminal_share: float
    notes: list[str] = field(default_factory=list)


def capm_wacc(beta: float, risk_free: float, erp: float, pre_tax_cost_of_debt: float,
              tax_rate: float, equity_value: float, debt: float) -> dict:
    """Weighted average cost of capital using CAPM for the cost of equity."""
    cost_of_equity = risk_free + beta * erp
    after_tax_debt = pre_tax_cost_of_debt * (1 - tax_rate)
    total = max(equity_value + debt, 1.0)
    we, wd = equity_value / total, debt / total
    return {
        "cost_of_equity": cost_of_equity,
        "after_tax_cost_of_debt": after_tax_debt,
        "equity_weight": we,
        "debt_weight": wd,
        "wacc": we * cost_of_equity + wd * after_tax_debt,
    }


def run_dcf(a: Assumptions, base_revenue: float, debt: float, cash: float, shares: float,
            first_year: int) -> DCFResult:
    """Five-year unlevered DCF with a mid-year discounting convention."""
    years, revenue, growth = [], [], []
    rev = base_revenue
    for t in range(1, 6):
        g = a.growth_y1 + (a.growth_y5 - a.growth_y1) * (t - 1) / 4
        rev = rev * (1 + g)
        years.append(first_year + t - 1)
        revenue.append(rev)
        growth.append(g)
    revenue = np.array(revenue)
    ebit = revenue * a.ebit_margin
    nopat = ebit * (1 - a.tax_rate)
    da = revenue * a.da_pct
    capex = revenue * a.capex_pct
    nwc = revenue * a.nwc_pct
    ufcf = nopat + da - capex - nwc
    ebitda = ebit + da
    t_mid = np.arange(1, 6) - 0.5
    discount = 1 / (1 + a.wacc) ** t_mid
    pv = ufcf * discount

    notes = []
    if a.terminal_method == "multiple":
        terminal = ebitda[-1] * a.exit_multiple
    else:
        spread = a.wacc - a.terminal_growth
        if spread < 0.005:
            notes.append("The discount rate is too close to terminal growth, so the spread was floored at 0.5%.")
            spread = 0.005
        terminal = ufcf[-1] * (1 + a.terminal_growth) / spread
    pv_terminal = terminal / (1 + a.wacc) ** 5

    ev = pv.sum() + pv_terminal
    equity = ev - debt + cash
    per_share = equity / shares if shares else float("nan")

    proj = pd.DataFrame({
        "Year": years, "Revenue growth": growth, "Revenue": revenue, "EBITDA": ebitda, "EBIT": ebit,
        "NOPAT": nopat, "D&A": da, "Capex": capex, "Working capital": nwc,
        "Unlevered FCF": ufcf, "Discount factor": discount, "PV of FCF": pv,
    })
    return DCFResult(proj, float(pv.sum()), float(pv_terminal), float(ev), float(equity),
                     float(per_share), float(pv_terminal / ev) if ev else float("nan"), notes)


def sensitivity(a: Assumptions, base_revenue: float, debt: float, cash: float, shares: float,
                first_year: int, wacc_steps=(-0.01, -0.005, 0, 0.005, 0.01),
                second_steps=None) -> pd.DataFrame:
    """Value per share across discount rates and terminal growth (or exit multiples)."""
    if a.terminal_method == "multiple":
        second_steps = second_steps or (-2, -1, 0, 1, 2)
        cols = [a.exit_multiple + s for s in second_steps]
    else:
        second_steps = second_steps or (-0.01, -0.005, 0, 0.005, 0.01)
        cols = [a.terminal_growth + s for s in second_steps]
    rows = [a.wacc + s for s in wacc_steps]
    out = pd.DataFrame(index=rows, columns=cols, dtype=float)
    for w in rows:
        for c in cols:
            kw = dict(a.__dict__)
            kw["wacc"] = w
            if a.terminal_method == "multiple":
                kw["exit_multiple"] = c
            else:
                kw["terminal_growth"] = c
            out.loc[w, c] = run_dcf(Assumptions(**kw), base_revenue, debt, cash, shares, first_year).per_share
    return out


MULTIPLES = {
    "EV / Revenue": "ev_revenue",
    "EV / EBITDA": "ev_ebitda",
    "P / E (forward)": "pe_forward",
    "P / E (trailing)": "pe_trailing",
}


def implied_prices(peers: pd.DataFrame, target: dict) -> pd.DataFrame:
    """Apply peer multiples (25th percentile, median, 75th percentile) to the target company."""
    rows = []
    debt, cash, shares = target["debt"], target["cash"], target["shares"]
    for label, col in MULTIPLES.items():
        vals = pd.to_numeric(peers.get(col), errors="coerce").dropna() if col in peers else pd.Series(dtype=float)
        vals = vals[(vals > 0) & (vals < 60)]
        if len(vals) == 0:
            continue
        q = vals.quantile([0.25, 0.5, 0.75]).values
        if col == "ev_revenue":
            metric = target.get("revenue")
            fn = (lambda m: (m * metric - debt + cash) / shares) if metric else None
        elif col == "ev_ebitda":
            metric = target.get("ebitda")
            fn = (lambda m: (m * metric - debt + cash) / shares) if metric and metric > 0 else None
        elif col == "pe_forward":
            metric = target.get("forward_eps")
            fn = (lambda m: m * metric) if metric and metric > 0 else None
        else:
            metric = target.get("trailing_eps")
            fn = (lambda m: m * metric) if metric and metric > 0 else None
        if fn is None:
            continue
        rows.append({"Multiple": label, "Peer 25th pct": q[0], "Peer median": q[1], "Peer 75th pct": q[2],
                     "Low": fn(q[0]), "Mid": fn(q[1]), "High": fn(q[2]), "Peers used": int(len(vals))})
    return pd.DataFrame(rows)
