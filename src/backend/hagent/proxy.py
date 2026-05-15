import json
import logging
import re
import sys
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import os
from pathlib import Path

import yaml

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

_PROXY_CONFIG = None

# ── Lọc phần diễn giải nội bộ khỏi câu trả lời của mô hình ─────────────────

_NARRATION_PATTERNS = [
    # "Để tôi...", "Tôi sẽ...", "Tôi đã..." + nội dung tới khi xuống dòng trống
    r"(?mi)^\s*(Để tôi|Tôi sẽ|Tôi đã|Bây giờ tôi|Hãy đợi|Đang thực hiện|Đang kiểm tra|Đang gọi|Đang liệt kê)[^\n]*\n?",
    # "Đang kiểm tra bộ dữ liệu..." + biểu tượng
    r"(?mi)^\s*Đang[^\n]{0,120}\.{2,}[^\n]*\n?",
    # Các dấu hiệu suy luận hoặc kênh nội bộ
    r"(?si)<channel\|?>.*?(?=\n\n|\Z)",
    r"(?si)thought\s*[:：].*?(?=\n\n|\Z)",
    r"(?si)analysis\s*[:：].*?(?=\n\n|\Z)",
    # "Các bước thực hiện:" + danh sách đánh số
    r"(?mi)^\s*Đang thực hiện các bước\s*[:：]\s*\n(?:\s*\d+\..*\n?)+",
]

def load_proxy_config() -> dict:
    """Đọc cấu hình proxy từ hagent.yaml."""
    global _PROXY_CONFIG
    if _PROXY_CONFIG is not None:
        return _PROXY_CONFIG

    config_path = Path(os.getenv("HAGENT_CONFIG", Path(__file__).with_name("hagent.yaml")))
    if not config_path.is_absolute():
        config_path = Path(__file__).resolve().parent / config_path

    try:
        with open(config_path, "r", encoding="utf-8") as config_file:
            config = yaml.safe_load(config_file) or {}
    except Exception as exc:
        logging.warning(f"Không đọc được cấu hình HAgent tại {config_path}: {exc}")
        config = {}

    proxy_config = config.get("proxy", {})
    proxy_config["_config_dir"] = str(config_path.parent)
    _PROXY_CONFIG = proxy_config
    return proxy_config

def get_proxy_value(*keys: str):
    """Lấy giá trị lồng nhau trong cấu hình proxy."""
    current = load_proxy_config()
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current

def resolve_proxy_path(*keys: str) -> str | None:
    """Chuyển path trong cấu hình proxy thành path tuyệt đối."""
    value = get_proxy_value(*keys)
    if not value:
        return None
    path = Path(str(value))
    if path.is_absolute():
        return str(path)
    config_dir = Path(str(get_proxy_value("_config_dir") or Path(__file__).resolve().parent))
    return str((config_dir / path).resolve())

def proxy_message(message_key: str, **values: str) -> str:
    """Format thông báo lỗi theo template trong cấu hình proxy."""
    template = get_proxy_value("error_messages", message_key) or get_proxy_value("error_messages", "generic")
    if not template:
        logging.error("Thiếu proxy.error_messages.%s trong cấu hình HAgent", message_key)
        raise RuntimeError(f"Thiếu cấu hình proxy.error_messages.{message_key}")
    try:
        return str(template).format(**values)
    except KeyError as exc:
        logging.warning(f"Thiếu biến {exc} khi format thông báo lỗi {message_key}")
        return str(template)

def clean_reply(text: str) -> str:
    if not text:
        return text
    out = text
    for pat in _NARRATION_PATTERNS:
        out = re.sub(pat, "", out)
    # Gộp các đoạn trống liên tiếp để câu trả lời gọn hơn
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out.strip()

def is_internal_error(text: str) -> bool:
    if not text:
        return False
    markers = [
        "HAgent Error:",
        "Traceback",
        "GatewayTransportError",
        "FailoverError",
        "[diagnostic]",
        "[agent/embedded]",
        "[model-fallback/decision]",
        "rawError=",
        "EMBEDDED FALLBACK",
    ]
    return any(marker in text for marker in markers)

def user_safe_error(raw_error: str) -> str:
    """Chuyển log lỗi nội bộ thành thông báo ngắn cho ChatWidget."""
    text = raw_error or ""
    lower = text.lower()

    memory_match = re.search(
        r"model requires more system memory \(([^)]+)\) than is available \(([^)]+)\)",
        text,
        re.IGNORECASE,
    )
    if memory_match:
        required, available = memory_match.groups()
        return proxy_message("ollama_memory", required=required, available=available)

    if "html error page" in lower or "model_not_found" in lower or "404 <!doctype html" in lower:
        return proxy_message("ollama_endpoint")

    if "gatewaytransporterror" in lower or "1006 abnormal closure" in lower:
        return proxy_message("gateway_connection")

    if "timeout" in lower:
        return proxy_message("timeout")

    if "no valid json" in lower or "json" in lower:
        return proxy_message("invalid_response")

    return proxy_message("generic")

class HAgentProxyHandler(BaseHTTPRequestHandler):
    def _safe_write(self, payload: bytes):
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            logging.info("Client disconnected before response body was written: %s", self.path)

    def _send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'OPTIONS, GET, POST')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def do_OPTIONS(self):
        self.send_response(204)
        self._send_cors_headers()
        self.end_headers()

    def do_GET(self):
        if self.path == '/health':
            self.send_response(200)
            self._send_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self._safe_write(json.dumps({"status": "ok", "service": "hagent-proxy"}).encode('utf-8'))
            return
        self.send_response(404)
        self.end_headers()

    def do_POST(self):
        if '/hooks/agent' in self.path:
            content_length = int(self.headers.get('Content-Length', 0))
            post_data = self.rfile.read(content_length) if content_length > 0 else b''
            try:
                data = json.loads(post_data.decode('utf-8'))
                message = data.get("message", "Hello")
                session_id = data.get("session_id", "default_session")
                
                # Trích xuất ngữ cảnh người dùng từ request của Bridge
                context = data.get("context", {})
                user_token = context.get("user_token", "")
                user_id = context.get("user_id", "")
                
                logging.info(f"Received message from Bridge: {message} for session: {session_id}")
                logging.info(f"User context: user_id={user_id}, token_length={len(user_token) if user_token else 0}")
                
                # Chuẩn bị biến môi trường cho giao diện dòng lệnh HAgent để hautoml_tools.py sử dụng
                env = os.environ.copy()
                if user_token:
                    env["USER_TOKEN"] = user_token
                if user_id:
                    env["USER_ID"] = user_id

                # Ghi file dự phòng để môi trường chạy kỹ năng vẫn đọc được token và mã người dùng
                token_file = resolve_proxy_path("user_context_files", "token")
                user_id_file = resolve_proxy_path("user_context_files", "user_id")
                env["HAGENT_USER_TOKEN_FILE"] = token_file
                env["HAGENT_USER_ID_FILE"] = user_id_file
                try:
                    if user_token:
                        with open(token_file, "w", encoding="utf-8") as tf:
                            tf.write(user_token)
                    if user_id:
                        with open(user_id_file, "w", encoding="utf-8") as uf:
                            uf.write(user_id)
                except Exception as e:
                    logging.warning(f"Could not write user context fallback files: {e}")
                
                # Đọc SOUL.md để ghép vào lời nhắc hệ thống
                soul_content = ""
                try:
                    soul_path = resolve_proxy_path("soul_path")
                    if soul_path:
                        with open(soul_path, "r", encoding="utf-8") as f:
                            soul_content = f.read()
                            # Ghép nội dung SOUL.md vào trước yêu cầu người dùng
                            message = f"{soul_content}\n\n---\n\nUser request: {message}"
                except Exception as e:
                    logging.warning(f"Could not read SOUL.md: {e}")
                
                # Thực thi lệnh HAgent qua giao diện dòng lệnh
                cmd = ["openclaw", "agent", "--message", message, "--session-id", session_id, "--json"]
                logging.info(f"Executing: {' '.join(cmd)}")
                
                # Chạy trong không gian làm việc đã cấu hình để agent tìm được kỹ năng và siêu dữ liệu
                workspace_cwd = resolve_proxy_path("workspace_dir")
                if not os.path.isdir(workspace_cwd):
                    workspace_cwd = None
                result = subprocess.run(cmd, capture_output=True, text=True, env=env, cwd=workspace_cwd)
                
                agent_reply = "No response"
                sources = []
                suggestions = []
                
                if result.returncode != 0:
                    logging.error(f"CLI Error: {result.stderr}")
                    agent_reply = user_safe_error(result.stderr or result.stdout)
                else:
                    # Trích xuất JSON từ đầu ra của HAgent
                    js_content = result.stdout + "\n" + result.stderr
                    try:
                        # Tìm tất cả đối tượng JSON trong đầu ra, ưu tiên đối tượng có "payloads"
                        import re
                        cli_res = None
                        
                        # Tìm tất cả vị trí bắt đầu "{" ở đầu dòng hoặc sau khoảng trắng
                        candidates = []
                        depth = 0
                        obj_start = -1
                        for i, ch in enumerate(js_content):
                            if ch == '{':
                                if depth == 0:
                                    obj_start = i
                                depth += 1
                            elif ch == '}':
                                depth -= 1
                                if depth == 0 and obj_start != -1:
                                    candidate = js_content[obj_start:i+1]
                                    candidates.append(candidate)
                                    obj_start = -1
                        
                        logging.info(f"== Found {len(candidates)} JSON candidates in output")
                        
                        # Chọn khối JSON có chứa "payloads"
                        for candidate in candidates:
                            try:
                                parsed = json.loads(candidate)
                                if isinstance(parsed, dict):
                                    if "payloads" in parsed or "result" in parsed or "data" in parsed:
                                        cli_res = parsed
                                        logging.info(f"== Selected JSON with keys: {list(parsed.keys())}")
                                        break
                                    elif cli_res is None and len(parsed) > 0:
                                        cli_res = parsed  # Dự phòng: lấy JSON đầu tiên không rỗng
                            except json.JSONDecodeError:
                                continue
                        
                        if cli_res is not None:
                            if "result" in cli_res and isinstance(cli_res["result"], dict) and "payloads" in cli_res["result"]:
                                payloads = cli_res["result"]["payloads"]
                                agent_reply = "\n".join([p["text"] for p in payloads if isinstance(p, dict) and "text" in p])
                            elif "payloads" in cli_res:
                                payloads = cli_res["payloads"]
                                agent_reply = "\n".join([p.get("text", "") for p in payloads if isinstance(p, dict) and p.get("text")])
                            elif "data" in cli_res and isinstance(cli_res["data"], dict) and "message" in cli_res["data"]:
                                agent_reply = cli_res["data"]["message"]
                            else:
                                agent_reply = cli_res.get("response", cli_res.get("message", ""))
                                
                            if not agent_reply or str(agent_reply).strip() == "":
                                agent_reply = json.dumps(cli_res, ensure_ascii=False, indent=2)[:1000]

                            if isinstance(cli_res, dict):
                                if "sources" in cli_res:
                                    sources = cli_res["sources"]
                                elif "data" in cli_res and isinstance(cli_res["data"], dict) and "sources" in cli_res["data"]:
                                    sources = cli_res["data"]["sources"]
                        else:
                            agent_reply = user_safe_error("No valid JSON received from HAgent")
                            logging.error(f"No valid JSON found in {len(candidates)} candidates. Raw output: {js_content[:500]}")
                    except Exception as parse_err:
                        logging.warning(f"Failed to parse JSON. Err: {parse_err}")
                        agent_reply = user_safe_error("Error parsing response: " + str(parse_err))
                        
                    sys.stdout.flush()
                        
                    logging.info(f"== FINAL Agent Reply: {agent_reply}")


                # Lọc diễn giải và nhật ký nội bộ trước khi gửi về giao diện
                agent_reply = clean_reply(agent_reply)
                if is_internal_error(agent_reply):
                    agent_reply = user_safe_error(agent_reply)
                logging.info(f"== CLEANED Reply: {agent_reply}")

                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self._send_cors_headers()
                self.end_headers()
                
                response_data = {
                    "response": agent_reply,
                    "sources": sources,
                    "suggestions": suggestions,
                    "provider": "hagent",
                    "model": "agent"
                }
                self._safe_write(json.dumps(response_data).encode('utf-8'))
                
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
                self._safe_write(b'Bad Request')
            except Exception as ex:
                logging.error(f"Exception: {str(ex)}")
                self.send_response(500)
                self.end_headers()
                self._safe_write(json.dumps({"error": str(ex)}).encode('utf-8'))
            return

        self.send_response(404)
        self.end_headers()

if __name__ == '__main__':
    port = 18790
    server = HTTPServer(('0.0.0.0', port), HAgentProxyHandler)
    logging.info(f"HAgent Proxy listening internally on port {port}...")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    server.server_close()
    logging.info("Proxy Server stopped.")
