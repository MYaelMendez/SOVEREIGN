#!/usr/bin/env python3
"""Render fleet-waves.html to MP4 via Chrome CDP + ffmpeg NVENC.

Uses the Chrome DevTools Protocol over raw WebSocket (no puppeteer needed).
Drives the deterministic GSAP timeline via window.__timelines.
"""
import os, time, json, base64, subprocess, tempfile, socket, threading, http.client
import http.server, functools, select, hashlib

CHROME  = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
FFMPEG  = r"C:\Users\yaelm\AppData\Local\hermes\tools\ffmpeg-9.0.1-win32-x64\bin\ffmpeg.exe"
SITE_DIR  = r"C:\æ\site"
SCENE_URL = "http://127.0.0.1:8125/aipodcast_me/fleet-waves.html"
OUTPUT    = r"C:\æ\site\aipodcast_me\fleet-waves-development.mp4"
DURATION, FPS, W, H = 12.0, 30, 1920, 1080

def start_http_server():
    """Serve C:/æ/site on :8125 for local Chrome access."""
    h = functools.partial(http.server.SimpleHTTPRequestHandler, directory=SITE_DIR)
    srv = http.server.HTTPServer(("127.0.0.1", 8125), h)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    print(f"HTTP server on :8125 serving {SITE_DIR}")
    return srv

def start_chrome(port):
    """Launch Chrome headless with remote debugging."""
    cmd = [ CHROME,
        "--headless=new", "--disable-gpu", "--no-sandbox",
        "--no-first-run", "--no-default-browser-check", "--disable-extensions",
        "--disable-dev-shm-usage",
        f"--remote-debugging-port={port}",
        f"--window-size={W},{H}", "--mute-audio",
        "--autoplay-policy=no-user-gesture-required",
        SCENE_URL ]
    return subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

def discover_ws_url(port, timeout=20):
    """Query Chrome's /json/version endpoint for the WebSocket debugger URL."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            conn = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
            conn.request("GET", "/json/version")
            resp = conn.getresponse()
            body = resp.read().decode()
            conn.close()
            data = json.loads(body)
            ws = data.get("webSocketDebuggerUrl")
            if ws:
                return ws
        except Exception:
            pass
        time.sleep(0.5)
    raise RuntimeError(f"CDP not ready on port {port}")

def ws_handshake(host, port, path):
    """Perform a raw WebSocket handshake (RFC 6455)."""
    sock = socket.create_connection((host, port), timeout=10)
    sock.settimeout(10)
    key = base64.b64encode(os.urandom(16)).decode()
    req = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    )
    sock.sendall(req.encode())
    resp = b""
    while b"\r\n\r\n" not in resp:
        resp += sock.recv(4096)
    return sock

def read_ws_frame(sock):
    """Read and parse a WebSocket frame."""
    hdr = sock.recv(2)
    if len(hdr) < 2:
        return None
    opcode = hdr[1] & 0x0F
    masked = bool(hdr[1] & 0x80)
    length = hdr[0] & 0x7F
    if length == 126:
        length = int.from_bytes(sock.recv(2), "big")
    elif length == 127:
        length = int.from_bytes(sock.recv(8), "big")
    data = b""
    if length > 0:
        while len(data) < length:
            chunk = sock.recv(length - len(data))
            if not chunk:
                break
            data += chunk
    if masked:
        mask = sock.recv(4)
        data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
    if opcode == 8:
        return None
    if opcode in (1, 2) and data.strip():
        return json.loads(data.decode())
    return None

def send_ws(sock, obj):
    """Send a JSON object as a masked WebSocket text frame."""
    payload = json.dumps(obj).encode()
    frame = bytearray([0x81])
    if len(payload) < 126:
        frame.append(0x80 | len(payload))
    elif len(payload) < 65536:
        frame.append(0x80 | 126)
        frame += len(payload).to_bytes(2, "big")
    else:
        frame.append(0x80 | 127)
        frame += len(payload).to_bytes(8, "big")
    mask = os.urandom(4)
    frame += mask
    frame += bytes(b ^ mask[i % 4] for i, b in enumerate(payload))
    sock.sendall(frame)

def cdp_call(ws, msg_id, method, params=None):
    """Send a CDP command and wait for the response with matching id."""
    send_ws(ws, {"id": msg_id, "method": method, "params": params or {}})
    deadline = time.time() + 10
    while time.time() < deadline:
        r, _, _ = select.select([ws], [], [], 0.5)
        if not r:
            continue
        msg = read_ws_frame(ws)
        if msg and msg.get("id") == msg_id:
            return msg
    return {"error": "timeout"}

def main():
    tmp = tempfile.mkdtemp(prefix="fleetwaves_")
    httpd = start_http_server()
    time.sleep(0.3)

    chrome = start_chrome(9222)
    print(f"Chrome (pid={chrome.pid}) starting...")

    frames = []
    try:
        ws_url = discover_ws_url(9222)
        # Parse ws://127.0.0.1:9222/devtools/page/TARGET_ID
        u = ws_url.split("ws://")[-1].split("wss://")[-1]
        host_port, path = u.split("/", 1)
        host, port_str = host_port.rsplit(":", 1)
        ws = ws_handshake(host, int(port_str), "/" + path)
        print("WebSocket handshake ✓")

        # Enable domains
        cdp_call(ws, 1, "Runtime.enable")
        cdp_call(ws, 2, "Page.enable")
        cdp_call(ws, 3, "Network.enable")

        # Wait for GSAP timeline registration
        print("Waiting for GSAP timeline...")
        for _ in range(400):
            resp = cdp_call(ws, 4, "Runtime.evaluate", {
                "expression": "typeof window.__timelines !== 'undefined' && window.__timelines['fleet-waves-dev'] ? 'READY' : 'WAIT'",
                "returnByValue": True
            })
            val = resp.get("result",{}).get("result",{}).get("value","")
            if val == "READY":
                print("Timeline registered ✓")
                break
            time.sleep(0.1)
        else:
            print("Timeline not found — rendering anyway")

        n = int(DURATION * FPS)
        print(f"Capturing {n} frames @ {FPS}fps...")

        for i in range(n):
            progress = (i / FPS) / DURATION
            # Seek GSAP timeline
            cdp_call(ws, 1000 + i, "Runtime.evaluate", {
                "expression": f"var tl=window.__timelines&&window.__timelines['fleet-waves-dev'];if(tl)tl.pause({progress});",
                "returnByValue": True
            })
            time.sleep(0.015)

            # Screenshot
            resp = cdp_call(ws, 2000 + i, "Page.captureScreenshot", {
                "format": "png", "quality": 100,
                "clip": {"x": 0, "y": 0, "width": W, "height": H, "scale": 1}
            })
            b64 = resp.get("result", {}).get("data", "")
            if b64:
                data = base64.b64decode(b64)
                fpath = os.path.join(tmp, f"{i:05d}.png")
                with open(fpath, "wb") as f:
                    f.write(data)
                frames.append(fpath)
            if (i + 1) % 30 == 0:
                print(f"  {int((i+1)/n*100)}%  ({i+1}/{n} frames)")

        ws.close()
        print(f"Captured {len(frames)} frames. Encoding MP4...")

        # ffmpeg concat → NVENC
        list_file = os.path.join(tmp, "list.txt")
        with open(list_file, "w") as f:
            for fp in frames:
                f.write(f"file '{fp}'\n")
                f.write("duration 0.033\n")

        os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
        cmd = [FFMPEG, "-y", "-f", "concat", "-safe", 0, "-i", list_file,
               "-c:v", "h264_nvenc", "-b:v", "6M", "-pix_fmt", "yuv420p",
               "-r", str(FPS), "-vf", "format=yuv420p", OUTPUT]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if r.returncode != 0 and "nvenc" in r.stderr.lower():
            print("NVENC unavailable, falling back to libx264...")
            cmd = [c if c != "h264_nvenc" else "libx264" for c in cmd]
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=300)

        if os.path.exists(OUTPUT) and os.path.getsize(OUTPUT) > 0:
            sz = os.path.getsize(OUTPUT)
            print(f"✅ {OUTPUT}  ({sz/1024/1024:.1f} MB)")
        else:
            print(f"❌ Output failed. stderr: {r.stderr[-500:]}")

    finally:
        chrome.terminate()
        try: chrome.wait(timeout=5)
        except: chrome.kill()
        httpd.shutdown()

if __name__ == "__main__":
    main()
