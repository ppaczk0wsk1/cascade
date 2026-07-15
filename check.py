import json
import os
import pathlib
import time
import urllib.request

TARGETS = {
    "cascade": "https://ca-8e6efac6962e40569ba757d0195679f6.ecs.eu-central-1.on.aws/healthz"
}
results = []

for name, url in TARGETS.items():
    t0 = time.time()
    ok = False
    code = 0
    try:
        r = urllib.request.urlopen(url, timeout=5)
        code = r.status
        ok = code == 200
    except Exception:
        code = -1

    if not ok:
        payload = {"content": f"🔴 {name} is DOWN (code {code})"}
        req = urllib.request.Request(
            os.environ["WEBHOOK"],
            data=json.dumps(payload).encode(),
            headers={"content-type": "application/json"},
        )
        urllib.request.urlopen(req)

    results.append(
        {
            "name": name,
            "ok": ok,
            "code": code,
            "ms": round((time.time() - t0) * 1000),
            "ts": int(time.time()),
        }
    )

hist = pathlib.Path("history.json")
data = json.loads(hist.read_text()) if hist.exists() else []
data = (data + results)[-2000:]
hist.write_text(json.dumps(data))
