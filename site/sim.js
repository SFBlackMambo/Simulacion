// Animación de la simulación en el navegador. El simulador (Python) corre en worker.js; aquí solo se dibuja.

const COL = {
  fondo: "#1a1a19", asfalto: "#383835", borde: "#52514e", texto: "#f0efec", texto2: "#c3c2b7",
  linea: "#f0efec", amarillo: "#c98500", curva: "#282826", perfil: "#222221",
};
const COLOR_ESTADO = ["#3987e5", "#c3c2b7", "#199e70", "#d95926"]; // libre, atrapado, rebasando, sonda
const N = 11; // números por vehículo (ver trafico/web.py: SimWeb.estado)
const VELOCIDADES = [1, 2, 5, 10, 20, 50];

const $ = (s) => document.querySelector(s);
const lienzo = $("#lienzo");
const ctx = lienzo.getContext("2d");
const form = $("#controles");

let worker = null;
let geo = null; // geometría de la carretera
let estado = new Float64Array(0);
let info = null;
let esperando = false; // hay un "avanzar" en camino
let acumulado = 0; // segundos simulados pendientes
let pausa = false;
let ventana = 800; // m visibles en el tramo ampliado
let centro = 0;
let seguir = true;
let ultimo = performance.now();

// ---------------------------------------------------------------- worker
function arrancarWorker() {
  worker = new Worker("worker.js", { type: "module" });
  worker.onmessage = (ev) => {
    const m = ev.data;
    if (m.tipo === "cargando") {
      $("#cargando").textContent = m.texto;
    } else if (m.tipo === "geometria") {
      geo = m.g;
      centro = geo.longitud / 2;
      ventana = Math.min(800, geo.longitud);
      $("#modelo").innerHTML = (geo.modelo.length ? geo.modelo : ["modelo simple (todo lo demás apagado)"])
        .map((t) => `<li>${t}</li>`).join("");
      $("#cargando").hidden = true;
      $("#iniciar").disabled = false;
      $("#iniciar").textContent = "Reiniciar con estas opciones";
    } else if (m.tipo === "estado") {
      estado = m.estado;
      info = m.info;
      esperando = false;
      actualizarPaneles();
    } else if (m.tipo === "error") {
      $("#cargando").hidden = false;
      $("#cargando").textContent = "Error: " + m.texto;
      esperando = false;
    }
  };
  iniciar();
}

function opciones() {
  const f = new FormData(form);
  return {
    modo: f.get("modo"),
    vehiculos: Number(f.get("vehiculos")),
    flujo: Number(f.get("flujo")),
    longitud_km: Number(f.get("longitud_km")),
    trazado: f.get("trazado"),
    relieve: f.get("relieve"),
    realista: f.get("realista") === "on",
    camiones: Number(f.get("camiones")) / 100,
    cada_2mas1_km: Number(f.get("cada_2mas1_km")),
    vel_sonda: Number(f.get("vel_sonda")),
    semilla: Number(f.get("semilla")),
  };
}

function iniciar() {
  $("#cargando").hidden = false;
  $("#cargando").textContent = worker && geo ? "Preparando la carretera…" : $("#cargando").textContent;
  geo = null;
  estado = new Float64Array(0);
  info = null;
  acumulado = 0;
  esperando = true;
  seguir = true;
  $("#seguir").classList.add("activo");
  worker.postMessage({ tipo: "iniciar", opciones: opciones() });
}

// ---------------------------------------------------------------- ciclo
function cuadro(ahora) {
  const dt = Math.min(0.1, (ahora - ultimo) / 1000);
  ultimo = ahora;
  if (geo && !pausa) acumulado += dt * Number($("#velocidad").value);
  if (geo && !esperando && acumulado >= 0.2) {
    const s = Math.min(acumulado, 20); // si el navegador no alcanza, se pierde tiempo en vez de trabarse
    acumulado = acumulado > 40 ? 0 : acumulado - s;
    esperando = true;
    worker.postMessage({ tipo: "avanzar", segundos: s });
  }
  dibujar();
  requestAnimationFrame(cuadro);
}

// ---------------------------------------------------------------- paneles (HTML)
const hms = (seg) => {
  seg = Math.max(0, Math.round(seg));
  const h = Math.floor(seg / 3600), m = Math.floor((seg % 3600) / 60), s = seg % 60;
  return h ? `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}` : `${m}:${String(s).padStart(2, "0")}`;
};

function actualizarPaneles() {
  if (!info) return;
  $("#contadores").textContent = `Tiempo ${hms(info.t)} · En la carretera ${info.en_carretera} · Rebases ${info.rebases}`
    + ` · Abortados ${info.abortos} · Colisiones ${info.colisiones}`;
  const a = info.activa;
  if (a) {
    $("#panel-sonda").innerHTML = `<b>Quiere ir a ${a.v0.toFixed(0)} km/h, va a ${a.v.toFixed(0)} km/h</b><br>`
      + `Recorrido ${a.recorrido_km.toFixed(1)} de ${(geo.longitud / 1000).toFixed(0)} km en ${hms(a.t)}<br>`
      + `Tiempo perdido por el tráfico: ${Math.max(0, a.perdido).toFixed(0)} s<br>`
      + `Vehículos rebasados: ${a.rebases} · Veces que tuvo que frenar por otro: ${a.alcances}`;
  } else if (info.proxima != null) {
    $("#panel-sonda").textContent = `La próxima sonda (${geo.v_sonda} km/h) entra en ${hms(info.proxima)}`;
  } else {
    $("#panel-sonda").textContent = "Todas las sondas llegaron.";
  }
  const filas = info.hechas.map((s) => `<tr><td>#${s.n}</td><td>${hms(s.tardo)}</td><td>${hms(s.libre)}</td>`
    + `<td>${s.perdio.toFixed(0)} s</td><td>${s.rebases}</td><td>${s.alcances}</td></tr>`);
  $("#tabla-sondas tbody").innerHTML = filas.join("");
  if (info.hechas.length) {
    const p = info.hechas.reduce((x, s) => x + s.perdio, 0) / info.hechas.length;
    $("#promedio").textContent = `En promedio, cada sonda perdió ${p.toFixed(0)} s por el tráfico.`;
  } else {
    $("#promedio").textContent = "";
  }
}

// ---------------------------------------------------------------- dibujo (canvas)
function ajustarTamano() {
  const ancho = lienzo.clientWidth;
  const conPerfil = geo && geo.perfil.length, tres = geo && geo.carriles_rebase.length;
  const alto = (conPerfil ? 176 : 104) + (tres ? 180 : 120) + 76;
  const r = window.devicePixelRatio || 1;
  if (lienzo.width !== Math.round(ancho * r) || lienzo.height !== Math.round(alto * r)) {
    lienzo.width = Math.round(ancho * r);
    lienzo.height = Math.round(alto * r);
    lienzo.style.height = alto + "px";
  }
  ctx.setTransform(r, 0, 0, r, 0, 0);
  return [ancho, alto];
}

function rect(x, y, w, h, color, radio = 0) {
  ctx.fillStyle = color;
  if (radio) {
    ctx.beginPath();
    ctx.roundRect(x, y, w, h, radio);
    ctx.fill();
  } else {
    ctx.fillRect(x, y, w, h);
  }
}

function texto(t, x, y, color = COL.texto2, tam = 13, alinear = "left", negrita = false) {
  ctx.fillStyle = color;
  ctx.font = `${negrita ? "bold " : ""}${tam}px system-ui, -apple-system, "Segoe UI", sans-serif`;
  ctx.textAlign = alinear;
  ctx.textBaseline = "middle";
  ctx.fillText(t, x, y);
}

function linea(x1, y1, x2, y2, color, ancho = 2) {
  ctx.strokeStyle = color;
  ctx.lineWidth = ancho;
  ctx.beginPath();
  ctx.moveTo(x1, y1);
  ctx.lineTo(x2, y2);
  ctx.stroke();
}

const MAPA = { x: 20, y: 24, alto: 26 };

function zona2mas1(s) {
  for (const [a, b, d] of geo.carriles_rebase) if (a <= s && s < b) return d;
  return 0;
}
const enTramos = (s, tramos) => tramos.some(([a, b]) => a <= s && s < b);

function dibujar() {
  const [w] = ajustarTamano();
  rect(0, 0, w, lienzo.height, COL.fondo);
  if (!geo) return;
  const L = geo.longitud;
  // sonda activa: la vista la sigue
  if (seguir && info && info.activa) centro = info.activa.pos;
  centro = Math.min(L - ventana / 2, Math.max(ventana / 2, centro));
  const izq = centro - ventana / 2;

  // --- mapa de la carretera completa ---
  const mx = MAPA.x, my = MAPA.y, mw = w - 2 * MAPA.x, mh = MAPA.alto;
  rect(mx, my, mw, mh, COL.asfalto, 4);
  for (const [a, b] of geo.curvas) rect(mx + (a / L) * mw, my, Math.max(1, ((b - a) / L) * mw), mh, COL.curva);
  for (const [a, b] of geo.carriles_rebase) rect(mx + (a / L) * mw, my + mh * 0.45, Math.max(1, ((b - a) / L) * mw), 2, COL.linea);
  for (let i = 0; i < estado.length; i += N) {
    const pos = estado[i], carril = estado[i + 1], color = estado[i + 5], sonda = estado[i + 9];
    const py = my + (carril === 1 ? mh * 0.3 : carril >= 2 ? mh * 0.5 : mh * 0.7);
    ctx.fillStyle = COLOR_ESTADO[color];
    ctx.beginPath();
    ctx.arc(mx + (pos / L) * mw, py, sonda ? 4 : 2, 0, 2 * Math.PI);
    ctx.fill();
  }
  ctx.strokeStyle = COL.texto;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.roundRect(mx + (izq / L) * mw, my - 5, Math.max(2, (ventana / L) * mw), mh + 10, 3);
  ctx.stroke();
  const pasoKm = Math.max(1, Math.round(L / 1000 / 10));
  for (let km = 0; km <= L / 1000; km += pasoKm) texto(`${km} km`, mx + ((km * 1000) / L) * mw, my + mh + 14, COL.texto2, 12, "center");

  // --- perfil de alturas ---
  let top = 104;
  if (geo.perfil.length) {
    const py = 96, ph = 40, hs = geo.perfil;
    const hmin = Math.min(...hs), hmax = Math.max(...hs), rango = Math.max(hmax - hmin, 20);
    rect(mx + (izq / L) * mw, py - 2, Math.max(2, (ventana / L) * mw), ph + 4, COL.perfil);
    ctx.strokeStyle = COL.texto2;
    ctx.lineWidth = 2;
    ctx.beginPath();
    hs.forEach((h, i) => {
      const x = mx + (mw * i) / (hs.length - 1), y = py + ph - ((h - hmin) / rango) * ph;
      i ? ctx.lineTo(x, y) : ctx.moveTo(x, y);
    });
    ctx.stroke();
    texto(`perfil de alturas (${rango.toFixed(0)} m de desnivel)`, mx, py - 10, COL.texto2, 12);
    top = 176;
  }

  // --- tramo ampliado ---
  const tres = geo.carriles_rebase.length > 0;
  const altoVia = tres ? 180 : 120;
  const carril = altoVia / (tres ? 3 : 2);
  const vx = 20, vw = w - 40;
  const esc = vw / ventana;
  const X = (s) => vx + (s - izq) * esc;
  texto("← sentido contrario", vx, top - 10, COL.texto2, 12);
  rect(vx, top, vw, altoVia, COL.asfalto);
  ctx.save();
  ctx.beginPath();
  ctx.rect(vx, top - 30, vw, altoVia + 60);
  ctx.clip();
  for (const [a, b, r, vmax] of geo.curvas) {
    if (b > izq && a < izq + ventana) {
      const xa = Math.max(vx, X(a)), xb = Math.min(vx + vw, X(b));
      rect(xa, top, xb - xa, altoVia, COL.curva);
      texto(`curva R = ${r.toFixed(0)} m · máx ${vmax.toFixed(0)} km/h`, xa + 6, top + altoVia + 14, COL.texto2, 12);
    }
  }
  for (const [a, b, g] of geo.pendientes) {
    if (b > izq && a < izq + ventana) {
      texto(`${g > 0 ? "sube" : "baja"} ${Math.abs(100 * g).toFixed(1)} %`, Math.max(vx, X(a)) + 200, top - 10, COL.texto2, 12);
    }
  }
  for (const [a, , lim] of geo.limites) {
    if (a >= izq && a < izq + ventana) {
      const x = X(a) + 16, y = top - 14;
      ctx.fillStyle = COL.texto; ctx.beginPath(); ctx.arc(x, y, 12, 0, 2 * Math.PI); ctx.fill();
      ctx.strokeStyle = "#d03b3b"; ctx.lineWidth = 3; ctx.stroke();
      texto(lim.toFixed(0), x, y + 1, COL.fondo, 11, "center", true);
    }
  }
  // rayas: discontinua, doble amarilla donde no se rebasa y en los tramos 2+1
  const paso = ventana < 3000 ? 12 : 60;
  for (let s = Math.floor(izq / paso) * paso; s < izq + ventana; s += paso) {
    const discontinua = (y) => { if (Math.round(s / paso) % 2 === 0) linea(X(s), y, X(s + paso * 0.6), y, COL.linea); };
    const doble = (y) => { linea(X(s), y - 3, X(s + paso), y - 3, COL.amarillo); linea(X(s), y + 3, X(s + paso), y + 3, COL.amarillo); };
    const z = tres ? zona2mas1(s) : 0;
    if (z === 1) { doble(top + carril); discontinua(top + 2 * carril); }
    else if (z === -1) { discontinua(top + carril); doble(top + 2 * carril); }
    else {
      const ymid = top + (tres ? 1.5 : 1) * carril;
      enTramos(s, geo.no_rebase) ? doble(ymid) : discontinua(ymid);
    }
  }
  linea(vx, top, vx + vw, top, COL.borde);
  linea(vx, top + altoVia, vx + vw, top + altoVia, COL.borde);
  ctx.restore();
  texto("sentido →", vx + vw, top - 10, COL.texto2, 12, "right");

  // vehículos
  ctx.save();
  ctx.beginPath();
  ctx.rect(vx, top, vw, altoVia);
  ctx.clip();
  const altoCoche = carril * 0.36;
  const largoMin = altoCoche * 1.8;
  const yc = (ln) => top + (ln === 1 ? carril * 0.5 : tres && ln >= 2 ? carril * 1.5 : carril * (tres ? 2.5 : 1.5));
  for (let i = 0; i < estado.length; i += N) {
    const [pos, ln, lnPrev, lc, v, color, camion, dir, largoM, sonda] = estado.subarray(i, i + 10);
    const atras = pos - largoM * dir;
    let xa = Math.min(X(pos), X(atras)), xb = Math.max(X(pos), X(atras));
    if (xb < vx || xa > vx + vw) continue;
    const largo = Math.max(xb - xa, largoMin * (camion ? 2.4 : 1));
    if (dir === -1) xa = xb - largo; // el frente queda a la izquierda
    const yv = lc >= 1 ? yc(ln) : yc(lnPrev) + (yc(ln) - yc(lnPrev)) * lc;
    const y = yv - altoCoche / 2;
    rect(xa, y, largo, altoCoche, COLOR_ESTADO[color], 3);
    if (camion) { // cabina: franja oscura en el frente
      const cab = largo * 0.22;
      rect(dir === 1 ? xa + largo - cab + 2 : xa + cab, y, 2, altoCoche, COL.fondo);
    }
    if (sonda) {
      ctx.strokeStyle = COL.texto; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.roundRect(xa - 3, y - 3, largo + 6, altoCoche + 6, 5); ctx.stroke();
    }
    if (largo >= 34) texto(v.toFixed(0), xa + largo / 2, yv + 1, sonda ? COL.texto : COL.fondo, 12, "center");
  }
  ctx.restore();
  if (info && info.activa) { // rótulo de la sonda (fuera del recorte, para que no se corte)
    const x = X(info.activa.pos);
    if (x > vx && x < vx + vw) texto(`SONDA ${info.activa.v0.toFixed(0)} km/h`, x, top + altoVia + 30, COL.texto, 12, "center", true);
  }

  // regla de distancia
  const yreg = top + altoVia + 48;
  const pasoM = [50, 100, 250, 500, 1000, 2000, 5000].find((p) => ventana / p <= 12) || 10000;
  for (let m = Math.ceil(izq / pasoM) * pasoM; m <= izq + ventana; m += pasoM) {
    linea(X(m), yreg, X(m), yreg + 6, COL.borde, 1);
    texto(`${(m / 1000).toFixed(2).replace(/\.?0+$/, "")} km`, X(m), yreg + 16, COL.texto2, 12, "center");
  }
  if (pausa) texto("PAUSA", w / 2, top - 10, COL.texto, 14, "center", true);
}

// ---------------------------------------------------------------- controles
function zoom(f) { if (geo) ventana = Math.min(geo.longitud, Math.max(150, ventana * f)); }
function mover(d) { if (!geo) return; seguir = false; $("#seguir").classList.remove("activo"); centro += d; }
function alternarPausa() { pausa = !pausa; $("#pausa").textContent = pausa ? "Continuar" : "Pausa"; }
function cambiarVelocidad(paso) {
  const sel = $("#velocidad");
  const i = Math.max(0, Math.min(VELOCIDADES.length - 1, VELOCIDADES.indexOf(Number(sel.value)) + paso));
  sel.value = String(VELOCIDADES[i]);
}

// Escenarios listos para mostrar (llenan los controles y arrancan)
const ESCENARIOS = {
  ligero: { modo: "lleno", vehiculos: 15, longitud_km: 8, trazado: "recta", relieve: "plano", realista: true, camiones: 10, cada_2mas1_km: 0 },
  denso: { modo: "lleno", vehiculos: 50, longitud_km: 8, trazado: "recta", relieve: "plano", realista: true, camiones: 10, cada_2mas1_km: 0 },
  "2mas1": { modo: "lleno", vehiculos: 30, longitud_km: 9, trazado: "recta", relieve: "plano", realista: true, camiones: 10, cada_2mas1_km: 3 },
  montana: { modo: "lleno", vehiculos: 20, longitud_km: 8, trazado: "muchas", relieve: "montanoso", realista: true, camiones: 20, cada_2mas1_km: 0 },
};
$("#escenario").addEventListener("change", () => {
  const e = ESCENARIOS[$("#escenario").value];
  if (!e) return;
  for (const [k, v] of Object.entries(e)) {
    const campo = form.elements[k];
    if (campo.type === "checkbox") campo.checked = v; else campo.value = String(v);
  }
  form.modo.dispatchEvent(new Event("change"));
  if (!$("#iniciar").disabled) iniciar();
});
form.addEventListener("input", (e) => { if (e.target.id !== "escenario") $("#escenario").value = "propio"; });

form.addEventListener("submit", (e) => { e.preventDefault(); iniciar(); });
form.modo.addEventListener("change", () => {
  const lleno = form.modo.value === "lleno";
  $("#l-vehiculos").hidden = !lleno;
  $("#l-flujo").hidden = lleno;
});
$("#pausa").addEventListener("click", alternarPausa);
$("#acercar").addEventListener("click", () => zoom(1 / 1.4));
$("#alejar").addEventListener("click", () => zoom(1.4));
$("#seguir").addEventListener("click", () => { seguir = !seguir; $("#seguir").classList.toggle("activo", seguir); });
lienzo.addEventListener("click", (e) => {
  if (!geo) return;
  const r = lienzo.getBoundingClientRect();
  const x = e.clientX - r.left, y = e.clientY - r.top;
  const mw = r.width - 2 * MAPA.x;
  if (y >= MAPA.y - 10 && y <= MAPA.y + MAPA.alto + 10 && x >= MAPA.x && x <= MAPA.x + mw) {
    centro = ((x - MAPA.x) / mw) * geo.longitud;
    seguir = false;
    $("#seguir").classList.remove("activo");
  }
});
lienzo.addEventListener("wheel", (e) => { e.preventDefault(); zoom(e.deltaY < 0 ? 1 / 1.2 : 1.2); }, { passive: false });
document.addEventListener("keydown", (e) => {
  if (e.target.closest("form")) return; // escribiendo en los controles
  const k = e.key;
  if (k === " ") { e.preventDefault(); alternarPausa(); }
  else if (k === "+" || k === "=") cambiarVelocidad(1);
  else if (k === "-") cambiarVelocidad(-1);
  else if (k === "z" || k === "Z") zoom(1 / 1.4);
  else if (k === "x" || k === "X") zoom(1.4);
  else if (k === "ArrowLeft") mover(-0.25 * ventana);
  else if (k === "ArrowRight") mover(0.25 * ventana);
  else if (k === "s" || k === "S") $("#seguir").click();
});

arrancarWorker();
requestAnimationFrame(cuadro);
