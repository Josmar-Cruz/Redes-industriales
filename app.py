from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import check_password_hash
import socket

APP_USER = "MYBLOOD"
APP_PW_HASH = "scrypt:32768:8:1$Um1YuR5zCEhSUtwh$8e8f4da23c986e2830337ac83b27ed297631d8d1fb7d452ca6347bb09e625a2b72ebb04efbc4c9476a1ed2b64b2f52088902e83cc4e87633db25c1e8d39fa794"
SECRET_KEY = "REDES"

TCP_HOST = "127.0.0.1"
TCP_PORT = 5001

app = Flask(__name__)
app.secret_key = SECRET_KEY

def is_logged_in():
    return session.get("logged_in") is True

def send_cmd(cmd: str) -> str:
    with socket.create_connection((TCP_HOST, TCP_PORT), timeout=3) as s:
        s.sendall((cmd + "\n").encode("utf-8"))
        return s.recv(1024).decode("utf-8", errors="ignore").strip()

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = request.form.get("username", "").strip()
        pw = request.form.get("password", "")
        if user == APP_USER and check_password_hash(APP_PW_HASH, pw):
            session["logged_in"] = True
            return redirect(url_for("index"))
        return render_template("login.html", error="Usuario o contraseña incorrectos")
    return render_template("login.html", error=None)

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/")
def index():
    if not is_logged_in():
        return redirect(url_for("login"))
    return render_template("index.html")

@app.post("/set_led")
def set_led():
    if not is_logged_in():
        return jsonify({"ok": False, "error": "No autorizado"}), 401

    data = request.get_json(silent=True) or {}
    led = str(data.get("led", "")).strip()
    state = str(data.get("state", "")).strip()

    if led not in ("1", "2"):
        return jsonify({"ok": False, "error": "Usa led=1 o led=2"}), 400
    if state not in ("0", "1"):
        return jsonify({"ok": False, "error": "Usa state=0 o state=1"}), 400

    cmd = "LED" + led + ("_ON" if state == "1" else "_OFF")

    try:
        resp = send_cmd(cmd)
    except OSError as e:
        return jsonify({"ok": False, "error": "No se pudo conectar al servidor TCP: " + str(e)}), 500

    return jsonify({"ok": True, "cmd": cmd, "resp": resp})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
