"""Cascade Lite - a single-service collaborative pixel canvas.

One process, SQLite storage, poll-based frontend.
Exposes the three ops endpoints every later project relies on:
  /healthz  liveness   — is the process up?
  /readyz   readiness  — can it serve? (DB reachable)
  /metrics  Prometheus — paints, errors, latency
"""
import os
import time
import random
import sqlite3
from contextlib import closing

from fastapi import FastAPI
from fastapi.responses import JSONResponse, PlainTextResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

W = H = 64                                   # canvas is 64x64 pixels
DB = os.getenv("DB_PATH", "canvas.db")       # 12-factor: path from the environment
HERE = os.path.dirname(__file__)

app = FastAPI(title="Cascade Lite")

# --- in-memory metrics (a real app would use a client lib; this keeps deps tiny) ---
PAINTS = {"total": 0, "errors": 0}
LAT_MS = []                                  # recent paint latencies, ms

# --- chaos: a time-boxed, self-contained fault injector for the demo ---
# In Cascade Full this maps to real Chaos Mesh experiments; here it just makes
# the app misbehave for a few seconds so you can watch /metrics react and recover.
CHAOS = {"mode": None, "until": 0.0}          # mode in {None, "latency", "error"}
CHAOS_SECONDS = 20                            # experiments auto-expire (auto-heal)


def chaos_active():
    """Return the active chaos mode, or None once the window has expired."""
    if CHAOS["mode"] and time.monotonic() < CHAOS["until"]:
        return CHAOS["mode"]
    CHAOS["mode"] = None
    return None


def db():
    """Open the SQLite DB and ensure the table exists."""
    conn = sqlite3.connect(DB)
    conn.execute(
        "CREATE TABLE IF NOT EXISTS px (x INT, y INT, color TEXT, PRIMARY KEY (x, y))"
    )
    return conn


class Pixel(BaseModel):
    x: int
    y: int
    color: str


@app.get("/healthz")                         # liveness: process is running
def healthz():
    return {"ok": True}


@app.get("/readyz")                          # readiness: can we actually serve?
def readyz():
    try:
        with closing(db()) as c:
            c.execute("SELECT 1")
        return {"ready": True}
    except Exception:
        return JSONResponse({"ready": False}, status_code=503)


@app.get("/api/canvas")
def canvas():
    with closing(db()) as c:
        rows = c.execute("SELECT x, y, color FROM px").fetchall()
    return {"w": W, "h": H, "pixels": [{"x": r[0], "y": r[1], "color": r[2]} for r in rows]}


@app.post("/api/paint")
def paint(p: Pixel):
    t0 = time.time()
    mode = chaos_active()
    try:
        if mode == "latency":
            time.sleep(random.uniform(0.3, 1.2))     # CHAOS: slow every request down
        if mode == "error" and random.random() < 0.5:
            PAINTS["errors"] += 1                     # CHAOS: fail ~half the requests
            return JSONResponse({"ok": False, "error": "chaos"}, status_code=500)
        if not (0 <= p.x < W and 0 <= p.y < H):
            raise ValueError("out of bounds")
        if not (isinstance(p.color, str) and p.color.startswith("#") and len(p.color) in (4, 7)):
            raise ValueError("bad color")
        with closing(db()) as c:
            c.execute("INSERT OR REPLACE INTO px VALUES (?, ?, ?)", (p.x, p.y, p.color))
            c.commit()
        PAINTS["total"] += 1
        return {"ok": True}
    except Exception:
        PAINTS["errors"] += 1
        return JSONResponse({"ok": False}, status_code=400)
    finally:
        LAT_MS.append((time.time() - t0) * 1000)
        del LAT_MS[:-1000]                    # keep only the last 1000 samples


@app.post("/api/chaos")
def chaos(mode: str = "latency"):
    """Start (or clear) a time-boxed chaos experiment. mode = latency | error | clear."""
    if mode == "clear":
        CHAOS["mode"] = None
        return {"chaos": "cleared"}
    if mode not in ("latency", "error"):
        return JSONResponse({"error": "mode must be latency, error, or clear"}, status_code=400)
    CHAOS["mode"] = mode
    CHAOS["until"] = time.monotonic() + CHAOS_SECONDS
    return {"chaos": mode, "seconds": CHAOS_SECONDS}


@app.get("/metrics")                         # Prometheus text format
def metrics():
    ordered = sorted(LAT_MS)
    p99 = ordered[int(len(ordered) * 0.99)] / 1000.0 if ordered else 0.0
    body = (
        "# HELP cascade_paints_total Total successful paints\n"
        "# TYPE cascade_paints_total counter\n"
        f"cascade_paints_total {PAINTS['total']}\n"
        "# HELP cascade_paint_errors_total Total rejected paints\n"
        "# TYPE cascade_paint_errors_total counter\n"
        f"cascade_paint_errors_total {PAINTS['errors']}\n"
        "# HELP cascade_paint_latency_p99_seconds p99 paint latency\n"
        "# TYPE cascade_paint_latency_p99_seconds gauge\n"
        f"cascade_paint_latency_p99_seconds {p99}\n"
        "# HELP cascade_chaos_active Whether a chaos experiment is running\n"
        "# TYPE cascade_chaos_active gauge\n"
        f"cascade_chaos_active {1 if chaos_active() else 0}\n"
    )
    return PlainTextResponse(body)


@app.get("/")
def index():
    return FileResponse(os.path.join(HERE, "static", "index.html"))


# serve the rest of /static (if you add JS/CSS files later)
if os.path.isdir(os.path.join(HERE, "static")):
    app.mount("/static", StaticFiles(directory=os.path.join(HERE, "static")), name="static")