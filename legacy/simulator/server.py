"""
server.py - سرور محلی شبیه‌ساز Algorand برای رابط Lmarket.
اجرا:  python3 server.py   →   http://127.0.0.1:8765/

این سرور هیچ کلید ناشری ندارد؛ release.json را فقط سرو می‌کند (ساخته‌شده توسط make_release.py).
پیش‌نمایش و امضای تراکنش با یک توکن یک‌بارمصرف به هم وصل‌اند، تا همان چیزی که کاربر تأیید کرده امضا شود.
"""
import json
import os
import re
import secrets
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import algosim as sim

SERVER = {
    "HOST": "127.0.0.1",
    "PORT": 8765,
    "WEB_DIR": os.path.dirname(os.path.abspath(__file__)),
    "DEV_TOOLS": True,          # ابزار زمان/قطع شبکه؛ در نسخه‌ی واقعی False
    "MAX_BODY": 64 * 1024,      # بایت
    "MAX_PENDING": 500,         # بیشترین پیش‌نمایش معلق
}
ALLOWED_HOSTS = {f"127.0.0.1:{SERVER['PORT']}", f"localhost:{SERVER['PORT']}"}
ALLOWED_ORIGINS = {f"http://{h}" for h in ALLOWED_HOSTS}

STATE = {"pending": {}}
LOCK = threading.Lock()


def reset_world():
    chain, wallets = sim.make_demo_world()
    with LOCK:
        STATE.update(chain=chain, wallets=wallets, pending={})


def block_loop():
    while True:
        time.sleep(sim.SETTINGS["BLOCK_TIME"])
        STATE["chain"].produce_block()


class Handler(BaseHTTPRequestHandler):
    server_version = "LmarketSim/2"

    def log_message(self, fmt, *args):
        sys.stderr.write("%s %s\n" % (self.command, self.path))

    # ------------------------------------------------ پاسخ
    def send(self, code, ctype, body):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(body)

    def j(self, code, obj):
        self.send(code, "application/json; charset=utf-8", json.dumps(obj, ensure_ascii=False).encode())

    def host_ok(self):
        """جلوی DNS rebinding و درخواست از صفحه‌های دیگر را می‌گیرد."""
        if self.headers.get("Host") not in ALLOWED_HOSTS:
            self.j(403, {"error": "میزبان درخواست مجاز نیست"})
            return False
        origin = self.headers.get("Origin")
        if origin and origin not in ALLOWED_ORIGINS:
            self.j(403, {"error": "مبدأ درخواست مجاز نیست"})
            return False
        return True

    # ------------------------------------------------ GET
    def do_GET(self):
        if not self.host_ok():
            return
        try:
            self.route_get()
        except Exception:
            traceback.print_exc()
            self.j(500, {"error": "خطای داخلی سرور"})

    def route_get(self):
        chain = STATE["chain"]
        path = self.path.split("?")[0]
        if path in ("/", "/index.html"):
            with open(os.path.join(SERVER["WEB_DIR"], "index.html"), "rb") as f:
                return self.send(200, "text/html; charset=utf-8", f.read())
        if path == "/release.json":
            fp = os.path.join(SERVER["WEB_DIR"], "release.json")
            if not os.path.exists(fp):
                return self.j(404, {"error": "release.json ساخته نشده است؛ make_release.py را اجرا کنید"})
            with open(fp, "rb") as f:
                return self.send(200, "application/json; charset=utf-8", f.read())
        if not path.startswith("/api/"):
            return self.j(404, {"error": "not found"})
        if chain.faults["latency_ms"]:
            time.sleep(chain.faults["latency_ms"] / 1000)
        if chain.faults["offline"]:
            return self.j(503, {"error": "گره در دسترس نیست"})

        if path == "/api/params":
            return self.j(200, chain.params())
        if path == "/api/wallets":
            return self.j(200, [{"name": n, "address": w.address, "balance": chain.balance(w.address),
                                 "age_days": chain.reputation(w.address)["wallet_age_days"]}
                                for n, w in STATE["wallets"].items()])
        if (m := re.fullmatch(r"/api/account/([A-Z2-7]+)", path)):
            return self.j(200, chain.account_info(m[1]))
        if (m := re.fullmatch(r"/api/reputation/([A-Z2-7]+)", path)):
            return self.j(200, chain.reputation(m[1]))
        if (m := re.fullmatch(r"/api/apps/([A-Z2-7]+)", path)):
            return self.j(200, chain.apps_for(m[1]))
        if (m := re.fullmatch(r"/api/app/(\d+)", path)):
            return self.j(200, chain.app_info(int(m[1])))
        if (m := re.fullmatch(r"/api/app/(\d+)/events", path)):
            return self.j(200, chain.events_for(int(m[1])))
        if (m := re.fullmatch(r"/api/tx/([A-Z2-7]+)", path)):
            return self.j(200, chain.tx_status(m[1]))
        return self.j(404, {"error": "not found"})

    # ------------------------------------------------ POST
    def do_POST(self):
        if not self.host_ok():
            return
        n = int(self.headers.get("Content-Length") or 0)
        if n > SERVER["MAX_BODY"]:
            return self.j(413, {"error": "درخواست خیلی بزرگ است"})
        try:
            data = json.loads(self.rfile.read(n) or b"{}")
            if not isinstance(data, dict):
                raise ValueError("object expected")
        except Exception:
            return self.j(400, {"error": "درخواست نامعتبر"})
        try:
            self.route_post(data)
        except sim.SubmitError as ex:
            self.j(400, {"error": str(ex)})
        except (KeyError, ValueError, TypeError) as ex:
            self.j(400, {"error": f"درخواست ناقص یا نادرست: {ex}"})
        except Exception:
            traceback.print_exc()
            self.j(500, {"error": "خطای داخلی سرور"})

    def route_post(self, data):
        chain, wallets = STATE["chain"], STATE["wallets"]
        path = self.path.split("?")[0]
        if path.startswith("/api/dev/"):
            if not SERVER["DEV_TOOLS"]:
                return self.j(404, {"error": "not found"})
            return self.dev(path[len("/api/dev/"):], data)
        if chain.faults["latency_ms"]:
            time.sleep(chain.faults["latency_ms"] / 1000)
        if chain.faults["offline"]:
            return self.j(503, {"error": "گره در دسترس نیست"})
        by_addr = {w.address: w for w in wallets.values()}

        if path == "/api/wallet/preview":
            w = by_addr.get(data.get("address"))
            if not w:
                return self.j(404, {"error": "کیف پول پیدا نشد"})
            txns, summary = sim.build_group(chain, w.address, data["intent"])
            token = secrets.token_urlsafe(16)
            with LOCK:
                pend = STATE["pending"]
                if len(pend) >= SERVER["MAX_PENDING"]:
                    pend.pop(next(iter(pend)))
                pend[token] = {"address": w.address, "txns": txns}
            return self.j(200, {"token": token, "summary": summary, "balance": chain.balance(w.address)})

        if path == "/api/wallet/sign":
            with LOCK:
                p = STATE["pending"].pop(data.get("token"), None)   # یک‌بارمصرف
            if not p or p["address"] != data.get("address"):
                return self.j(400, {"error": "پیش‌نمایش منقضی شده یا با این کیف پول نمی‌خواند؛ دوباره تلاش کنید"})
            w = by_addr[p["address"]]
            return self.j(200, {"signed": [w.sign_txn(t) for t in p["txns"]]})

        if path == "/api/wallet/code":
            w = by_addr.get(data.get("address"))
            info = chain.app_info(int(data["app_id"]))
            if not w or not info["exists"]:
                return self.j(404, {"error": "کیف پول یا قرارداد پیدا نشد"})
            s = info["state"]
            want = {s["seller"]: sim.LmarketV1.KIND_PAY, s["buyer"]: sim.LmarketV1.KIND_GOODS}.get(w.address)
            if not want:
                return self.j(400, {"error": "این کیف پول طرف قرارداد نیست"})
            msg = sim.LmarketV1.code_message(s["version"], chain.genesis_id, info["id"], want)
            return self.j(200, {"code": sim.b32(w.sign_message(msg)), "kind": want, "message": msg.decode()})

        if path == "/api/submit":
            return self.j(200, {"gid": chain.submit(data["signed"])})
        return self.j(404, {"error": "not found"})

    # ------------------------------------------------ ابزار آزمایش (فقط DEV_TOOLS)
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
            return self.j(404, {"error": "unknown"})
        self.j(200, {"ok": True, "params": STATE["chain"].params()})


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
