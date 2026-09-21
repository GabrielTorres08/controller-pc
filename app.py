import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, render_template

load_dotenv(Path(__file__).with_name(".env"))

app = Flask(__name__)

TOKEN = os.getenv("GITHUB_TOKEN", "")
OWNER = os.getenv("GITHUB_OWNER", "")
REPO = os.getenv("GITHUB_REPO", "Terraria_Server2")
CODESPACE_NAME = os.getenv("CODESPACE_NAME", "")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "8080"))
START_TIMEOUT = int(os.getenv("START_TIMEOUT", "180"))
POLL_INTERVAL = int(os.getenv("POLL_INTERVAL", "5"))

API = "https://api.github.com"
HEADERS = {
    "Accept": "application/vnd.github+json",
    "Authorization": f"Bearer {TOKEN}",
    "X-GitHub-Api-Version": "2022-11-28",
}

def config_error():
    missing = []
    for key, value in {
        "GITHUB_TOKEN": TOKEN,
        "GITHUB_OWNER": OWNER,
        "CODESPACE_NAME": CODESPACE_NAME,
    }.items():
        if not value:
            missing.append(key)
    return missing

def github_request(method, path, **kwargs):
    if config_error():
        raise RuntimeError("Configure o arquivo .env antes de usar o controlador.")
    response = requests.request(
        method,
        API + path,
        headers=HEADERS,
        timeout=30,
        **kwargs,
    )
    if not response.ok:
        try:
            detail = response.json()
        except Exception:
            detail = response.text
        raise RuntimeError(f"GitHub API {response.status_code}: {detail}")
    if response.text:
        return response.json()
    return {}

def get_codespace():
    return github_request(
        "GET",
        f"/user/codespaces/{CODESPACE_NAME}",
    )

def get_codespace_state():
    data = get_codespace()
    return {
        "name": data.get("name"),
        "state": data.get("state"),
        "machine": data.get("machine", {}).get("display_name")
            if isinstance(data.get("machine"), dict) else data.get("machine"),
        "web_url": data.get("web_url"),
        "repository": data.get("repository", {}).get("full_name")
            if isinstance(data.get("repository"), dict) else None,
    }

def start_codespace():
    return github_request(
        "POST",
        f"/user/codespaces/{CODESPACE_NAME}/start",
    )

def stop_codespace():
    return github_request(
        "POST",
        f"/user/codespaces/{CODESPACE_NAME}/stop",
    )

@app.get("/")
def index():
    return render_template("index.html")

@app.get("/api/status")
def api_status():
    try:
        return jsonify({"ok": True, "codespace": get_codespace_state()})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

@app.post("/api/codespace/start")
def api_start():
    try:
        data = get_codespace_state()
        if data["state"] == "Available":
            return jsonify({"ok": True, "message": "Codespace já está disponível.", "codespace": data})

        start_codespace()

        deadline = time.time() + START_TIMEOUT
        last = data
        while time.time() < deadline:
            time.sleep(POLL_INTERVAL)
            last = get_codespace_state()
            if last["state"] == "Available":
                return jsonify({
                    "ok": True,
                    "message": "Codespace iniciado.",
                    "codespace": last,
                })

        return jsonify({
            "ok": False,
            "error": f"Timeout aguardando Codespace. Estado atual: {last['state']}",
            "codespace": last,
        }), 504
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

@app.post("/api/codespace/stop")
def api_stop():
    try:
        stop_codespace()
        return jsonify({"ok": True, "message": "Solicitação de parada enviada."})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500

@app.post("/api/server/start")
def api_server_start():
    # Esta rota prepara a próxima etapa. O GitHub Codespaces não oferece,
    # neste fluxo, uma execução arbitrária de shell pelo endpoint de start.
    return jsonify({
        "ok": False,
        "error": (
            "Codespace iniciado, mas a execução automática do script interno "
            "ainda precisa ser configurada. Veja README.md."
        ),
    }), 501

@app.post("/api/server/stop")
def api_server_stop():
    return jsonify({
        "ok": False,
        "error": "A parada interna do Terraria será conectada na próxima etapa.",
    }), 501

if __name__ == "__main__":
    app.run(host=HOST, port=PORT, debug=False)
