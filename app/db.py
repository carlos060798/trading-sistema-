"""Acceso a SQLite y rutas de datos.

Datos: DIARIO_DATA_DIR si existe; si no, modo portable (`datos/` junto al ejecutable, si ya existe o hay
`portable.txt`); instalado: %APPDATA%/DiarioTrading/datos (el instalador no lo toca al actualizar o desinstalar).
"""
import os
import sqlite3
import sys

FROZEN = getattr(sys, "frozen", False)
BASE_DIR = os.path.dirname(sys.executable) if FROZEN else os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _data_dir():
    if os.environ.get("DIARIO_DATA_DIR"):
        return os.environ["DIARIO_DATA_DIR"]
    local = os.path.join(BASE_DIR, "datos")
    if not FROZEN or os.path.isdir(local) or os.path.exists(os.path.join(BASE_DIR, "portable.txt")):
        return local
    return os.path.join(os.environ.get("APPDATA") or os.path.expanduser("~"), "DiarioTrading", "datos")


DATA_DIR = _data_dir()
DB_PATH = os.path.join(DATA_DIR, "diario.db")
SHOTS_DIR = os.path.join(DATA_DIR, "capturas")
BACKUP_DIR = os.path.join(DATA_DIR, "backups")

SCHEMA = """
CREATE TABLE IF NOT EXISTS instruments (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    contract_size REAL NOT NULL,
    tick_size REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ext_id TEXT UNIQUE,
    source TEXT NOT NULL DEFAULT 'manual',
    instrument TEXT NOT NULL REFERENCES instruments(code),
    broker_symbol TEXT,
    side TEXT NOT NULL CHECK (side IN ('buy','sell')),
    volume REAL NOT NULL,
    entry_time TEXT NOT NULL,
    exit_time TEXT,
    entry_price REAL NOT NULL,
    exit_price REAL,
    sl REAL,
    tp REAL,
    commission REAL NOT NULL DEFAULT 0,
    swap REAL NOT NULL DEFAULT 0,
    profit REAL NOT NULL DEFAULT 0,
    setup TEXT DEFAULT '',
    emotion INTEGER,
    plan_grade TEXT DEFAULT '',
    mistake TEXT DEFAULT '',
    notes_pre TEXT DEFAULT '',
    notes_post TEXT DEFAULT '',
    screenshot TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_trades_exit ON trades(exit_time);
CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL UNIQUE,
    kind TEXT NOT NULL DEFAULT 'real' CHECK (kind IN ('real','demo','fondeo')),
    broker TEXT DEFAULT '',
    currency TEXT NOT NULL DEFAULT 'USD',
    starting_balance REAL NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    server_mode TEXT NOT NULL DEFAULT 'fixed' CHECK (server_mode IN ('utc','fixed','ny_close')),
    server_offset REAL NOT NULL DEFAULT 0,
    money_scale REAL NOT NULL DEFAULT 1
);
CREATE TABLE IF NOT EXISTS movements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    date TEXT NOT NULL,
    amount REAL NOT NULL,
    note TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS reviews (
    period TEXT PRIMARY KEY,
    went_well TEXT DEFAULT '',
    to_improve TEXT DEFAULT '',
    next_goal TEXT DEFAULT ''
);
CREATE TABLE IF NOT EXISTS imports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES accounts(id),
    filename TEXT NOT NULL,
    sha256 TEXT NOT NULL,
    imported_at TEXT NOT NULL,
    n_read INTEGER NOT NULL,
    n_added INTEGER NOT NULL,
    n_dup INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS trade_shots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_id INTEGER NOT NULL REFERENCES trades(id) ON DELETE CASCADE,
    file TEXT NOT NULL,
    label TEXT DEFAULT ''
);
"""

# contract_size: unidades por 1.00 lote. Varía por bróker: comprobarlo en MT5 (Especificación del símbolo).
DEFAULT_INSTRUMENTS = [
    ("XAU", "Oro (XAUUSD)", 100.0, 0.01),
    ("SPX", "S&P 500 (US500)", 1.0, 0.1),
    ("NDX", "Nasdaq 100 (US100)", 1.0, 0.1),
]
DEFAULT_SETTINGS = {"starting_balance": "10000"}


def connect():
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(SHOTS_DIR, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init():
    with connect() as conn:
        conn.executescript(SCHEMA)
        conn.executemany("INSERT OR IGNORE INTO instruments VALUES (?,?,?,?)", DEFAULT_INSTRUMENTS)
        conn.executemany("INSERT OR IGNORE INTO settings VALUES (?,?)", DEFAULT_SETTINGS.items())
        # Migración desde la v0.1 (sin cuentas): cuenta por defecto + columna account_id.
        cols = {r["name"] for r in conn.execute("PRAGMA table_info(trades)")}
        if "account_id" not in cols:
            conn.execute("ALTER TABLE trades ADD COLUMN account_id INTEGER REFERENCES accounts(id)")
        acols = {r["name"] for r in conn.execute("PRAGMA table_info(accounts)")}
        if "money_scale" not in acols:
            conn.execute("ALTER TABLE accounts ADD COLUMN money_scale REAL NOT NULL DEFAULT 1")
        if "server_mode" not in acols:
            conn.execute("ALTER TABLE accounts ADD COLUMN server_mode TEXT NOT NULL DEFAULT 'fixed'")
            conn.execute("ALTER TABLE accounts ADD COLUMN server_offset REAL NOT NULL DEFAULT 0")
        if not conn.execute("SELECT 1 FROM accounts").fetchone():
            start = conn.execute("SELECT value FROM settings WHERE key='starting_balance'").fetchone()
            conn.execute("INSERT INTO accounts (name, kind, starting_balance) VALUES ('Principal','real',?)",
                         (float(start["value"]) if start else 0,))
        conn.execute("UPDATE trades SET account_id = (SELECT MIN(id) FROM accounts) WHERE account_id IS NULL")
        conn.execute("INSERT INTO trade_shots (trade_id, file) SELECT id, screenshot FROM trades "
                     "WHERE screenshot != '' AND NOT EXISTS (SELECT 1 FROM trade_shots s WHERE s.trade_id = trades.id)")
        conn.execute("UPDATE trades SET screenshot = ''")
