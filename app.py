"""Quick valuation: type a ticker, get a DCF, trading comps, and a football field.

Built by Owen Caccavelli with Python, Streamlit, pandas, Plotly, and yfinance.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import data
import valuation as v

st.set_page_config(page_title="Quick valuation, by Owen Caccavelli", page_icon="📈", layout="wide")

VIOLET, SKY, EMBER = "#7B68E8", "#8FB3FF", "#F08A3E"
TEXT, MUTED, LINE = "#F7F6F3", "#A3A09A", "rgba(255,255,255,.12)"
UP, DOWN = "#5BD08A", "#FF8A7A"
SITE = "https://owenc.netlify.app/#/projects"

st.markdown(f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:opsz,wght@14..32,400..700&family=Geist+Mono:wght@400;500&display=swap');
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp p, .stApp li, .stApp label, .stApp input, .stApp button,
.stApp [data-testid="stMetricValue"], .stApp [data-testid="stMetricLabel"], .stApp [data-baseweb="tab"], .stApp .stMarkdown,
.verdict, .verdict *, .co, .co *, .hero, .hero * {{ font-family: "Inter", -apple-system, "Helvetica Neue", Arial, sans-serif !important; }}
#MainMenu, footer, header [data-testid="stToolbar"] {{ visibility: hidden; }}
.block-container {{ padding-top: 3.2rem; max-width: 1240px; }}
h1, h2, h3 {{ letter-spacing: -.03em; font-weight: 600; }}
.brand {{ display:flex; justify-content:space-between; align-items:center; gap:16px; font-size:15px; color:{MUTED}; margin-bottom:1.6rem; }}
.brand a {{ color:{MUTED}; text-decoration:none; }} .brand a:hover {{ color:{TEXT}; }}
.brand b {{ color:{TEXT}; font-weight:600; display:inline-flex; align-items:center; gap:10px; }}
.brand i {{ width:16px; height:16px; border-radius:50%; background:linear-gradient(90deg,{VIOLET},{SKY} 50%,{EMBER}); display:inline-block; }}
.hero h1 {{ font-size: clamp(40px, 5vw, 64px); line-height: 1; margin: 0 0 .5rem; }}
.hero p {{ color:{MUTED}; font-size:18px; margin:0 0 1.2rem; max-width:62ch; }}
.co {{ margin: 1.6rem 0 .4rem; }}
.co .nm {{ font-size: 34px; font-weight: 600; letter-spacing: -.03em; line-height: 1.15; color:{TEXT}; }}
.co span {{ color:{MUTED}; font-size:15px; }}
.big {{ font-family:"Geist Mono", monospace; }}
[data-testid="stMetricValue"] {{ font-family:"Inter"; letter-spacing:-.03em; font-size: clamp(22px, 2.3vw, 32px); }}
[data-testid="stMetricValue"] > div {{ overflow: visible; text-overflow: clip; white-space: nowrap; }}
.verdict {{ border:1px solid {LINE}; border-radius:18px; padding:20px 22px; background:linear-gradient(180deg,#22201E,#1A1917); }}
.verdict .num {{ font-size:44px; font-weight:600; letter-spacing:-.04em; line-height:1.05; }}
.verdict .lbl {{ color:{MUTED}; font-size:14px; margin-top:4px; }}
.up, .verdict .lbl.up {{ color:{UP}; }} .down, .verdict .lbl.down {{ color:{DOWN}; }}
.note {{ color:{MUTED}; font-size:14px; }}
.stTabs [data-baseweb="tab"] {{ font-size:16px; }}
</style>
""", unsafe_allow_html=True)


# ---------- helpers ----------
def money(x, d=1):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    a = abs(x)
    sign = "−" if x < 0 else ""
    if a >= 1e12: return f"{sign}${a/1e12:.{d}f}T"
    if a >= 1e9: return f"{sign}${a/1e9:.{d}f}B"
    if a >= 1e6: return f"{sign}${a/1e6:.{d}f}M"
    return f"{sign}${a:,.2f}"


def pct(x, d=1, sign=False):
    if x is None or (isinstance(x, float) and np.isnan(x)):
        return "n/a"
    s = f"{x*100:.{d}f}%"
    return ("+" + s) if sign and x > 0 else s


def updown(price, value):
    if not price or value is None or np.isnan(value):
        return "", "n/a"
    u = value / price - 1
    return ("up" if u >= 0 else "down"), pct(u, 0, sign=True)


def chart_layout(fig, height=360, **kw):
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)", font=dict(family="Inter", color=TEXT, size=13),
        legend=dict(orientation="h", y=-0.15, x=0, font=dict(color=MUTED)),
        xaxis=dict(gridcolor=LINE, zeroline=False), yaxis=dict(gridcolor=LINE, zeroline=False), **kw)
    return fig


@st.cache_data(ttl=3600, show_spinner=False)
def load_company(t):
    return data.fetch_company(t)


@st.cache_data(ttl=3600, show_spinner=False)
def load_peers(tickers: tuple):
    return [p for p in (data.fetch_peer(t) for t in tickers) if p]


@st.cache_data(ttl=3600, show_spinner=False)
def load_rf():
    return data.risk_free_rate()


# ---------- header ----------
st.markdown(f'<div class="brand"><b><i></i>Owen Caccavelli</b><a href="{SITE}" target="_blank">All projects</a></div>', unsafe_allow_html=True)
st.markdown('<div class="hero"><h1>Quick valuation</h1><p>Type any U.S.-listed ticker to get a DCF, trading comps, and a football field in seconds. Every assumption is adjustable in the sidebar.</p></div>', unsafe_allow_html=True)

qp = st.query_params.get("ticker", "VST")
with st.form("tk", border=False):
    c1, c2 = st.columns([4, 1])
    raw = c1.text_input("Ticker", value=qp, max_chars=10, label_visibility="collapsed", placeholder="Enter a ticker, like VST or COST")
    go_btn = c2.form_submit_button("Value it", width="stretch", type="primary")
ex = st.columns(6)
for i, sym in enumerate(["VST", "COST", "NKE", "WM", "MCD", "UBER"]):
    if ex[i].button(sym, width="stretch", key=f"ex_{sym}"):
        st.query_params["ticker"] = sym
        st.rerun()
ticker = (raw or "VST").strip().upper()
if go_btn and ticker != qp:
    st.query_params["ticker"] = ticker
    st.rerun()
ticker = st.query_params.get("ticker", ticker).upper()

with st.spinner(f"Pulling {ticker} from Yahoo Finance"):
    try:
        co = load_company(ticker)
    except data.DataError as e:
        st.error(str(e))
        st.stop()
    except Exception:
        st.error("Something went wrong pulling data. Yahoo Finance may be rate limiting, so try again in a minute.")
        st.stop()

hist = co["hist"]
is_financial = co["sector"] == "Financial Services" or "EBIT" not in hist
defaults = data.defaults_from_history(hist)
rf_live = load_rf()
current_ev = co["market_cap"] + co["debt"] - co["cash"]
ev_ebitda_now = current_ev / co["ebitda_ttm"] if co["ebitda_ttm"] and co["ebitda_ttm"] > 0 else None
k = co["ticker"]  # widget keys include the ticker, so defaults reset when it changes

# ---------- sidebar assumptions ----------
with st.sidebar:
    st.markdown(f"### Assumptions for {k}")
    st.caption("Defaults come from the last few years of reported numbers. Change anything.")
    st.markdown("**Revenue**")
    g1 = st.slider("Growth, year 1", -10.0, 40.0, defaults["growth_y1"] * 100, 0.5, format="%.1f%%", key=f"g1{k}") / 100
    g5 = st.slider("Growth, year 5", -5.0, 25.0, round((defaults["growth_y1"] + 0.025) / 2 * 200) / 2, 0.5, format="%.1f%%", key=f"g5{k}",
                   help="Growth fades in a straight line from year 1 to year 5.") / 100
    st.markdown("**Margins and reinvestment**")
    ebit_m = st.slider("EBIT margin", -20.0, 60.0, defaults["ebit_margin"] * 100, 0.5, format="%.1f%%", key=f"em{k}") / 100
    tax = st.slider("Tax rate", 0.0, 35.0, defaults["tax_rate"] * 100, 0.5, format="%.1f%%", key=f"tx{k}") / 100
    da = st.slider("D&A, % of revenue", 0.0, 30.0, defaults["da_pct"] * 100, 0.1, format="%.1f%%", key=f"da{k}") / 100
    capex = st.slider("Capex, % of revenue", 0.0, 40.0, defaults["capex_pct"] * 100, 0.1, format="%.1f%%", key=f"cx{k}") / 100
    nwc = st.slider("Working capital investment, % of revenue", -5.0, 5.0, defaults["nwc_pct"] * 100, 0.1, format="%.1f%%", key=f"nw{k}") / 100

    st.markdown("**Discount rate**")
    rf = st.slider("Risk-free rate (10-year Treasury)", 1.0, 8.0, round(rf_live * 400) / 4, 0.05, format="%.2f%%", key=f"rf{k}",
                   help="Defaults to the latest 10-year Treasury yield.") / 100
    erp = st.slider("Equity risk premium", 3.0, 8.0, 5.0, 0.25, format="%.2f%%", key=f"erp{k}") / 100
    beta = st.slider("Beta", 0.3, 2.5, float(np.clip(co["beta"] or 1.0, 0.3, 2.5)), 0.05, key=f"b{k}")
    ie = hist["Interest expense"].dropna().iloc[-1] if "Interest expense" in hist and hist["Interest expense"].notna().any() else None
    kd_default = float(np.clip(abs(ie) / co["debt"], 0.03, 0.12)) if ie and co["debt"] else 0.055
    kd = st.slider("Pre-tax cost of debt", 2.0, 12.0, round(kd_default * 400) / 4, 0.25, format="%.2f%%", key=f"kd{k}") / 100
    w = v.capm_wacc(beta, rf, erp, kd, tax, co["market_cap"], co["debt"])
    st.caption(f"Cost of equity {pct(w['cost_of_equity'])}, after-tax cost of debt {pct(w['after_tax_cost_of_debt'])}, "
               f"{pct(w['equity_weight'], 0)} equity and {pct(w['debt_weight'], 0)} debt.")
    st.metric("WACC", pct(w["wacc"], 2))

    st.markdown("**Terminal value**")
    method = st.radio("Method", ["Exit multiple", "Perpetual growth"], horizontal=True, key=f"tm{k}",
                      help="Exit multiple is the default because it anchors the end value to how the market prices the business today.")
    exit_default = float(np.clip(round((ev_ebitda_now or 10) * 2) / 2, 4, 40))
    if method == "Exit multiple":
        mult = st.slider("Exit EV / EBITDA", 3.0, 45.0, exit_default, 0.5, format="%.1fx", key=f"xm{k}",
                         help="Defaults to the company's current EV / EBITDA.")
        tg = 0.025
    else:
        tg = st.slider("Perpetual growth rate", 0.0, 5.0, 2.5, 0.25, format="%.2f%%", key=f"tg{k}") / 100
        mult = exit_default

a = v.Assumptions(growth_y1=g1, growth_y5=g5, ebit_margin=ebit_m, tax_rate=tax, da_pct=da, capex_pct=capex, nwc_pct=nwc,
                  wacc=w["wacc"], terminal_method="multiple" if method == "Exit multiple" else "growth",
                  terminal_growth=tg, exit_multiple=mult)
base_rev = float(hist["Revenue"].iloc[-1])
first_year = int(hist.index[-1]) + 1
res = v.run_dcf(a, base_rev, co["debt"], co["cash"], co["shares"], first_year)
sens = v.sensitivity(a, base_rev, co["debt"], co["cash"], co["shares"], first_year)

# ---------- peers ----------
peer_default = ", ".join(data.default_peers(co))

# ---------- company header ----------
st.markdown(f'<div class="co"><div class="nm">{co["name"]} ({k})</div><span>{co["industry"]}{", " + co["sector"] if co["sector"] else ""}</span></div>', unsafe_allow_html=True)
m = st.columns(5)
m[0].metric("Share price", f"${co['price']:,.2f}")
m[1].metric("Market cap", money(co["market_cap"]))
m[2].metric("Enterprise value", money(current_ev))
m[3].metric("EV / EBITDA (TTM)", f"{ev_ebitda_now:.1f}x" if ev_ebitda_now else "n/a")
m[4].metric("52-week range", f"\\${co['low_52w']:,.0f}–{co['high_52w']:,.0f}" if co["low_52w"] and co["high_52w"] else "n/a")

if is_financial:
    st.warning("This looks like a bank, insurer, or other financial company. A DCF on free cash flow doesn't really work for them, "
               "because debt is part of how they make money. Lean on the P / E comps instead.")

tab_sum, tab_dcf, tab_comps, tab_fin, tab_about = st.tabs(["Summary", "DCF", "Comps", "Financials", "How it works"])

# ---------- comps (computed before summary so the football field can use it) ----------
with tab_comps:
    st.markdown("#### Trading comparables")
    peer_text = st.text_input("Peers, separated by commas", value=peer_default, key=f"peers{k}",
                              placeholder="Add 3 to 6 similar companies, like CEG, NRG, TLN")
    peer_list = tuple(dict.fromkeys(p.strip().upper() for p in peer_text.split(",") if p.strip() and p.strip().upper() != k))[:8]
    peers = load_peers(peer_list) if peer_list else []
    target_row = {"ticker": k, "name": co["name"], "price": co["price"], "market_cap": co["market_cap"],
                  "ev_revenue": current_ev / co["revenue_ttm"] if co["revenue_ttm"] else None,
                  "ev_ebitda": ev_ebitda_now, "pe_forward": co["price"] / co["forward_eps"] if co["forward_eps"] and co["forward_eps"] > 0 else None,
                  "pe_trailing": co["price"] / co["trailing_eps"] if co["trailing_eps"] and co["trailing_eps"] > 0 else None}
    implied = pd.DataFrame()
    if not peers:
        st.info("Add a few peer tickers above to build the comps table." if not peer_list else "Couldn't load any of those peers. Check the tickers.")
    else:
        peer_df = pd.DataFrame(peers)
        missing = [p for p in peer_list if p not in set(peer_df["ticker"])]
        if missing:
            st.caption(f"Skipped {', '.join(missing)}: no data from Yahoo Finance.")
        table = pd.concat([pd.DataFrame([target_row]), peer_df], ignore_index=True)
        show = pd.DataFrame({
            "Company": table["name"] + " (" + table["ticker"] + ")",
            "Market cap": table["market_cap"].map(money),
            "EV / Revenue": table["ev_revenue"].map(lambda x: f"{x:.1f}x" if pd.notna(x) else "n/a"),
            "EV / EBITDA": table["ev_ebitda"].map(lambda x: f"{x:.1f}x" if pd.notna(x) and x > 0 else "n/a"),
            "P / E (forward)": table["pe_forward"].map(lambda x: f"{x:.1f}x" if pd.notna(x) and x > 0 else "n/a"),
            "P / E (trailing)": table["pe_trailing"].map(lambda x: f"{x:.1f}x" if pd.notna(x) and x > 0 else "n/a"),
        })
        st.dataframe(show.style.apply(lambda r: [f"background-color: rgba(240,138,62,.14)" if r.name == 0 else "" for _ in r], axis=1),
                     hide_index=True, width="stretch")
        st.caption(f"The first row is {k}. Peer medians below exclude it. Multiples are trailing twelve months from Yahoo Finance, "
                   "so recent acquisitions or one-off items can distort them. Multiples above 60x are left out.")
        implied = v.implied_prices(peer_df, {"debt": co["debt"], "cash": co["cash"], "shares": co["shares"],
                                             "revenue": co["revenue_ttm"], "ebitda": co["ebitda_ttm"],
                                             "forward_eps": co["forward_eps"], "trailing_eps": co["trailing_eps"]})
        if is_financial and not implied.empty:
            implied = implied[implied["Multiple"].str.startswith("P / E")].reset_index(drop=True)
        if implied.empty:
            st.info("Not enough peer data to imply a price.")
        else:
            st.markdown("#### What the peers imply for " + k)
            out = implied.copy()
            for c in ["Peer 25th pct", "Peer median", "Peer 75th pct"]:
                out[c] = out[c].map(lambda x: f"{x:.1f}x")
            for c in ["Low", "Mid", "High"]:
                out[c] = out[c].map(lambda x: f"${x:,.0f}" if x > 0 else "n/a")
            st.dataframe(out.rename(columns={"Low": "Price at 25th", "Mid": "Price at median", "High": "Price at 75th"}),
                         hide_index=True, width="stretch")
            fig = go.Figure()
            ev_e = table[["ticker", "ev_ebitda"]].dropna()
            ev_e = ev_e[ev_e["ev_ebitda"] > 0].sort_values("ev_ebitda")
            fig.add_bar(x=ev_e["ev_ebitda"], y=ev_e["ticker"], orientation="h",
                        marker_color=[EMBER if t == k else "rgba(255,255,255,.28)" for t in ev_e["ticker"]],
                        text=[f"{x:.1f}x" for x in ev_e["ev_ebitda"]], textposition="outside")
            chart_layout(fig, height=60 + 44 * len(ev_e), title=dict(text="EV / EBITDA", font=dict(size=15)))
            fig.update_xaxes(showgrid=False, showticklabels=False)
            st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

# ---------- summary ----------
with tab_sum:
    dcf_ok = not is_financial and not np.isnan(res.per_share)
    comps_mid = None
    if not implied.empty:
        pick = implied[implied["Multiple"] == "EV / EBITDA"]
        if pick.empty:
            pick = implied[implied["Multiple"] == "P / E (forward)"]
        if not pick.empty:
            comps_mid = float(pick["Mid"].iloc[0])
    vals = [x for x in [res.per_share if dcf_ok else None, comps_mid] if x and x > 0]
    blend = float(np.mean(vals)) if vals else None

    c = st.columns(3)
    for col, (lbl, val) in zip(c, [("DCF value per share", res.per_share if dcf_ok else None),
                                     ("Comps value per share (median)", comps_mid),
                                     ("Blended estimate", blend)]):
        cls, up = updown(co["price"], val)
        col.markdown(f'<div class="verdict"><div class="num">{("$" + format(val, ",.0f")) if val and val > 0 else "n/a"}</div>'
                     f'<div class="lbl">{lbl}</div><div class="lbl {cls}">{up} vs ${co["price"]:,.2f}</div></div>', unsafe_allow_html=True)

    st.markdown("#### Football field")
    bars = []
    if dcf_ok:
        inner = sens.iloc[1:4, 1:4].values.astype(float)
        bars.append(("DCF (sensitivity range)", np.nanmin(inner), np.nanmax(inner), VIOLET))
    for _, r in implied.iterrows():
        if r["Low"] > 0 and r["High"] > 0:
            bars.append((f"Comps, {r['Multiple']}", r["Low"], r["High"], SKY))
    if co["low_52w"] and co["high_52w"]:
        bars.append(("52-week trading range", co["low_52w"], co["high_52w"], "rgba(255,255,255,.35)"))
    if co["target_low"] and co["target_high"]:
        bars.append((f"Analyst targets ({co['analysts'] or '?'} analysts)", co["target_low"], co["target_high"], EMBER))
    if bars:
        bars = bars[::-1]
        fig = go.Figure()
        fig.add_bar(y=[b[0] for b in bars], x=[b[2] - b[1] for b in bars], base=[b[1] for b in bars], orientation="h",
                    marker_color=[b[3] for b in bars], text=[f"${b[1]:,.0f} to ${b[2]:,.0f}" for b in bars],
                    textposition="inside", insidetextanchor="middle", textfont=dict(color="#141312", size=13),
                    hovertemplate="%{y}: %{text}<extra></extra>")
        fig.add_vline(x=co["price"], line_color=TEXT, line_width=2, line_dash="dot",
                      annotation_text=f"Price ${co['price']:,.0f}", annotation_position="top", annotation_font_color=TEXT)
        chart_layout(fig, height=90 + 56 * len(bars))
        fig.update_xaxes(tickprefix="$")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("Ranges, not point estimates. The DCF bar covers a half-point change in WACC and one step in the terminal assumption either way.")

    if co["summary"]:
        with st.expander(f"What {co['name']} does"):
            st.write(co["summary"])

# ---------- DCF ----------
with tab_dcf:
    if is_financial:
        st.info("Shown for completeness only. For financial companies, use the comps.")
    cls, up = updown(co["price"], res.per_share)
    c = st.columns(4)
    c[0].metric("Value per share", f"${res.per_share:,.2f}" if not np.isnan(res.per_share) else "n/a", up)
    c[1].metric("Enterprise value", money(res.enterprise_value))
    c[2].metric("Equity value", money(res.equity_value))
    c[3].metric("Terminal value share of EV", pct(res.terminal_share, 0))
    for n in res.notes:
        st.caption(n)

    ufcf5 = float(res.projection["Unlevered FCF"].iloc[-1])
    ebitda5 = float(res.projection["EBITDA"].iloc[-1])
    if a.terminal_method == "multiple":
        tv = ebitda5 * a.exit_multiple
        implied_g = (tv * a.wacc - ufcf5) / (tv + ufcf5) if tv + ufcf5 else float("nan")
        st.caption(f"Cross-check: a {a.exit_multiple:.1f}x exit multiple implies the business grows about {pct(implied_g)} a year forever "
                   f"after year 5. Above 3% to 4% is usually a sign the multiple is aggressive.")
    else:
        tv = ufcf5 * (1 + a.terminal_growth) / max(a.wacc - a.terminal_growth, 0.005)
        st.caption(f"Cross-check: {pct(a.terminal_growth, 2)} perpetual growth implies an exit multiple of about "
                   f"{tv / ebitda5:.1f}x year-5 EBITDA, versus {ev_ebitda_now:.1f}x today." if ev_ebitda_now and ebitda5 > 0 else "")

    proj = res.projection.set_index("Year")
    fig = go.Figure()
    hist_fcf = (hist["EBIT"] * (1 - tax) + hist.get("D&A", 0) - hist.get("Capex", 0)) if "EBIT" in hist else None
    fig.add_bar(x=[str(y) for y in hist.index], y=hist["Revenue"] / 1e9, name="Revenue, reported", marker_color="rgba(255,255,255,.22)")
    fig.add_bar(x=[f"{y}E" for y in proj.index], y=proj["Revenue"] / 1e9, name="Revenue, projected", marker_color=VIOLET)
    if hist_fcf is not None:
        fig.add_scatter(x=[str(y) for y in hist.index], y=hist_fcf / 1e9, name="Unlevered FCF, reported", mode="lines+markers",
                        line=dict(color=MUTED, width=2))
    fig.add_scatter(x=[f"{y}E" for y in proj.index], y=proj["Unlevered FCF"] / 1e9, name="Unlevered FCF, projected",
                    mode="lines+markers", line=dict(color=EMBER, width=3))
    chart_layout(fig, height=380, barmode="group")
    fig.update_xaxes(type="category", categoryorder="array",
                     categoryarray=[str(y) for y in hist.index] + [f"{y}E" for y in proj.index])
    fig.update_yaxes(tickprefix="$", ticksuffix="B")
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})

    st.markdown("#### Projection")
    def _fmt_row(r):
        if r == "Revenue growth":
            return [pct(x) for x in proj[r]]
        if r == "Discount factor":
            return [f"{x:.3f}" for x in proj[r]]
        return [money(x) for x in proj[r]]
    t = pd.DataFrame([_fmt_row(r) for r in proj.columns], index=proj.columns, columns=[f"{c}E" for c in proj.index])
    st.dataframe(t, width="stretch", height=38 * (len(t) + 1) + 4)

    st.markdown("#### Bridge to value per share")
    bridge = pd.DataFrame({"": ["PV of free cash flow, 5 years", "PV of terminal value", "Enterprise value", "Less total debt",
                                "Plus cash", "Equity value", "Shares outstanding", "Value per share"],
                           "Amount": [money(res.pv_fcf), money(res.pv_terminal), money(res.enterprise_value), money(-co["debt"]),
                                      money(co["cash"]), money(res.equity_value), f"{co['shares']/1e6:,.1f}M",
                                      f"${res.per_share:,.2f}" if not np.isnan(res.per_share) else "n/a"]})
    st.dataframe(bridge, hide_index=True, width="stretch")

    st.markdown("#### Sensitivity")
    second = "Exit multiple" if a.terminal_method == "multiple" else "Perpetual growth"
    s = sens.copy()
    s.index = [pct(x, 2) for x in s.index]
    s.columns = [f"{c:.1f}x" for c in s.columns] if a.terminal_method == "multiple" else [pct(c, 2) for c in s.columns]
    st.caption(f"Value per share. Rows are WACC, columns are {second.lower()}. Green is above today's price.")
    st.dataframe(s.style.format("${:,.0f}").apply(
        lambda col: [f"color: {UP}" if x >= co["price"] else f"color: {DOWN}" for x in col]),
        width="stretch")

# ---------- financials ----------
with tab_fin:
    st.markdown("#### Reported history")
    h = hist.copy()
    cols = [c for c in ["Revenue", "EBITDA", "EBIT", "Net income", "D&A", "Capex", "Operating cash flow", "Free cash flow"] if c in h]
    ht = h[cols].T
    ht = ht.apply(lambda col: col.map(money))
    st.dataframe(ht, width="stretch")
    if "EBIT" in hist:
        mg = pd.DataFrame({"EBIT margin": hist["EBIT"] / hist["Revenue"]})
        if "Free cash flow" in hist:
            mg["Free cash flow margin"] = hist["Free cash flow"] / hist["Revenue"]
        fig = go.Figure()
        for c_, colr in zip(mg.columns, [EMBER, SKY]):
            fig.add_scatter(x=[str(y) for y in mg.index], y=mg[c_] * 100, name=c_, mode="lines+markers", line=dict(color=colr, width=3))
        chart_layout(fig, height=300)
        fig.update_xaxes(type="category")
        fig.update_yaxes(ticksuffix="%")
        st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})
    st.caption("Annual figures from Yahoo Finance. Capex is shown as a positive number.")

# ---------- about ----------
with tab_about:
    st.markdown(f"""
#### How it works

**Data.** Prices, share counts, debt, cash, and the last four years of financial statements come from Yahoo Finance through the
`yfinance` Python library. The risk-free rate is the latest 10-year Treasury yield.

**DCF.** Revenue grows from your year 1 rate, fading in a straight line to your year 5 rate. Unlevered free cash flow is
EBIT after tax, plus D&A, minus capex and working capital investment. Cash flows are discounted at WACC using a mid-year
convention. The terminal value uses either an exit EV / EBITDA multiple (the default, set to today's multiple) or perpetual growth.
Equity value is enterprise value minus total debt plus cash.

**WACC.** Cost of equity comes from CAPM: the risk-free rate plus beta times the equity risk premium. Cost of debt starts from
interest expense divided by total debt. Weights use market cap and total debt.

**Comps.** Peer multiples come from Yahoo Finance. The tool applies the 25th percentile, median, and 75th percentile of each
multiple to the company's own revenue, EBITDA, or earnings to get a price range.

**Limits.** This is a quick screen, not a full model. It ignores minority interest, preferred stock, leases, and options, and
Yahoo's data can be incomplete for some companies. It isn't investment advice.

Built by Owen Caccavelli with Python, Streamlit, pandas, Plotly, and yfinance. [See my other projects]({SITE}).
""")
