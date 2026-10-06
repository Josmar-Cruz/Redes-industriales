#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import socket
import signal
import threading
import time
from collections import deque
from datetime import datetime

import lgpio
from gpiozero import PWMOutputDevice, DigitalOutputDevice

HOST = "0.0.0.0"
PORT = 5001

PIN_ENA = 18
PIN_IN1 = 23
PIN_IN2 = 24
PIN_A = 17

# pulsos del canal A por cada vuelta del eje de salida (11 x la relacion del motor)
PULSOS_VUELTA = 374
DT = 0.1
RPM_MAX = 300

_running = True
_lock = threading.Lock()

ena = PWMOutputDevice(PIN_ENA, frequency=1000)
in1 = DigitalOutputDevice(PIN_IN1)
in2 = DigitalOutputDevice(PIN_IN2)

est = {
    "dir": "PARAR", "sp": 0.0,
    "rpm": 0.0, "pwm": 0.0, "err": 0.0,
    "p": 0.0, "i": 0.0, "d": 0.0,
    "kp": 0.2, "ki": 1.0, "kd": 0.01,
}
pulsos = 0
datos = deque(maxlen=6000)   # 10 min a 10 muestras por segundo
t_ini = None


def handle_sig(*_):
    global _running
    _running = False


def contar(chip, gpio, level, tick):
    global pulsos
    pulsos += 1


def mover(direccion, sp):
    sp = max(0.0, min(float(RPM_MAX), sp))

    with _lock:
        if direccion != est["dir"]:
            est["i"] = 0.0
            # si cambia de sentido, frena tantito antes
            if est["dir"] != "PARAR":
                ena.value = 0
                in1.off()
                in2.off()
                time.sleep(0.2)

        if direccion == "ADELANTE":
            in1.on()
            in2.off()
        elif direccion == "ATRAS":
            in1.off()
            in2.on()
        else:
            in1.off()
            in2.off()
            ena.value = 0
            sp = 0.0

        est["dir"] = direccion
        est["sp"] = sp


def lazo_pid():
    global t_ini
    antes = pulsos
    rpm_ant = 0.0
    t_ant = time.monotonic()

    while _running:
        time.sleep(DT)
        ahora = time.monotonic()
        dt = ahora - t_ant
        t_ant = ahora

        p_ahora = pulsos
        crudo = (p_ahora - antes) / dt * 60 / PULSOS_VUELTA
        antes = p_ahora

        with _lock:
            rpm = 0.6 * crudo + 0.4 * est["rpm"]
            sp = est["sp"]
            err = sp - rpm

            if est["dir"] == "PARAR" or sp <= 0:
                p = i = d = u = 0.0
            else:
                p = est["kp"] * err
                d = -est["kd"] * (rpm - rpm_ant) / dt
                i = est["i"] + est["ki"] * err * dt
                i = max(0.0, min(100.0, i))
                u = p + i + d

                # si ya esta saturado ya no sigue acumulando
                if (u > 100 and err > 0) or (u < 0 and err < 0):
                    i = est["i"]
                    u = p + i + d

                u = max(0.0, min(100.0, u))

            ena.value = u / 100
            est.update(rpm=rpm, err=err, pwm=u, p=p, i=i, d=d)

            if est["dir"] != "PARAR" or rpm > 0.5:
                if t_ini is None:
                    t_ini = ahora
                datos.append((
                    round(ahora - t_ini, 3),
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    est["dir"], round(sp, 1), round(rpm, 2), round(err, 2), round(u, 2),
                    round(p, 3), round(i, 3), round(d, 3),
                    est["kp"], est["ki"], est["kd"],
                ))

        rpm_ant = rpm


def txt_estado():
    e = est
    return (f"OK {e['dir']} {e['sp']:.1f} {e['rpm']:.1f} {e['pwm']:.1f} {e['err']:.1f} "
            f"{e['p']:.2f} {e['i']:.2f} {e['d']:.2f} {e['kp']:g} {e['ki']:g} {e['kd']:g} "
            f"{pulsos} {len(datos)}")


def atender(msg):
    global t_ini
    partes = msg.upper().split()
    if not partes:
        return "ERR vacio"

    if partes[0] == "ESTADO":
        return txt_estado()

    if partes[0] == "MOTOR" and len(partes) == 3:
        direccion = partes[1]
        if direccion not in ("ADELANTE", "ATRAS", "PARAR"):
            return "ERR direccion no valida"
        try:
            sp = float(partes[2])
        except ValueError:
            return "ERR setpoint no valido"
        mover(direccion, sp)
        print(f"[MOTOR] {est['dir']} setpoint {est['sp']:.0f} rpm")
        return txt_estado()

    if partes[0] == "PID" and len(partes) == 4:
        try:
            kp, ki, kd = (float(x) for x in partes[1:])
        except ValueError:
            return "ERR constantes no validas"
        if min(kp, ki, kd) < 0:
            return "ERR las constantes no pueden ser negativas"
        with _lock:
            est.update(kp=kp, ki=ki, kd=kd)
        print(f"[PID] Kp={kp:g} Ki={ki:g} Kd={kd:g}")
        return txt_estado()

    if partes[0] == "LIMPIAR":
        with _lock:
            datos.clear()
            t_ini = None
        print("[DATOS] registro borrado")
        return txt_estado()

    if partes[0] == "DATOS":
        with _lock:
            filas = list(datos)
        return "".join(",".join(str(x) for x in f) + "\n" for f in filas) + "FIN"

    return "ERR comando no valido"


def main():
    global _running
    signal.signal(signal.SIGINT, handle_sig)
    signal.signal(signal.SIGTERM, handle_sig)

    h = lgpio.gpiochip_open(0)
    lgpio.gpio_claim_alert(h, PIN_A, lgpio.RISING_EDGE, lgpio.SET_PULL_UP)
    cb = lgpio.callback(h, PIN_A, lgpio.RISING_EDGE, contar)

    mover("PARAR", 0)
    threading.Thread(target=lazo_pid, daemon=True).start()

    print(f"[MOTOR] ENA=GPIO{PIN_ENA} IN1=GPIO{PIN_IN1} IN2=GPIO{PIN_IN2} encoder A=GPIO{PIN_A}")
    print(f"[PID] Kp={est['kp']} Ki={est['ki']} Kd={est['kd']}  cada {DT} s")

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((HOST, PORT))
        s.listen(5)
        s.settimeout(0.5)

        print(f"[TCP] Escuchando en {HOST}:{PORT}")

        while _running:
            try:
                conn, _ = s.accept()
            except socket.timeout:
                continue

            with conn:
                conn.settimeout(1.0)
                data = b""
                try:
                    while True:
                        chunk = conn.recv(1024)
                        if not chunk:
                            break
                        data += chunk
                        if b"\n" in data:
                            break
                except socket.timeout:
                    pass

                msg = data.decode("utf-8", errors="ignore").strip()
                resp = atender(msg)
                conn.sendall((resp + "\n").encode("utf-8"))

    mover("PARAR", 0)
    ena.value = 0
    cb.cancel()
    lgpio.gpiochip_close(h)
    print("Cerrado limpio, motor parado.")


if __name__ == "__main__":
    main()
