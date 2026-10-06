const rpmEl = document.getElementById("rpm");
const pwmEl = document.getElementById("pwm");
const errEl = document.getElementById("err");
const sentidoEl = document.getElementById("sentido");
const spEl = document.getElementById("sp");
const spTxt = document.getElementById("spTxt");
const statusEl = document.getElementById("status");
const statusTxt = document.getElementById("statusTxt");
const logEl = document.getElementById("log");
const arco = document.getElementById("arco");
const marcaEl = document.getElementById("marca");
const muestrasEl = document.getElementById("muestras");
const kpEl = document.getElementById("kp");
const kiEl = document.getElementById("ki");
const kdEl = document.getElementById("kd");
const btnExcel = document.getElementById("btnExcel");
const grafica = document.getElementById("grafica");
const ctx = grafica.getContext("2d");

const RPM_MAX = 300;   // igual que en servidor_tcp.py

const lado = { ADELANTE: "DERECHA", ATRAS: "IZQUIERDA", PARAR: "PARADO" };

let dirActual = "PARAR";
let histRpm = [];
let histSp = [];
let pidiendo = false;
let primera = true;

const largo = arco.getTotalLength();
arco.style.strokeDasharray = largo;
arco.style.strokeDashoffset = largo;

function log(t) {
  const hora = new Date().toLocaleTimeString();
  const linea = document.createElement("div");
  linea.textContent = `> [${hora}] ${t}`;
  logEl.prepend(linea);
  while (logEl.children.length > 6) logEl.lastChild.remove();
}

function setLink(ok, t) {
  statusEl.classList.toggle("mal", !ok);
  statusTxt.textContent = t;
}

function pintarSp() {
  spTxt.textContent = spEl.value;
  spEl.style.setProperty("--p", (spEl.value / RPM_MAX * 100) + "%");
}

function marca(rpm) {
  const f = Math.min(rpm / RPM_MAX, 1);
  const a = Math.PI * (1 - f);
  marcaEl.setAttribute("x1", 110 + 76 * Math.cos(a));
  marcaEl.setAttribute("y1", 110 - 76 * Math.sin(a));
  marcaEl.setAttribute("x2", 110 + 104 * Math.cos(a));
  marcaEl.setAttribute("y2", 110 - 104 * Math.sin(a));
}

function marcarDir() {
  document.querySelectorAll(".dir").forEach(b => {
    b.classList.toggle("activo", b.dataset.dir === dirActual);
  });
  const nombres = { ADELANTE: "derecha", ATRAS: "izquierda", PARAR: "parado" };
  sentidoEl.textContent = nombres[dirActual] || dirActual;
}

async function post(url, body) {
  const res = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {})
  });
  if (res.status === 401) {
    window.location.href = "/login";
    return null;
  }
  return res.json();
}

async function mandar(dir, sp) {
  try {
    const data = await post("/api/motor", { dir, sp });
    if (!data) return;
    if (data.ok) {
      dirActual = data.dir;
      marcarDir();
      log(`MOTOR ${lado[data.dir] || data.dir} setpoint ${data.sp.toFixed(0)} rpm`);
    } else {
      log(`ERR ${data.resp || data.error}`);
    }
  } catch (e) {
    log(`ERR ${e}`);
  }
}

async function aplicarPid() {
  try {
    const data = await post("/api/pid", { kp: kpEl.value, ki: kiEl.value, kd: kdEl.value });
    if (!data) return;
    if (data.ok) log(`PID Kp=${data.kp} Ki=${data.ki} Kd=${data.kd}`);
    else log(`ERR ${data.resp || data.error}`);
  } catch (e) {
    log(`ERR ${e}`);
  }
}

async function limpiar() {
  if (!confirm("¿Borrar todos los datos registrados?")) return;
  const data = await post("/api/limpiar");
  if (data && data.ok) {
    muestrasEl.textContent = 0;
    log("registro borrado, t = 0");
  }
}

async function exportar() {
  btnExcel.disabled = true;
  log("generando excel...");

  try {
    const res = await fetch("/api/exportar");

    if (res.status === 401) {
      window.location.href = "/login";
      return;
    }

    if (!res.ok) {
      const d = await res.json().catch(() => ({}));
      log(`ERR ${d.error || res.status}`);
      return;
    }

    const blob = await res.blob();
    const cab = res.headers.get("Content-Disposition") || "";
    const m = cab.match(/filename="?([^";]+)"?/);
    const nombre = m ? m[1] : "motor_pid.xlsx";

    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = nombre;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 2000);

    log(`descargado ${nombre}`);
  } catch (e) {
    log(`ERR ${e}`);
  } finally {
    btnExcel.disabled = false;
  }
}

async function estado() {
  if (pidiendo) return;
  pidiendo = true;

  try {
    const res = await fetch("/api/estado");
    if (res.status === 401) {
      window.location.href = "/login";
      return;
    }

    const data = await res.json();
    if (data.ok) {
      setLink(true, "link ok");
      rpmEl.textContent = data.rpm.toFixed(0);
      pwmEl.textContent = data.pwm.toFixed(0);
      errEl.textContent = data.err.toFixed(1);
      muestrasEl.textContent = data.muestras;
      document.getElementById("tp").textContent = data.p.toFixed(2);
      document.getElementById("ti").textContent = data.i.toFixed(2);
      document.getElementById("td").textContent = data.d.toFixed(2);

      arco.style.strokeDashoffset = largo * (1 - Math.min(data.rpm / RPM_MAX, 1));
      marca(data.sp);

      if (primera) {
        kpEl.value = data.kp;
        kiEl.value = data.ki;
        kdEl.value = data.kd;
        if (data.dir !== "PARAR") {
          spEl.value = data.sp;
          pintarSp();
        }
        primera = false;
      }

      if (data.dir !== dirActual) {
        dirActual = data.dir;
        marcarDir();
      }

      histRpm.push(data.rpm);
      histSp.push(data.sp);
      if (histRpm.length > 100) {
        histRpm.shift();
        histSp.shift();
      }
      dibujar();
    } else {
      setLink(false, "sin señal");
    }
  } catch (e) {
    setLink(false, "sin señal");
  }

  pidiendo = false;
}

function dibujar() {
  const w = grafica.width;
  const h = grafica.height;
  ctx.clearRect(0, 0, w, h);

  ctx.strokeStyle = "rgba(0,240,255,.08)";
  ctx.lineWidth = 1;
  for (let x = 0; x <= w; x += 60) {
    ctx.beginPath();
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
    ctx.stroke();
  }
  for (let y = 0; y <= h; y += 55) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  }

  const tope = Math.max(50, ...histRpm, ...histSp) * 1.2;
  ctx.fillStyle = "#7d86a8";
  ctx.font = "14px 'Share Tech Mono', monospace";
  ctx.fillText(tope.toFixed(0) + " rpm", 8, 18);

  if (histRpm.length < 2) return;

  const paso = w / 99;
  const yv = v => h - (v / tope) * (h - 10);

  ctx.beginPath();
  histSp.forEach((v, i) => (i === 0 ? ctx.moveTo(i * paso, yv(v)) : ctx.lineTo(i * paso, yv(v))));
  ctx.strokeStyle = "#f3e600";
  ctx.lineWidth = 2;
  ctx.setLineDash([8, 6]);
  ctx.stroke();
  ctx.setLineDash([]);

  ctx.beginPath();
  ctx.moveTo(0, h);
  histRpm.forEach((v, i) => ctx.lineTo(i * paso, yv(v)));
  ctx.lineTo((histRpm.length - 1) * paso, h);
  ctx.closePath();
  ctx.fillStyle = "rgba(0,240,255,.1)";
  ctx.fill();

  ctx.beginPath();
  histRpm.forEach((v, i) => (i === 0 ? ctx.moveTo(i * paso, yv(v)) : ctx.lineTo(i * paso, yv(v))));
  ctx.strokeStyle = "#00f0ff";
  ctx.lineWidth = 2;
  ctx.shadowColor = "#00f0ff";
  ctx.shadowBlur = 10;
  ctx.stroke();
  ctx.shadowBlur = 0;
}

spEl.addEventListener("input", pintarSp);

spEl.addEventListener("change", () => {
  if (dirActual !== "PARAR") mandar(dirActual, Number(spEl.value));
});

document.querySelectorAll(".presets .btn").forEach(b => {
  b.addEventListener("click", () => {
    spEl.value = b.dataset.v;
    pintarSp();
    if (dirActual !== "PARAR") mandar(dirActual, Number(spEl.value));
  });
});

document.querySelectorAll(".dir").forEach(b => {
  b.addEventListener("click", () => {
    const dir = b.dataset.dir;
    mandar(dir, dir === "PARAR" ? 0 : Number(spEl.value));
  });
});

document.getElementById("btnPid").addEventListener("click", aplicarPid);
document.getElementById("btnLimpiar").addEventListener("click", limpiar);
btnExcel.addEventListener("click", exportar);

// espacio = paro de emergencia (menos cuando escribes las constantes)
document.addEventListener("keydown", e => {
  if (e.code === "Space" && e.target.type !== "number") {
    e.preventDefault();
    if (document.activeElement) document.activeElement.blur();
    mandar("PARAR", 0);
  }
});

// Inicial
pintarSp();
marcarDir();
marca(0);
dibujar();
estado();
setInterval(estado, 300);
