import json
import logging
import sys
import subprocess
from http.server import BaseHTTPRequestHandler, HTTPServer
import urllib.parse
import os

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

class HAgentProxyHandler(BaseHTTPRequestHandler):
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
            self.wfile.write(json.dumps({"status": "ok", "service": "hagent-proxy"}).encode('utf-8'))
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
                
                # Trích xuất user context từ Bridge request
                context = data.get("context", {})
                user_token = context.get("user_token", "")
                user_id = context.get("user_id", "")
                
                logging.info(f"Received message from Bridge: {message} for session: {session_id}")
                logging.info(f"User context: user_id={user_id}, token_length={len(user_token) if user_token else 0}")
                
                # Chuẩn bị env cho HAgent CLI — truyền token để hautoml_tools.py sử dụng
                env = os.environ.copy()
                if user_token:
                    env["USER_TOKEN"] = user_token
                if user_id:
                    env["USER_ID"] = user_id

                # Ghi fallback file để skill runtime vẫn đọc được token/user_id
                token_file = "/tmp/hagent_user_token"
                user_id_file = "/tmp/hagent_user_id"
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
                
                # Đọc SOUL.md để inject vào system prompt
                soul_content = ""
                try:
                    with open("/app/hagent/SOUL.md", "r", encoding="utf-8") as f:
                        soul_content = f.read()
                        # Prepend SOUL.md content to message
                        message = f"{soul_content}\n\n---\n\nUser request: {message}"
                except Exception as e:
                    logging.warning(f"Could not read SOUL.md: {e}")
                
                # Thực thi lệnh HAgent CLI toàn cục
                cmd = ["openclaw", "agent", "--message", message, "--session-id", session_id, "--json"]
                logging.info(f"Executing: {' '.join(cmd)}")
                
                result = subprocess.run(cmd, capture_output=True, text=True, env=env)
                
                agent_reply = "No response"
                sources = []
                suggestions = []
                
                if result.returncode != 0:
                    logging.error(f"CLI Error: {result.stderr}")
                    agent_reply = f"HAgent Error: {result.stderr}"
                else:
                    # Trích xuất JSON từ output (HAgent outputs MULTIPLE JSON blocks)
                    js_content = result.stdout + "\n" + result.stderr
                    try:
                        # Tìm TẤT CẢ JSON objects trong output, chọn cái có "payloads"
                        import re
                        cli_res = None
                        
                        # Tìm tất cả vị trí bắt đầu '{' ở đầu dòng hoặc sau whitespace
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
                        
                        # Chọn JSON block có chứa "payloads" (block chính)
                        for candidate in candidates:
                            try:
                                parsed = json.loads(candidate)
                                if isinstance(parsed, dict):
                                    if "payloads" in parsed or "result" in parsed or "data" in parsed:
                                        cli_res = parsed
                                        logging.info(f"== Selected JSON with keys: {list(parsed.keys())}")
                                        break
                                    elif cli_res is None and len(parsed) > 0:
                                        cli_res = parsed  # fallback to first non-empty
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
                            agent_reply = "No valid JSON received from HAgent"
                            logging.error(f"No valid JSON found in {len(candidates)} candidates. Raw output: {js_content[:500]}")
                    except Exception as parse_err:
                        logging.warning(f"Failed to parse JSON. Err: {parse_err}")
                        agent_reply = "Error parsing response: " + str(parse_err)
                        
                    sys.stdout.flush()
                        
                    logging.info(f"== FINAL Agent Reply: {agent_reply}")


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
                self.wfile.write(json.dumps(response_data).encode('utf-8'))
                
            except json.JSONDecodeError:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b'Bad Request')
            except Exception as ex:
                logging.error(f"Exception: {str(ex)}")
                self.send_response(500)
                self.end_headers()
                self.wfile.write(json.dumps({"error": str(ex)}).encode('utf-8'))
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
