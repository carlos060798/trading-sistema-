"""Importadores: informe HTML de MT5 (Posiciones) y CSV genérico."""
import csv
import io
import re
from html.parser import HTMLParser

DATE_RE = re.compile(r"^\d{4}[.\-]\d{2}[.\-]\d{2} \d{2}:\d{2}(:\d{2})?$")

SYMBOL_PATTERNS = [
    ("XAU", re.compile(r"XAU|GOLD", re.I)),
    ("SPX", re.compile(r"US500|SPX|SP500|S&P|SPY500", re.I)),
    ("NDX", re.compile(r"NAS100|US100|USTEC|NDX|NASDAQ|NQ100", re.I)),
]
SIDES = {"buy": "buy", "compra": "buy", "sell": "sell", "venta": "sell"}


def map_symbol(symbol):
    for code, rx in SYMBOL_PATTERNS:
        if rx.search(symbol or ""):
            return code
    return None


def decode(raw: bytes) -> str:
    if raw[:2] in (b"\xff\xfe", b"\xfe\xff"):
        return raw.decode("utf-16")
    for enc in ("utf-8-sig", "cp1252"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("latin-1")


def num(text):
    t = (text or "").replace("\xa0", "").replace(" ", "").strip()
    if not t:
        return None
    if "," in t and "." not in t:
        t = t.replace(",", ".")
    else:
        t = t.replace(",", "")
    try:
        return float(t)
    except ValueError:
        return None


def norm_date(text):
    t = (text or "").strip().replace(".", "-", 2).replace("/", "-")
    if not DATE_RE.match(t.replace("-", ".")):
        return None
    return t if len(t) > 16 else t + ":00"


class _Rows(HTMLParser):
    def __init__(self):
        super().__init__()
        self.rows, self._row, self._cell = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self._row = []
        elif tag in ("td", "th") and self._row is not None:
            self._cell = []

    def handle_data(self, data):
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag):
        if tag in ("td", "th") and self._cell is not None and self._row is not None:
            self._row.append("".join(self._cell).strip())
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def _trade(ext_id, source, symbol, side, volume, t_in, p_in, sl, tp, t_out, p_out, comm, swap, profit):
    return {
        "ext_id": ext_id, "source": source, "broker_symbol": symbol, "instrument": map_symbol(symbol),
        "side": side, "volume": volume, "entry_time": t_in, "entry_price": p_in,
        "sl": sl or None, "tp": tp or None, "exit_time": t_out, "exit_price": p_out,
        "commission": comm or 0.0, "swap": swap or 0.0, "profit": profit or 0.0,
    }


def parse_mt5_html(text):
    """Sección 'Posiciones': hora, posición, símbolo, tipo, volumen, precio, S/L, T/P, hora, precio, comisión, swap, beneficio."""
    p = _Rows()
    p.feed(text)
    trades = []
    for c in p.rows:
        if len(c) < 13 or not norm_date(c[0]) or not norm_date(c[8]):
            continue
        side = SIDES.get(c[3].lower())
        if not side:
            continue
        trades.append(_trade(
            f"mt5:{c[1]}", "mt5", c[2], side, num(c[4]), norm_date(c[0]), num(c[5]), num(c[6]), num(c[7]),
            norm_date(c[8]), num(c[9]), num(c[10]), num(c[11]), num(c[12]),
        ))
    return trades


def parse_csv(text):
    """CSV genérico. Columnas: position,symbol,side,volume,entry_time,exit_time,entry_price,exit_price,sl,tp,commission,swap,profit"""
    sample = text[:2048]
    delim = ";" if sample.count(";") > sample.count(",") else ","
    trades = []
    for r in csv.DictReader(io.StringIO(text), delimiter=delim):
        r = {(k or "").strip().lower(): (v or "").strip() for k, v in r.items()}
        side = SIDES.get(r.get("side", "").lower())
        t_in, t_out = norm_date(r.get("entry_time")), norm_date(r.get("exit_time"))
        if not side or not t_in:
            continue
        symbol = r.get("symbol", "")
        ext = f"csv:{r['position']}" if r.get("position") else f"csv:{symbol}|{t_in}|{r.get('entry_price')}|{r.get('volume')}"
        trades.append(_trade(
            ext, "csv", symbol, side, num(r.get("volume")), t_in, num(r.get("entry_price")), num(r.get("sl")),
            num(r.get("tp")), t_out, num(r.get("exit_price")), num(r.get("commission")), num(r.get("swap")), num(r.get("profit")),
        ))
    return trades


def parse_file(filename, raw):
    text = decode(raw)
    if filename.lower().endswith((".htm", ".html")) or "<table" in text[:5000].lower():
        return parse_mt5_html(text)
    return parse_csv(text)
