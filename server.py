"""
server.py - سرور محلی که شبیه‌ساز Algorand را مثل algod + indexer + کیف پول به رابط HTML می‌دهد.
اجرا:  python3 server.py      سپس مرورگر:  http://127.0.0.1:8765/
نیازی به نصب چیزی جز پکیج cryptography نیست. تنظیمات همین‌جا در SERVER است.
"""
import json
import os
import re
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import algosim as sim

SERVER = {"HOST": "127.0.0.1", "PORT": 8765, "WEB_DIR": os.path.dirname(os.path.abspath(__file__))}

STATE = {}


def reset_world():
    chain, wallets = sim.make_demo_world()
    STATE.update(chain=chain, wallets=wallets)


def block_loop():
    while True:
        time.sleep(sim.SETTINGS["BLOCK_TIME"])
        STATE["chain"].produce_block()


def j(handler, code, obj):
    body = json.dumps(obj, ensure_ascii=False).encode()
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    server_version = "LmarketSim/1"

    def log_message(self, *a):  # بی‌صدا
        pass

    # ---------------------------------------------------------- GET
    def do_GET(self):
        chain = STATE["chain"]
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            return self.static("index.html", "text/html; charset=utf-8")
        if path == "/release.json":
            return j(self, 200, sim.release_manifest())
        if not path.startswith("/api/"):
            return j(self, 404, {"error": "not found"})
        if chain.faults["latency_ms"]:
            time.sleep(chain.faults["latency_ms"] / 1000)
        if chain.faults["offline"] and not path.startswith("/api/dev"):
            return j(self, 503, {"error": "گره در دسترس نیست"})
        m = None
        if path == "/api/params":
            return j(self, 200, chain.params())
        if path == "/api/wallets":
            return j(self, 200, [{"name": n, "address": w.address, "balance": chain.balance(w.address),
                                  "age_days": chain.reputation(w.address)["wallet_age_days"]}
                                 for n, w in STATE["wallets"].items()])
        if (m := re.fullmatch(r"/api/account/([A-Z2-7]+)", path)):
            return j(self, 200, chain.account_info(m[1]))
        if (m := re.fullmatch(r"/api/reputation/([A-Z2-7]+)", path)):
            return j(self, 200, chain.reputation(m[1]))
        if (m := re.fullmatch(r"/api/apps/([A-Z2-7]+)", path)):
            return j(self, 200, chain.apps_for(m[1]))
        if (m := re.fullmatch(r"/api/app/(\d+)", path)):
            return j(self, 200, chain.app_info(int(m[1])))
        if (m := re.fullmatch(r"/api/app/(\d+)/events", path)):
            return j(self, 200, chain.events_for(int(m[1])))
        if (m := re.fullmatch(r"/api/tx/([A-Z2-7]+)", path)):
            return j(self, 200, chain.tx_status(m[1]))
        return j(self, 404, {"error": "not found"})

    def static(self, name, ctype):
        with open(os.path.join(SERVER["WEB_DIR"], name), "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    # ---------------------------------------------------------- POST
    def do_POST(self):
        chain, wallets = STATE["chain"], STATE["wallets"]
        path = self.path.split("?")[0]
        try:
            n = int(self.headers.get("Content-Length") or 0)
            data = json.loads(self.rfile.read(n) or b"{}")
        except Exception:
            return j(self, 400, {"error": "درخواست نامعتبر"})
        if path.startswith("/api/dev/"):
            return self.dev(path[len("/api/dev/"):], data)
        if chain.faults["latency_ms"]:
            time.sleep(chain.faults["latency_ms"] / 1000)
        if chain.faults["offline"]:
            return j(self, 503, {"error": "گره در دسترس نیست"})
        by_addr = {w.address: w for w in wallets.values()}
        try:
            if path in ("/api/wallet/preview", "/api/wallet/sign"):
                w = by_addr.get(data.get("address"))
                if not w:
                    return j(self, 404, {"error": "کیف پول پیدا نشد"})
                txns, summary = sim.build_group(chain, w.address, data["intent"])
                if path.endswith("preview"):
                    return j(self, 200, {"summary": summary, "balance": chain.balance(w.address)})
                return j(self, 200, {"summary": summary, "signed": [w.sign_txn(t) for t in txns]})
            if path == "/api/wallet/code":
                w = by_addr.get(data.get("address"))
                info = chain.app_info(int(data["app_id"]))
                if not w or not info["exists"]:
                    return j(self, 404, {"error": "کیف پول یا قرارداد پیدا نشد"})
                s = info["state"]
                want = {s["seller"]: sim.LmarketV1.KIND_PAY, s["buyer"]: sim.LmarketV1.KIND_GOODS}.get(w.address)
                if not want:
                    return j(self, 400, {"error": "این کیف پول طرف قرارداد نیست"})
                msg = sim.LmarketV1.code_message(s["version"], chain.genesis_id, info["id"], want)
                return j(self, 200, {"code": sim.b32(w.sign_message(msg)), "kind": want, "message": msg.decode()})
            if path == "/api/submit":
                gid = chain.submit(data["signed"])
                return j(self, 200, {"gid": gid})
        except sim.SubmitError as ex:
            return j(self, 400, {"error": str(ex)})
        except (KeyError, ValueError, TypeError) as ex:
            return j(self, 400, {"error": f"درخواست ناقص: {ex}"})
        return j(self, 404, {"error": "not found"})

    def dev(self, op, d):
        chain = STATE["chain"]
        if op == "advance":
            chain.advance(int(d.get("seconds", 0)))
        elif op == "fault":
            chain.set_fault(**{k: d[k] for k in ("offline", "paused", "drop_next", "latency_ms") if k in d})
        elif op == "block":
            chain.produce_block()
        elif op == "reset":
            reset_world()
        elif op == "fund":
            chain.fund(d["address"], int(d["amount"]))
        else:
            return j(self, 404, {"error": "unknown"})
        return j(self, 200, {"ok": True, "params": STATE["chain"].params()})


def main():
    reset_world()
    threading.Thread(target=block_loop, daemon=True).start()
    httpd = ThreadingHTTPServer((SERVER["HOST"], SERVER["PORT"]), Handler)
    print(f"Lmarket simulator: http://{SERVER['HOST']}:{SERVER['PORT']}/")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
