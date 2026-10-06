#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from flask import Flask, render_template, request, redirect, url_for, session, jsonify, send_file
from werkzeug.security import check_password_hash
from datetime import datetime
import socket

try:
    from excel import armar_excel
except ImportError:
    armar_excel = None

# ====== CREDENCIALES ======
APP_USER = "Josmar"
APP_PW_HASH = "scrypt:32768:8:1$lkwNLfjScgXzwkVI$02286186cff58f50536c381a503daf857d0b07e34c808198cb4d813aac94330f50658fd255cb250adaafde54acc1b9876b2e072a03cf76103ed47cefbdc9947b"
SECRET_KEY = "REDES"

# ====== TCP hacia servidor_tcp.py ======
TCP_HOST = "127.0.0.1"
TCP_PORT = 5001

app = Flask(__name__, template_folder="templates", static_folder="static", static_url_path="/static")
app.secret_key = SECRET_KEY


def is_logged_in():
    return session.get("logged_in") is True


def send_cmd(cmd: str) -> str:
    with socket.create_connection((TCP_HOST, TCP_PORT), timeout=3) as s:
        s.sendall((cmd.strip() + "\n").encode("utf-8"))
        data = b""
        while b"\n" not in data:
            chunk = s.recv(1024)
            if not chunk:
                break
            data += chunk
        return data.decode("utf-8", errors="ignore").strip()


def pedir_datos():
    with socket.create_connection((TCP_HOST, TCP_PORT), timeout=5) as s:
        s.sendall(b"DATOS\n")
        data = b""
        while not data.endswith(b"FIN\n"):
            chunk = s.recv(65536)
            if not chunk:
                break
            data += chunk
    lineas = data.decode("utf-8", errors="ignore").splitlines()
    return [l for l in lineas if l and l != "FIN"]


def leer_resp(resp):
    # OK dir sp rpm pwm err p i d kp ki kd pulsos muestras
    p = resp.split()
    if len(p) == 14 and p[0] == "OK":
        return {
            "ok": True, "dir": p[1],
            "sp": float(p[2]), "rpm": float(p[3]), "pwm": float(p[4]), "err": float(p[5]),
            "p": float(p[6]), "i": float(p[7]), "d": float(p[8]),
            "kp": float(p[9]), "ki": float(p[10]), "kd": float(p[11]),
            "pulsos": int(p[12]), "muestras": int(p[13]),
            "resp": resp,
        }
    return {"ok": False, "resp": resp}


def mandar(cmd):
    try:
        return jsonify(leer_resp(send_cmd(cmd)))
    except OSError as e:
        return jsonify({"ok": False, "resp": f"sin conexion con servidor_tcp.py ({e})"})


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


@app.post("/api/motor")
def motor():
    if not is_logged_in():
        return jsonify({"ok": False, "error": "No autorizado"}), 401

    data = request.get_json(silent=True) or {}
    direccion = str(data.get("dir", "PARAR")).upper()
    if direccion not in ("ADELANTE", "ATRAS", "PARAR"):
        return jsonify({"ok": False, "error": "direccion no valida"}), 400

    try:
        sp = float(data.get("sp", 0))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "setpoint no valido"}), 400

    return mandar(f"MOTOR {direccion} {sp:.0f}")


@app.post("/api/pid")
def pid():
    if not is_logged_in():
        return jsonify({"ok": False, "error": "No autorizado"}), 401

    data = request.get_json(silent=True) or {}
    try:
        kp = float(data.get("kp"))
        ki = float(data.get("ki"))
        kd = float(data.get("kd"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "constantes no validas"}), 400

    if min(kp, ki, kd) < 0:
        return jsonify({"ok": False, "error": "las constantes no pueden ser negativas"}), 400

    return mandar(f"PID {kp:g} {ki:g} {kd:g}")


@app.get("/api/estado")
def estado():
    if not is_logged_in():
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return mandar("ESTADO")


@app.post("/api/limpiar")
def limpiar():
    if not is_logged_in():
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return mandar("LIMPIAR")


@app.get("/api/exportar")
def exportar():
    if not is_logged_in():
        return jsonify({"ok": False, "error": "No autorizado"}), 401

    if armar_excel is None:
        return jsonify({"ok": False, "error": "falta openpyxl, instala con: sudo apt install -y python3-openpyxl"}), 500

    try:
        lineas = pedir_datos()
        est = leer_resp(send_cmd("ESTADO"))
    except OSError as e:
        return jsonify({"ok": False, "error": f"sin conexion con servidor_tcp.py ({e})"}), 500

    if not lineas:
        return jsonify({"ok": False, "error": "no hay datos, mueve el motor primero"}), 400

    archivo = armar_excel(lineas, est)
    nombre = datetime.now().strftime("motor_pid_%Y-%m-%d_%H-%M-%S.xlsx")
    return send_file(
        archivo,
        as_attachment=True,
        download_name=nombre,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
