import io
import os
import sqlite3
import sys
import tempfile

DATA = tempfile.mkdtemp()
os.environ["DIARIO_DATA_DIR"] = DATA
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import db, metrics  # noqa: E402
from app.server import app  # noqa: E402
from test_core import HTML  # noqa: E402

db.init()
c = app.test_client()


def trade(**kw):
    base = {"instrument": "NDX", "side": "buy", "volume": 1, "entry_time": "2026-01-05 10:00:00", "entry_price": 100,
            "exit_time": "2026-01-05 11:00:00", "exit_price": 110, "sl": 95, "tp": 115, "profit": 10, "commission": -1}
    return c.post("/api/trades", json={**base, **kw})


def test_wilson_interval():
    lo, hi = metrics.wilson(5, 10)
    assert 23 < lo < 24 and 76 < hi < 77
    assert metrics.wilson(0, 0) == (None, None)


def test_import_per_account_and_dedupe():
    acc = c.post("/api/accounts", json={"name": "Demo", "kind": "demo", "starting_balance": 5000}).json["id"]
    data = lambda: {"file": (io.BytesIO(HTML.encode("utf-16")), "r.html"), "account_id": str(acc)}
    r1 = c.post("/api/import", data=data(), content_type="multipart/form-data").json
    r2 = c.post("/api/import", data=data(), content_type="multipart/form-data").json
    assert r1["added"] == 2 and r2["added"] == 0 and r2["duplicates"] == 2
    # el mismo ticket en otra cuenta no se considera duplicado
    r3 = c.post("/api/import", data={"file": (io.BytesIO(HTML.encode("utf-16")), "r.html"), "account_id": "1"},
                content_type="multipart/form-data").json
    assert r3["added"] == 2
    assert c.post("/api/accounts", json={"name": "Demo"}).status_code == 400  # nombre repetido


def test_balance_movements_and_account_filter():
    acc = c.post("/api/accounts", json={"name": "Fondeo", "kind": "fondeo", "starting_balance": 1000}).json["id"]
    trade(account_id=acc)
    c.post("/api/movements", json={"account_id": acc, "date": "2026-01-02", "amount": 500})
    m = c.get(f"/api/metrics?account={acc}").json
    assert m["starting_balance"] == 1000 and m["total_net"] == 9.0
    assert m["balance"] == 1509.0 and m["max_drawdown"] == 0  # depósitos no afectan al drawdown
    a = [x for x in c.get("/api/accounts").json if x["id"] == acc][0]
    assert a["balance"] == 1509.0


def test_periods_review_analysis_and_dataset():
    trade(entry_time="2026-02-02 09:00:00", exit_time="2026-02-02 10:00:00", setup="pullback", plan_grade="A")
    trade(entry_time="2026-02-03 09:30:00", exit_time="2026-02-03 10:00:00", profit=-5, mistake="sin stop", plan_grade="C")
    w = c.get("/api/periods?kind=week").json
    assert any(p["period"] == "2026-W06" for p in w)
    p = [p for p in w if p["period"] == "2026-W06"][0]
    assert p["n"] == 2 and p["plan_adherence"] == 50 and p["mistakes"] == 1
    assert c.get("/api/periods?kind=month").json[0]["period"] >= "2026-02"
    c.put("/api/reviews/2026-W06", json={"went_well": "paciencia"})
    assert [x for x in c.get("/api/periods?kind=week").json if x["period"] == "2026-W06"][0]["review"]["went_well"] == "paciencia"
    h = c.get("/api/analysis").json["by_hour"]
    assert all("reliable" in b and b["reliable"] is False for b in h)  # n < 20
    csv_text = c.get("/api/export/dataset.csv").data.decode("utf-8-sig")
    assert csv_text.splitlines()[0].startswith("trade_id,account_id,instrument")
    assert "pullback" in csv_text and "planned_rr" in csv_text


def test_multiple_shots_and_delete():
    tid = trade().json["id"]
    for _ in range(2):
        r = c.post(f"/api/trades/{tid}/shots", data={"file": (io.BytesIO(b"\x89PNG"), "a.png")}, content_type="multipart/form-data")
        assert r.status_code == 201
    shots = [t for t in c.get("/api/trades").json if t["id"] == tid][0]["shots"]
    assert len(shots) == 2
    assert c.delete(f"/api/shots/{shots[0]['id']}").status_code == 200
    assert not os.path.exists(os.path.join(db.SHOTS_DIR, shots[0]["file"]))
    assert c.post(f"/api/trades/{tid}/shots", data={"file": (io.BytesIO(b"x"), "a.exe")}, content_type="multipart/form-data").status_code == 400


def test_migration_from_v01(tmp_path):
    p = tmp_path / "old.db"
    con = sqlite3.connect(p)
    con.executescript("""CREATE TABLE settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO settings VALUES ('starting_balance','7000');
        CREATE TABLE instruments (code TEXT PRIMARY KEY, name TEXT, contract_size REAL, tick_size REAL);
        CREATE TABLE trades (id INTEGER PRIMARY KEY AUTOINCREMENT, ext_id TEXT UNIQUE, source TEXT DEFAULT 'manual',
          instrument TEXT, broker_symbol TEXT, side TEXT, volume REAL, entry_time TEXT, exit_time TEXT, entry_price REAL,
          exit_price REAL, sl REAL, tp REAL, commission REAL DEFAULT 0, swap REAL DEFAULT 0, profit REAL DEFAULT 0,
          setup TEXT DEFAULT '', emotion INTEGER, plan_grade TEXT DEFAULT '', mistake TEXT DEFAULT '',
          notes_pre TEXT DEFAULT '', notes_post TEXT DEFAULT '', screenshot TEXT DEFAULT '');
        INSERT INTO trades (instrument, side, volume, entry_time, entry_price, screenshot) VALUES ('XAU','buy',1,'2026-01-01 10:00:00',1,'old.png');""")
    con.commit()
    con.close()
    old = db.DB_PATH
    db.DB_PATH = str(p)
    try:
        db.init()
        con = db.connect()
        acc = con.execute("SELECT name, starting_balance FROM accounts").fetchone()
        assert (acc["name"], acc["starting_balance"]) == ("Principal", 7000)
        assert con.execute("SELECT account_id FROM trades").fetchone()[0] == 1
        assert con.execute("SELECT file FROM trade_shots").fetchone()[0] == "old.png"
        con.close()
    finally:
        db.DB_PATH = old


def test_hour_analysis_uses_colombia_time():
    acc = c.post("/api/accounts", json={"name": "UTCsrv", "server_mode": "utc", "starting_balance": 100}).json["id"]
    trade(account_id=acc, entry_time="2026-03-02 15:00:00", exit_time="2026-03-02 16:00:00")
    hours = [b["key"] for b in c.get(f"/api/analysis?account={acc}").json["by_hour"]]
    assert hours == ["10h"]
    assert "10h" in c.get(f"/api/metrics?account={acc}").json["by_hour"]
    row = c.get(f"/api/export/dataset.csv?account={acc}").data.decode("utf-8-sig").splitlines()[1]
    assert "2026-03-02 10:00:00" in row


def test_edit_account_and_movement():
    aid = c.post("/api/accounts", json={"name": "Cent", "starting_balance": 0}).json["id"]
    r = c.put(f"/api/accounts/{aid}", json={"name": "Cuenta cent Exness", "kind": "real", "broker": "Exness",
                                            "starting_balance": 250.5, "server_mode": "utc", "active": 1})
    assert r.status_code == 200
    a = [x for x in c.get("/api/accounts").json if x["id"] == aid][0]
    assert a["name"] == "Cuenta cent Exness" and a["starting_balance"] == 250.5 and a["broker"] == "Exness"
    assert c.put(f"/api/accounts/{aid}", json={"name": "Principal", "kind": "real"}).status_code == 400  # repetido
    assert c.put(f"/api/accounts/{aid}", json={"name": " ", "kind": "real"}).status_code == 400
    c.post("/api/movements", json={"account_id": aid, "date": "2026-02-01", "amount": 100})
    mid = c.get("/api/movements").json[0]["id"]
    assert c.put(f"/api/movements/{mid}", json={"date": "2026-02-02", "amount": 150, "note": "ajuste"}).status_code == 200
    m = [x for x in c.get("/api/movements").json if x["id"] == mid][0]
    assert (m["date"], m["amount"], m["note"]) == ("2026-02-02", 150, "ajuste")
