import argparse
import json
import socket
import threading
import queue
import re
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

from pydantic import BaseModel

from workflow.pipeline import TradingPipeline
from data.search import resolve_code, search_stock, get_stock_name_from_code
from memory.database import save_analysis, get_history, get_analysis


ROOT = Path(__file__).resolve().parent
WEB_DIR = ROOT / "web"


def _model_dump(value):
    if value is None:
        return None
    if isinstance(value, BaseModel):
        return value.model_dump()
    return value


def _state_to_payload(state, raw_input=""):
    return {
        "ticker": state.ticker,
        "ticker_name": state.ticker_name,
        "search_input": raw_input,
        "final_decision": _model_dump(state.final_decision),
        "research_plan": _model_dump(state.research_plan),
        "trade_proposal": _model_dump(state.trade_proposal),
        "risk_assessments": [
            {"agent": item.agent, "assessment": item.assessment}
            for item in state.risk_assessments
        ],
        "reports": {
            "technical": state.technical_report,
            "sentiment": state.sentiment_report,
            "news": state.news_report,
            "fundamental": state.fundamental_report,
        },
        "raw_data": {
            "industry": state.raw_data.get("industry", ""),
            "realtime": state.raw_data.get("realtime", {}),
            "news": state.raw_data.get("news", []),
            "fundamentals": state.raw_data.get("fundamentals", {}),
            "indicators": state.raw_data.get("indicators", {}),
            "past_context": state.raw_data.get("past_context", ""),
        },
    }


class WebHandler(SimpleHTTPRequestHandler):
    server_version = "TradingAgentWeb/1.0"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    def log_message(self, format, *args):
        pass

    def _cors_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.send_header("Access-Control-Max-Age", "86400")

    def do_OPTIONS(self):
        self.send_response(204)
        self._cors_headers()
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/api/health":
            self._send_json({"ok": True})
            return
        if parsed.path == "/":
            self.path = "/index.html"
        return super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        try:
            if parsed.path == "/api/search":
                self._handle_search()
            elif parsed.path == "/api/analyze":
                self._handle_analyze_blocking()
            elif parsed.path == "/api/analyze/stream":
                self._handle_analyze_stream()
            elif parsed.path == "/api/history":
                self._handle_history()
            elif parsed.path.startswith("/api/history/"):
                self._handle_history_detail()
            else:
                self._send_json({"error": "Not found"}, status=404)
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def _read_body(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length).decode("utf-8")
        return json.loads(raw or "{}")

    def _resolve_ticker(self, body: dict) -> str | None:
        raw_input = str(body.get("ticker", "")).strip()
        if not raw_input:
            self._send_json({"error": "请输入股票代码或名称"}, status=400)
            return None

        if re.match(r"^\d{6}$", raw_input):
            return raw_input

        code, name = resolve_code(raw_input)
        if code:
            return code

        self._send_json({
            "error": f"未找到匹配的股票: {raw_input}",
            "suggestions": [r["code"] + " " + r["name"] for r in search_stock(raw_input)[:5]],
        }, status=404)
        return None

    def _handle_search(self):
        body = self._read_body()
        query = str(body.get("query", "")).strip()
        if not query:
            self._send_json({"results": []})
            return

        results = search_stock(query)
        self._send_json({"results": results})

    def _handle_analyze_blocking(self):
        body = self._read_body()
        ticker = self._resolve_ticker(body)
        if ticker is None:
            return
        try:
            state = TradingPipeline().run(ticker)
            self._send_json(_state_to_payload(state))
        except Exception as exc:
            self._send_json({"error": str(exc)}, status=500)

    def _handle_analyze_stream(self):
        body = self._read_body()
        ticker = self._resolve_ticker(body)
        if ticker is None:
            return

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache")
        self.send_header("Connection", "close")
        self._cors_headers()
        self.end_headers()

        q = queue.Queue()
        raw_input = body.get("ticker", "").strip()

        def on_progress(phase, detail):
            q.put(("progress", {"phase": phase, "detail": detail}))

        def run_pipeline():
            try:
                state = TradingPipeline().run(ticker, on_progress=on_progress)
                q.put(("result", _state_to_payload(state, raw_input=raw_input)))
                try:
                    save_analysis(state, raw_input=raw_input)
                except Exception:
                    pass
            except Exception as exc:
                q.put(("error", {"error": str(exc)}))

        thread = threading.Thread(target=run_pipeline, daemon=True)
        thread.start()

        try:
            while thread.is_alive() or not q.empty():
                try:
                    kind, data = q.get(timeout=2.0)
                    if kind == "progress":
                        self._sse_send("progress", data)
                    elif kind == "result":
                        self._sse_send("result", data)
                        self._sse_send("done", {})
                        try:
                            self.wfile.flush()
                            self.connection.shutdown(socket.SHUT_WR)
                        except Exception:
                            pass
                        return
                    elif kind == "error":
                        self._sse_send("error", data)
                        self.close_connection = True
                        self.wfile.flush()
                        return
                except queue.Empty:
                    pass
        except BrokenPipeError:
            pass

    def _handle_history(self):
        limit = int(self._read_body().get("limit", 20))
        rows = get_history(limit)
        self._send_json({"history": rows})

    def _handle_history_detail(self):
        parts = self.path.split("/")
        try:
            aid = int(parts[-1])
        except (ValueError, IndexError):
            self._send_json({"error": "Invalid ID"}, status=400)
            return
        row = get_analysis(aid)
        if row is None:
            self._send_json({"error": "Not found"}, status=404)
            return
        self._send_json(row)

    def _sse_send(self, event, data):
        try:
            payload = json.dumps(data, ensure_ascii=False)
            self.wfile.write(f"event: {event}\ndata: {payload}\n\n".encode("utf-8"))
            self.wfile.flush()
        except Exception:
            pass

    def _send_json(self, payload, status=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self._cors_headers()
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def _find_port(preferred):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        if sock.connect_ex(("127.0.0.1", preferred)) != 0:
            return preferred
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def main():
    parser = argparse.ArgumentParser(description="Trading Agent Web UI")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()

    port = _find_port(args.port)
    server = ThreadingHTTPServer(("127.0.0.1", port), WebHandler)
    print(f"Trading Agent Web UI: http://127.0.0.1:{port}")
    print("Press Ctrl+C to stop.")
    server.serve_forever()


if __name__ == "__main__":
    main()
