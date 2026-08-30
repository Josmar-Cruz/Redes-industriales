const log = document.getElementById("log");
const btnOn1 = document.getElementById("btnOn1");
const btnOff1 = document.getElementById("btnOff1");
const btnOn2 = document.getElementById("btnOn2");
const btnOff2 = document.getElementById("btnOff2");

function writeLog(msg) {
  log.textContent = msg + "\n" + log.textContent;
}

async function setLed(led, state) {
  const r = await fetch("/set_led", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ led, state })
  });
  const j = await r.json();
  if (j.ok) writeLog(`${j.cmd} -> ${j.resp}`);
  else writeLog(`ERROR -> ${j.error || j.resp}`);
}

btnOn1.addEventListener("click", () => setLed(1, 1));
btnOff1.addEventListener("click", () => setLed(1, 0));
btnOn2.addEventListener("click", () => setLed(2, 1));
btnOff2.addEventListener("click", () => setLed(2, 0));
