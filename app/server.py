"""API local (Flask). Escucha solo en 127.0.0.1."""
import os
import shutil
import sys
import uuid
from datetime import datetime

import sqlite3

from flask import Flask, Response, jsonify, request, send_from_directory

from . import db, importer, metrics

_HERE = os.path.join(sys._MEIPASS, "app") if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
STATIC = os.path.join(_HERE, "static")

app = Flask(__name__, static_folder=None)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

TRADE_FIELDS = ["account_id", "instrument", "side", "volume", "entry_time", "exit_time", "entry_price", "exit_price", "sl", "tp",
                "commission", "swap", "profit", "setup", "emotion", "plan_grade", "mistake", "notes_pre", "notes_post"]
NUMERIC = {"account_id", "volume", "entry_price", "exit_price", "sl", "tp", "commission", "swap", "profit", "emotion"}


def rows(sql, args=()):
    with db.connect() as c:
        return [dict(r) for r in c.execute(sql, args).fetchall()]


def accounts_map():
    return {a["id"]: a for a in rows("SELECT * FROM accounts")}


def sizes():
    return {r["code"]: r["contract_size"] for r in rows("SELECT code, contract_size FROM instruments")}


def clean(data):
    out = {}
    for k in TRADE_FIELDS:
        if k not in data:
            continue
        v = data[k]
        if k in NUMERIC:
            v = None if v in (None, "") else float(v)
            if k in ("emotion", "account_id") and v is not None:
                v = int(v)
        elif isinstance(v, str):
            v = v.strip() or None if k in ("exit_time",) else v.strip()
        out[k] = v
    return out


def filtered_trades():
    where, args = ["1=1"], []
    for key, col in (("instrument", "instrument"), ("setup", "setup"), ("account", "account_id")):
        if request.args.get(key):
            where.append(f"{col} = ?")
            args.append(request.args[key])
    if request.args.get("from"):
        where.append("COALESCE(exit_time, entry_time) >= ?")
        args.append(request.args["from"])
    if request.args.get("to"):
        where.append("COALESCE(exit_time, entry_time) <= ?")
        args.append(request.args["to"] + " 23:59:59")
    return rows(f"SELECT * FROM trades WHERE {' AND '.join(where)} ORDER BY COALESCE(exit_time, entry_time) DESC", args)


def with_net(trades):
    sz = sizes()
    for t in trades:
        t["net"] = metrics.net(t)
        t["r"] = metrics.r_multiple(t, sz.get(t["instrument"], 1.0))
    return trades


@app.get("/")
def index():
    return send_from_directory(STATIC, "index.html")


@app.get("/static/<path:name>")
def static_files(name):
    return send_from_directory(STATIC, name)


@app.get("/api/version")
def version():
    from . import __version__
    return jsonify(version=__version__, data_dir=db.DATA_DIR)


@app.post("/api/shutdown")
def shutdown():
    """Cierra la app (para el uso instalado, sin ventana de consola)."""
    import threading
    threading.Timer(0.4, lambda: os._exit(0)).start()
    return jsonify(ok=True)


@app.get("/api/instruments")
def get_instruments():
    return jsonify(rows("SELECT * FROM instruments ORDER BY code"))


@app.put("/api/instruments/<code>")
def put_instrument(code):
    d = request.get_json()
    with db.connect() as c:
        c.execute("UPDATE instruments SET contract_size=?, tick_size=? WHERE code=?",
                  (float(d["contract_size"]), float(d["tick_size"]), code))
    return jsonify(ok=True)


def account_ids():
    """Cuentas seleccionadas por el filtro (?account=) o todas las activas."""
    if request.args.get("account"):
        return [int(request.args["account"])]
    return [r["id"] for r in rows("SELECT id FROM accounts WHERE active=1")]


def starting_balance():
    ids = account_ids()
    q = f"SELECT COALESCE(SUM(starting_balance),0) AS s FROM accounts WHERE id IN ({','.join('?' * len(ids))})"
    return float(rows(q, ids)[0]["s"]) if ids else 0.0


def movements_total():
    ids = account_ids()
    q = f"SELECT COALESCE(SUM(amount),0) AS s FROM movements WHERE account_id IN ({','.join('?' * len(ids))})"
    return float(rows(q, ids)[0]["s"]) if ids else 0.0


@app.get("/api/accounts")
def get_accounts():
    out = rows("SELECT * FROM accounts ORDER BY id")
    for a in out:
        mv = rows("SELECT COALESCE(SUM(amount),0) AS s FROM movements WHERE account_id=?", (a["id"],))[0]["s"]
        tr = rows("SELECT * FROM trades WHERE account_id=? AND exit_time IS NOT NULL", (a["id"],))
        a["movements"] = round(mv, 2)
        a["net"] = round(sum(metrics.net(t) for t in tr), 2)
        a["balance"] = round(a["starting_balance"] + mv + a["net"], 2)
        a["n_trades"] = len(tr)
    return jsonify(out)


@app.post("/api/accounts")
def create_account():
    d = request.get_json()
    if not (d.get("name") or "").strip():
        return jsonify(error="Falta el nombre"), 400
    try:
        with db.connect() as c:
            cur = c.execute("INSERT INTO accounts (name, kind, broker, currency, starting_balance, server_mode, server_offset) VALUES (?,?,?,?,?,?,?)",
                            (d["name"].strip(), d.get("kind", "real"), d.get("broker", ""), d.get("currency", "USD"),
                             float(d.get("starting_balance") or 0), d.get("server_mode", "fixed"), float(d.get("server_offset") or 0)))
    except sqlite3.IntegrityError:
        return jsonify(error="Nombre repetido o tipo no válido"), 400
    return jsonify(id=cur.lastrowid), 201


@app.put("/api/accounts/<int:aid>")
def update_account(aid):
    d = request.get_json()
    with db.connect() as c:
        c.execute("UPDATE accounts SET name=?, kind=?, broker=?, currency=?, starting_balance=?, active=?, server_mode=?, server_offset=? WHERE id=?",
                  (d["name"].strip(), d["kind"], d.get("broker", ""), d.get("currency", "USD"),
                   float(d.get("starting_balance") or 0), int(d.get("active", 1)), d.get("server_mode", "fixed"),
                   float(d.get("server_offset") or 0), aid))
    return jsonify(ok=True)


@app.get("/api/movements")
def get_movements():
    return jsonify(rows("SELECT m.*, a.name AS account FROM movements m JOIN accounts a ON a.id=m.account_id ORDER BY date DESC"))


@app.post("/api/movements")
def create_movement():
    d = request.get_json()
    with db.connect() as c:
        c.execute("INSERT INTO movements (account_id, date, amount, note) VALUES (?,?,?,?)",
                  (int(d["account_id"]), d["date"], float(d["amount"]), d.get("note", "")))
    return jsonify(ok=True), 201


@app.delete("/api/movements/<int:mid>")
def delete_movement(mid):
    with db.connect() as c:
        c.execute("DELETE FROM movements WHERE id=?", (mid,))
    return jsonify(ok=True)


@app.get("/api/periods")
def get_periods():
    kind = "week" if request.args.get("kind") == "week" else "month"
    out = metrics.periods(metrics.enrich(filtered_trades(), sizes(), accounts_map()), kind)
    rev = {r["period"]: r for r in rows("SELECT * FROM reviews")}
    for row in out:
        row["review"] = rev.get(row["period"], {"went_well": "", "to_improve": "", "next_goal": ""})
    return jsonify(out)


@app.put("/api/reviews/<period>")
def put_review(period):
    d = request.get_json()
    with db.connect() as c:
        c.execute("INSERT OR REPLACE INTO reviews VALUES (?,?,?,?)",
                  (period, d.get("went_well", ""), d.get("to_improve", ""), d.get("next_goal", "")))
    return jsonify(ok=True)


@app.get("/api/analysis")
def analysis():
    """Estadística descriptiva por tramos. Cada tramo lleva su n y un aviso si la muestra es pequeña."""
    closed = metrics.enrich(filtered_trades(), sizes(), accounts_map())

    def entry(t):  # hora de Colombia
        return metrics._dt(t["entry_local"])

    return jsonify({
        "min_n": 20,
        "by_hour": metrics.buckets(closed, lambda t: f"{entry(t).hour:02d}h" if entry(t) else None),
        "by_weekday": metrics.buckets(closed, lambda t: metrics.WEEKDAYS[entry(t).weekday()] if entry(t) else None),
        "by_volume": metrics.buckets(closed, metrics.volume_bucket),
        "by_setup": metrics.buckets(closed, lambda t: t.get("setup") or "(sin etiqueta)"),
        "by_instrument": metrics.buckets(closed, lambda t: t["instrument"]),
    })


@app.get("/api/export/dataset.csv")
def export_dataset():
    import csv
    import io
    counts = {r["trade_id"]: r["n"] for r in rows("SELECT trade_id, COUNT(*) AS n FROM trade_shots GROUP BY trade_id")}
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=metrics.DATASET_COLUMNS)
    w.writeheader()
    w.writerows(metrics.dataset_rows(filtered_trades(), sizes(), counts, accounts_map()))
    return Response("﻿" + buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=dataset-operaciones.csv"})



@app.get("/api/trades")
def list_trades():
    trades = with_net(filtered_trades())
    shots = {}
    for sh in rows("SELECT * FROM trade_shots ORDER BY id"):
        shots.setdefault(sh["trade_id"], []).append(sh)
    for t in trades:
        t["shots"] = shots.get(t["id"], [])
    return jsonify(trades)


@app.post("/api/trades")
def create_trade():
    d = clean(request.get_json())
    for req in ("instrument", "side", "volume", "entry_time", "entry_price"):
        if d.get(req) in (None, ""):
            return jsonify(error=f"Falta el campo: {req}"), 400
    d["source"] = "manual"
    d.setdefault("account_id", rows("SELECT MIN(id) AS i FROM accounts")[0]["i"])
    cols = ",".join(d)
    with db.connect() as c:
        cur = c.execute(f"INSERT INTO trades ({cols}) VALUES ({','.join('?' * len(d))})", list(d.values()))
    return jsonify(id=cur.lastrowid), 201


@app.put("/api/trades/<int:tid>")
def update_trade(tid):
    d = clean(request.get_json())
    if not d:
        return jsonify(error="Sin cambios"), 400
    with db.connect() as c:
        c.execute(f"UPDATE trades SET {','.join(k + '=?' for k in d)} WHERE id=?", [*d.values(), tid])
    return jsonify(ok=True)


@app.delete("/api/trades/<int:tid>")
def delete_trade(tid):
    with db.connect() as c:
        c.execute("DELETE FROM trades WHERE id=?", (tid,))
    return jsonify(ok=True)


@app.post("/api/trades/<int:tid>/shots")
def upload_shot(tid):
    f = request.files.get("file")
    ext = os.path.splitext(f.filename or "")[1].lower() if f else ""
    if not f or ext not in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
        return jsonify(error="Sube una imagen png/jpg/webp/gif"), 400
    name = f"{tid}-{uuid.uuid4().hex[:8]}{ext}"
    f.save(os.path.join(db.SHOTS_DIR, name))
    with db.connect() as c:
        cur = c.execute("INSERT INTO trade_shots (trade_id, file, label) VALUES (?,?,?)", (tid, name, request.form.get("label", "")))
    return jsonify(id=cur.lastrowid, file=name), 201


@app.delete("/api/shots/<int:sid>")
def delete_shot(sid):
    with db.connect() as c:
        r = c.execute("SELECT file FROM trade_shots WHERE id=?", (sid,)).fetchone()
        c.execute("DELETE FROM trade_shots WHERE id=?", (sid,))
    if r:
        try:
            os.remove(os.path.join(db.SHOTS_DIR, r["file"]))
        except OSError:
            pass
    return jsonify(ok=True)


@app.get("/shots/<path:name>")
def shot(name):
    return send_from_directory(db.SHOTS_DIR, name)


@app.get("/api/metrics")
def get_metrics():
    m = metrics.compute(filtered_trades(), sizes(), starting_balance(), accounts_map())
    m["balance"] = round(m["starting_balance"] + movements_total() + m["total_net"], 2)
    return jsonify(m)


@app.post("/api/import")
def import_file():
    f = request.files.get("file")
    if not f:
        return jsonify(error="Falta el archivo"), 400
    acc = int(request.form.get("account_id") or rows("SELECT MIN(id) AS i FROM accounts")[0]["i"])
    parsed = importer.parse_file(f.filename or "", f.read())
    added = dup = 0
    unknown = {}
    with db.connect() as c:
        for t in parsed:
            if not t["instrument"]:
                unknown[t["broker_symbol"]] = unknown.get(t["broker_symbol"], 0) + 1
                continue
            if t["volume"] is None or t["entry_price"] is None:
                continue
            t["ext_id"] = f"{acc}:{t['ext_id']}"  # el mismo ticket puede repetirse entre cuentas
            t["account_id"] = acc
            cols = list(t)
            cur = c.execute(f"INSERT OR IGNORE INTO trades ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                            [t[k] for k in cols])
            if cur.rowcount:
                added += 1
            else:
                dup += 1
    return jsonify(read=len(parsed), added=added, duplicates=dup, skipped_symbols=unknown)


@app.get("/api/export")
def export_all():
    return jsonify(instruments=rows("SELECT * FROM instruments"), accounts=rows("SELECT * FROM accounts"),
                   movements=rows("SELECT * FROM movements"), reviews=rows("SELECT * FROM reviews"),
                   shots=rows("SELECT * FROM trade_shots"),
                   trades=with_net(rows("SELECT * FROM trades ORDER BY id")))


@app.post("/api/backup")
def backup():
    os.makedirs(db.BACKUP_DIR, exist_ok=True)
    dest = os.path.join(db.BACKUP_DIR, f"diario-{datetime.now():%Y%m%d-%H%M%S}.db")
    with db.connect() as src:
        out = sqlite3.connect(dest)
        src.backup(out)
        out.close()
    return jsonify(path=dest)
