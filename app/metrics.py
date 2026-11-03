"""Cálculo de métricas. Función pura sobre una lista de operaciones (dicts)."""
from collections import defaultdict
from datetime import date, datetime, timedelta

LOCAL_UTC_OFFSET = -5  # Colombia (America/Bogota): UTC-5 todo el año, sin horario de verano


def _nth_sunday(year, month, n):
    d = date(year, month, 1)
    first = d + timedelta(days=(6 - d.weekday()) % 7)
    return first + timedelta(weeks=n - 1)


def us_dst(d):
    """Horario de verano de EE.UU. (2.º domingo de marzo – 1.er domingo de noviembre), a nivel de día."""
    return _nth_sunday(d.year, 3, 2) <= d < _nth_sunday(d.year, 11, 1)


def server_offset(dt, mode, offset):
    """Horas del servidor respecto a UTC. 'utc'=0; 'ny_close'=+2 invierno / +3 verano de EE.UU.; 'fixed'=offset."""
    if mode == "utc":
        return 0.0
    if mode == "ny_close":
        return 3.0 if us_dst(dt.date()) else 2.0
    return float(offset or 0)


def to_local(server_time, mode="fixed", offset=0):
    """Hora del servidor (texto ISO sin zona) -> datetime en hora de Colombia."""
    dt = _dt(server_time)
    if dt is None:
        return None
    return dt - timedelta(hours=server_offset(dt, mode, offset)) + timedelta(hours=LOCAL_UTC_OFFSET)


def _local_for(t, accounts):
    a = (accounts or {}).get(t.get("account_id")) or {}
    return to_local(t["entry_time"], a.get("server_mode", "fixed"), a.get("server_offset", 0))


def net(t):
    return round((t["profit"] or 0) + (t["commission"] or 0) + (t["swap"] or 0), 2)


def r_multiple(t, contract_size):
    """R = neto / riesgo inicial en dinero. Solo si hay S/L. Usa el S/L guardado (en MT5 es el final, no el inicial)."""
    if not t.get("sl") or not t.get("entry_price") or not t.get("volume"):
        return None
    risk = abs(t["entry_price"] - t["sl"]) * t["volume"] * contract_size
    return round(net(t) / risk, 2) if risk > 0 else None


def _group(rows, keyfn):
    g = defaultdict(lambda: {"n": 0, "net": 0.0, "wins": 0})
    for t in rows:
        k = keyfn(t)
        if k is None:
            continue
        g[k]["n"] += 1
        g[k]["net"] = round(g[k]["net"] + t["net"], 2)
        g[k]["wins"] += t["net"] > 0
    return {k: v for k, v in sorted(g.items(), key=lambda kv: str(kv[0]))}


def _dt(s):
    try:
        return datetime.fromisoformat(s)
    except (TypeError, ValueError):
        return None


def compute(trades, sizes, starting_balance, accounts=None):
    closed = [dict(t) for t in trades if t.get("exit_time")]
    closed.sort(key=lambda t: t["exit_time"])
    for t in closed:
        t["net"] = net(t)
        t["r"] = r_multiple(t, sizes.get(t["instrument"], 1.0))
    n = len(closed)
    wins = [t["net"] for t in closed if t["net"] > 0]
    losses = [t["net"] for t in closed if t["net"] < 0]
    gross_win, gross_loss = sum(wins), -sum(losses)
    wr = len(wins) / n if n else 0
    avg_win = gross_win / len(wins) if wins else 0
    avg_loss = gross_loss / len(losses) if losses else 0

    equity, peak, max_dd, max_dd_pct, curve = starting_balance, starting_balance, 0.0, 0.0, []
    for t in closed:
        equity += t["net"]
        peak = max(peak, equity)
        dd = peak - equity
        max_dd = max(max_dd, dd)
        max_dd_pct = max(max_dd_pct, dd / peak * 100 if peak else 0)
        curve.append({"t": t["exit_time"], "equity": round(equity, 2)})

    best_w = best_l = cur_w = cur_l = 0
    for t in closed:
        cur_w, cur_l = (cur_w + 1, 0) if t["net"] > 0 else (0, cur_l + 1) if t["net"] < 0 else (0, 0)
        best_w, best_l = max(best_w, cur_w), max(best_l, cur_l)

    rs = [t["r"] for t in closed if t["r"] is not None]
    hold = [(_dt(t["exit_time"]) - _dt(t["entry_time"])).total_seconds() / 60
            for t in closed if _dt(t["exit_time"]) and _dt(t["entry_time"])]
    daily = _group(closed, lambda t: t["exit_time"][:10])
    for t in closed:
        t["_wd"] = (_dt(t["exit_time"]).weekday() if _dt(t["exit_time"]) else None)

    return {
        "n": n,
        "open": len(trades) - n,
        "total_net": round(sum(t["net"] for t in closed), 2),
        "win_rate": round(wr * 100, 1),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
        "expectancy": round(wr * avg_win - (1 - wr) * avg_loss, 2) if n else 0,
        "avg_win": round(avg_win, 2),
        "avg_loss": round(-avg_loss, 2),
        "payoff": round(avg_win / avg_loss, 2) if avg_loss else None,
        "best": max((t["net"] for t in closed), default=0),
        "worst": min((t["net"] for t in closed), default=0),
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_pct": round(max_dd_pct, 2),
        "max_win_streak": best_w,
        "max_loss_streak": best_l,
        "avg_r": round(sum(rs) / len(rs), 2) if rs else None,
        "expectancy_r": round(sum(rs) / len(rs), 2) if rs else None,
        "n_with_r": len(rs),
        "avg_hold_min": round(sum(hold) / len(hold), 1) if hold else None,
        "equity": curve,
        "starting_balance": starting_balance,
        "daily": {k: v["net"] for k, v in daily.items()},
        "by_instrument": _group(closed, lambda t: t["instrument"]),
        "by_setup": _group(closed, lambda t: t.get("setup") or "(sin etiqueta)"),
        "by_weekday": _group(closed, lambda t: ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"][t["_wd"]] if t["_wd"] is not None else None),
        "by_hour": _group(closed, lambda t: f"{_local_for(t, accounts).hour:02d}h" if _local_for(t, accounts) else None),
        "by_mistake": _group(closed, lambda t: t.get("mistake") or None),
    }


# ---------- resúmenes por periodo, tramos y dataset ----------
WEEKDAYS = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]


def enrich(trades, sizes, accounts=None):
    """Añade net, r y entry_local (hora de Colombia) a las operaciones cerradas, ordenadas por salida."""
    out = []
    for t in trades:
        if not t.get("exit_time"):
            continue
        t = dict(t)
        loc = _local_for(t, accounts)
        t["entry_local"] = loc.strftime("%Y-%m-%d %H:%M:%S") if loc else None
        t["net"] = net(t)
        t["r"] = r_multiple(t, sizes.get(t["instrument"], 1.0))
        out.append(t)
    return sorted(out, key=lambda t: t["exit_time"])


def wilson(wins, n, z=1.96):
    """Intervalo de Wilson al 95 % para una proporción (win rate). Devuelve (bajo, alto) en %."""
    if n == 0:
        return None, None
    p = wins / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / d
    return round((centre - half) * 100, 1), round((centre + half) * 100, 1)


def summary(closed):
    n = len(closed)
    wins = [t["net"] for t in closed if t["net"] > 0]
    losses = [t["net"] for t in closed if t["net"] < 0]
    rs = [t["r"] for t in closed if t["r"] is not None]
    graded = [t for t in closed if t.get("plan_grade")]
    emo = [t["emotion"] for t in closed if t.get("emotion")]
    gw, gl = sum(wins), -sum(losses)
    wr = len(wins) / n if n else 0
    aw = gw / len(wins) if wins else 0
    al = gl / len(losses) if losses else 0
    lo, hi = wilson(len(wins), n)
    return {
        "n": n,
        "net": round(sum(t["net"] for t in closed), 2),
        "win_rate": round(wr * 100, 1),
        "win_rate_ci": [lo, hi],
        "profit_factor": round(gw / gl, 2) if gl else None,
        "expectancy": round(wr * aw - (1 - wr) * al, 2) if n else 0,
        "avg_r": round(sum(rs) / len(rs), 2) if rs else None,
        "plan_adherence": round(sum(t["plan_grade"] in ("A", "B") for t in graded) / len(graded) * 100) if graded else None,
        "graded": len(graded),
        "mistakes": sum(1 for t in closed if t.get("mistake")),
        "avg_emotion": round(sum(emo) / len(emo), 1) if emo else None,
    }


def periods(closed, kind):
    """kind: 'week' (semana ISO) o 'month'. Más reciente primero."""
    groups = {}
    for t in closed:
        d = _dt(t["exit_time"])
        if not d:
            continue
        if kind == "week":
            y, w, _ = d.isocalendar()
            key = f"{y}-W{w:02d}"
            label = datetime.fromisocalendar(y, w, 1).strftime("%d/%m/%Y")
        else:
            key, label = d.strftime("%Y-%m"), d.strftime("%Y-%m")
        groups.setdefault(key, {"label": label, "trades": []})["trades"].append(t)
    out = []
    for key in sorted(groups, reverse=True):
        row = summary(groups[key]["trades"])
        row.update(period=key, label=groups[key]["label"])
        out.append(row)
    for i, row in enumerate(out):  # variación vs periodo anterior
        prev = out[i + 1] if i + 1 < len(out) else None
        row["vs_prev_net"] = round(row["net"] - prev["net"], 2) if prev else None
    return out


def buckets(closed, keyfn, min_n=20):
    """Estadística por tramo (hora, día, volumen…). `reliable` = muestra suficiente (n >= min_n)."""
    g = {}
    for t in closed:
        k = keyfn(t)
        if k is not None:
            g.setdefault(k, []).append(t)
    out = []
    for k in sorted(g, key=str):
        s = summary(g[k])
        s.update(key=k, reliable=s["n"] >= min_n)
        out.append(s)
    return out


def volume_bucket(t):
    v = t.get("volume") or 0
    for hi, name in ((0.1, "≤0.10"), (0.5, "0.11–0.50"), (1, "0.51–1.00"), (5, "1.01–5.00")):
        if v <= hi:
            return name
    return ">5.00"


DATASET_COLUMNS = ["trade_id", "account_id", "instrument", "side", "volume", "entry_time", "entry_local", "exit_time", "hold_min",
                   "entry_hour", "weekday", "month", "risk_points", "planned_rr", "net", "r", "win", "setup",
                   "emotion", "plan_grade", "mistake", "n_shots", "notes_pre", "notes_post"]


def dataset_rows(trades, sizes, shot_counts, accounts=None):
    """Una fila por operación cerrada con features y etiquetas limpias (para análisis/ML futuros)."""
    rows = []
    for t in enrich(trades, sizes, accounts):
        i, o = _dt(t["entry_time"]), _dt(t["exit_time"])
        loc = _dt(t["entry_local"])
        risk = abs(t["entry_price"] - t["sl"]) if t.get("sl") else None
        rr = None
        if risk and t.get("tp"):
            rr = round(abs(t["tp"] - t["entry_price"]) / risk, 2)
        rows.append({
            "trade_id": t["id"], "account_id": t["account_id"], "instrument": t["instrument"], "side": t["side"],
            "volume": t["volume"], "entry_time": t["entry_time"], "entry_local": t["entry_local"], "exit_time": t["exit_time"],
            "hold_min": round((o - i).total_seconds() / 60, 1) if i and o else None,
            "entry_hour": loc.hour if loc else None, "weekday": WEEKDAYS[loc.weekday()] if loc else None,
            "month": loc.strftime("%Y-%m") if loc else None, "risk_points": round(risk, 5) if risk else None,
            "planned_rr": rr, "net": t["net"], "r": t["r"], "win": int(t["net"] > 0), "setup": t.get("setup") or "",
            "emotion": t.get("emotion"), "plan_grade": t.get("plan_grade") or "", "mistake": t.get("mistake") or "",
            "n_shots": shot_counts.get(t["id"], 0),
            "notes_pre": (t.get("notes_pre") or "").replace("\n", " "), "notes_post": (t.get("notes_post") or "").replace("\n", " "),
        })
    return rows


def twr(start, events, since=None, until=None):
    """Retorno ponderado en el tiempo (TWR) encadenado entre flujos de caja.

    events: (clave_ISO, 'trade'|'flow', importe). Un flujo (depósito/retiro) cierra el subperiodo:
    R = valor_antes_del_flujo / valor_tras_el_flujo_anterior - 1; TWR = producto(1+R) - 1.
    since/until acotan el periodo medido (el valor inicial incluye lo anterior a `since`).
    Ganancia absoluta = beneficio / (capital al inicio + depósitos netos del periodo).
    """
    v, prev, factor = float(start), float(start), 1.0
    started = since is None
    base, flows, profit, curve = v, 0.0, 0.0, []
    for key, kind, amt in sorted(events, key=lambda e: e[0]):
        if until and key > until:
            break
        if not started and key >= since:
            started, prev, base = True, v, v
        if kind == "trade":
            v += amt
            if started:
                profit += amt
                curve.append({"t": key, "twr": round(((factor * v / prev) if prev > 0 else factor) * 100 - 100, 2)})
        else:
            if started and prev > 0:
                factor *= v / prev
            v += amt
            prev = v
            if started:
                flows += amt
    if not started:
        base, prev = v, v
    final = factor * (v / prev) if prev > 0 else factor
    capital = base + flows
    return {
        "twr_pct": round(final * 100 - 100, 2),
        "abs_gain_pct": round(profit / capital * 100, 2) if capital > 0 else None,
        "profit": round(profit, 2),
        "net_deposits": round(base + flows, 2),
        "curve": curve,
    }
