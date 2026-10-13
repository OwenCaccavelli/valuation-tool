import math
import pandas as pd
import valuation as v


def base(**kw):
    a = dict(growth_y1=0.05, growth_y5=0.03, ebit_margin=0.20, tax_rate=0.25, da_pct=0.04,
             capex_pct=0.05, nwc_pct=0.01, wacc=0.09, terminal_method="growth", terminal_growth=0.025, exit_multiple=10)
    a.update(kw)
    return v.Assumptions(**a)


def test_wacc_weights_sum_to_one():
    w = v.capm_wacc(1.2, 0.04, 0.05, 0.06, 0.25, 800, 200)
    assert math.isclose(w["equity_weight"] + w["debt_weight"], 1)
    assert math.isclose(w["cost_of_equity"], 0.10)
    assert math.isclose(w["wacc"], 0.8 * 0.10 + 0.2 * 0.045)


def test_dcf_bridge_adds_up():
    r = v.run_dcf(base(), 1000, debt=300, cash=100, shares=50, first_year=2026)
    assert math.isclose(r.enterprise_value, r.pv_fcf + r.pv_terminal)
    assert math.isclose(r.equity_value, r.enterprise_value - 300 + 100)
    assert math.isclose(r.per_share, r.equity_value / 50)
    assert list(r.projection["Year"]) == [2026, 2027, 2028, 2029, 2030]


def test_growth_fades_linearly():
    r = v.run_dcf(base(growth_y1=0.10, growth_y5=0.02), 1000, 0, 0, 1, 2026)
    g = r.projection["Revenue growth"].round(4).tolist()
    assert g == [0.10, 0.08, 0.06, 0.04, 0.02]


def test_higher_wacc_lowers_value():
    lo = v.run_dcf(base(wacc=0.08), 1000, 0, 0, 1, 2026).per_share
    hi = v.run_dcf(base(wacc=0.11), 1000, 0, 0, 1, 2026).per_share
    assert lo > hi


def test_exit_multiple_terminal_value():
    r = v.run_dcf(base(terminal_method="multiple", exit_multiple=12), 1000, 0, 0, 1, 2026)
    ebitda5 = r.projection["EBITDA"].iloc[-1]
    assert math.isclose(r.pv_terminal, ebitda5 * 12 / 1.09 ** 5)


def test_sensitivity_center_matches_base():
    a = base()
    s = v.sensitivity(a, 1000, 0, 0, 1, 2026)
    assert math.isclose(s.iloc[2, 2], v.run_dcf(a, 1000, 0, 0, 1, 2026).per_share)


def test_implied_prices_from_peers():
    peers = pd.DataFrame({"ev_ebitda": [8, 10, 12], "pe_forward": [15, 20, 25]})
    out = v.implied_prices(peers, {"debt": 100, "cash": 0, "shares": 10, "ebitda": 50, "forward_eps": 2,
                                   "revenue": None, "trailing_eps": None})
    mid = out.set_index("Multiple")["Mid"]
    assert math.isclose(mid["EV / EBITDA"], (10 * 50 - 100) / 10)
    assert math.isclose(mid["P / E (forward)"], 40)
