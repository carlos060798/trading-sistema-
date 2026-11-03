import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import importer, metrics  # noqa: E402

HTML = """<html><body><table>
<tr><th>Time</th><th>Position</th><th>Symbol</th><th>Type</th><th>Volume</th><th>Price</th><th>S / L</th><th>T / P</th><th>Time</th><th>Price</th><th>Commission</th><th>Swap</th><th>Profit</th></tr>
<tr><td>2026.01.05 10:00:00</td><td>111</td><td>XAUUSD</td><td>buy</td><td>0.10</td><td>2650.10</td><td>2645.00</td><td>0.00</td><td>2026.01.05 11:30:00</td><td>2655.40</td><td>-0.70</td><td>0.00</td><td>53.00</td></tr>
<tr><td>2026.01.06 15:00:00</td><td>112</td><td>US500</td><td>sell</td><td>1.00</td><td>5000.0</td><td>5010.0</td><td>0.00</td><td>2026.01.06 15:20:00</td><td>5008.0</td><td>-1.00</td><td>0.00</td><td>-8.00</td></tr>
<tr><td>2026.01.07 15:00:00</td><td>113</td><td>EURUSD</td><td>buy</td><td>1.00</td><td>1.1</td><td>0</td><td>0</td><td>2026.01.07 15:20:00</td><td>1.1</td><td>0</td><td>0</td><td>1 234.50</td></tr>
</table></body></html>"""


def test_mt5_html_parse_and_symbol_map():
    t = importer.parse_mt5_html(HTML)
    assert [x["ext_id"] for x in t] == ["mt5:111", "mt5:112", "mt5:113"]
    assert [x["instrument"] for x in t] == ["XAU", "SPX", None]
    assert t[0]["profit"] == 53.0 and t[0]["commission"] == -0.7 and t[0]["side"] == "buy"
    assert t[0]["entry_time"] == "2026-01-05 10:00:00"
    assert t[2]["profit"] == 1234.5


def test_utf16_decode():
    assert "XAUUSD" in importer.decode(HTML.encode("utf-16"))


def test_csv_parse():
    csv_text = "position,symbol,side,volume,entry_time,exit_time,entry_price,exit_price,sl,tp,commission,swap,profit\n" \
               "9,GOLD,sell,0.2,2026-02-01 09:00:00,2026-02-01 10:00,2700,2690,2710,0,-1.4,0,200\n"
    t = importer.parse_csv(csv_text)[0]
    assert t["instrument"] == "XAU" and t["exit_time"] == "2026-02-01 10:00:00" and t["profit"] == 200.0


def test_metrics():
    base = dict(entry_price=100, sl=95, volume=1, commission=0, swap=0, instrument="SPX", entry_time="2026-01-05 10:00:00")
    trades = [
        {**base, "profit": 10, "exit_time": "2026-01-05 11:00:00"},   # +2R (riesgo 5)
        {**base, "profit": -5, "exit_time": "2026-01-06 11:00:00"},   # -1R
        {**base, "profit": -5, "exit_time": "2026-01-07 11:00:00"},   # -1R
    ]
    m = metrics.compute(trades, {"SPX": 1.0}, 1000)
    assert m["n"] == 3 and m["total_net"] == 0
    assert m["win_rate"] == 33.3 and m["profit_factor"] == 1.0
    assert m["max_drawdown"] == 10 and m["max_loss_streak"] == 2
    assert m["expectancy"] == 0 and m["avg_r"] == 0


def test_net_includes_costs():
    assert metrics.net({"profit": 10, "commission": -1, "swap": -0.5}) == 8.5


def test_us_dst_and_local_time():
    from datetime import date
    assert metrics.us_dst(date(2026, 7, 1)) and not metrics.us_dst(date(2026, 1, 15))
    assert not metrics.us_dst(date(2026, 11, 1)) and metrics.us_dst(date(2026, 10, 31))  # DST termina el 1-nov-2026
    assert metrics.us_dst(date(2026, 3, 8)) and not metrics.us_dst(date(2026, 3, 7))
    # servidor UTC 15:00 -> Colombia 10:00
    assert metrics.to_local("2026-01-05 15:00:00", "utc").hour == 10
    # cierre NY invierno GMT+2: 17:00 servidor = 15:00 UTC = 10:00 Colombia; verano GMT+3: 17:00 = 14:00 UTC = 09:00
    assert metrics.to_local("2026-01-05 17:00:00", "ny_close").hour == 10
    assert metrics.to_local("2026-07-06 17:00:00", "ny_close").hour == 9
    assert metrics.to_local("2026-01-05 17:00:00", "fixed", 3).hour == 9


def test_twr_ignores_deposits():
    # Ejemplo del informe: 10.000 -> 11.000 (+10 %), depósito 5.000, 16.000 -> 17.600 (+10 %) => TWR 21 %
    ev = [("2026-01-10 10:00:00", "trade", 1000.0), ("2026-01-15 00:00:00", "flow", 5000.0),
          ("2026-01-20 10:00:00", "trade", 1600.0)]
    r = metrics.twr(10000, ev)
    assert r["twr_pct"] == 21.0
    assert r["profit"] == 2600.0 and r["net_deposits"] == 15000.0
    assert r["abs_gain_pct"] == round(2600 / 15000 * 100, 2)
    # retiro tras pérdida: no cuenta como pérdida
    r2 = metrics.twr(1000, [("2026-02-01 10:00:00", "trade", -100.0), ("2026-02-02 00:00:00", "flow", -400.0)])
    assert r2["twr_pct"] == -10.0


def test_twr_since_uses_balance_at_start():
    ev = [("2026-01-05 10:00:00", "trade", 1000.0), ("2026-02-05 10:00:00", "trade", 550.0)]
    r = metrics.twr(10000, ev, since="2026-02-01 00:00:00")
    assert r["twr_pct"] == 5.0 and r["profit"] == 550.0  # 550 sobre 11.000
