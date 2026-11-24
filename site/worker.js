// Corre el simulador (Python, con Pyodide) en segundo plano para que la página no se trabe.
// Mensajes de la página: {tipo: "iniciar", opciones} y {tipo: "avanzar", segundos}.
// Respuestas: {tipo: "cargando", texto}, {tipo: "geometria", g}, {tipo: "estado", estado, info}, {tipo: "error", texto}.
import { loadPyodide } from "https://cdn.jsdelivr.net/pyodide/v314.0.8/full/pyodide.mjs";

let py = null;
let sim = null;
const listo = (async () => {
  postMessage({ tipo: "cargando", texto: "Cargando Python en el navegador…" });
  py = await loadPyodide();
  postMessage({ tipo: "cargando", texto: "Cargando numpy…" });
  await py.loadPackage("numpy");
  postMessage({ tipo: "cargando", texto: "Cargando el simulador…" });
  const archivos = await (await fetch("trafico/archivos.json")).json();
  py.FS.mkdirTree("/home/pyodide/trafico");
  await Promise.all(archivos.map(async (f) => {
    const txt = await (await fetch(`trafico/${f}`)).text();
    py.FS.writeFile(`/home/pyodide/trafico/${f}`, txt);
  }));
  py.runPython(`import sys; sys.path.insert(0, "/home/pyodide")
from trafico.web import SimWeb`);
})();

const aJs = (x) => x.toJs({ dict_converter: Object.fromEntries });

onmessage = async (ev) => {
  const m = ev.data;
  try {
    await listo;
    if (m.tipo === "iniciar") {
      if (sim) sim.destroy();
      const SimWeb = py.globals.get("SimWeb");
      const opciones = py.toPy(m.opciones);
      sim = SimWeb(opciones);
      opciones.destroy();
      SimWeb.destroy();
      const g = sim.geometria();
      postMessage({ tipo: "geometria", g: aJs(g) });
      g.destroy();
      enviarEstado();
    } else if (m.tipo === "avanzar" && sim) {
      sim.avanzar(m.segundos);
      enviarEstado();
    }
  } catch (e) {
    postMessage({ tipo: "error", texto: String(e) });
  }
};

function enviarEstado() {
  const e = sim.estado();
  const arr = new Float64Array(e.toJs());
  e.destroy();
  const i = sim.info();
  const info = aJs(i);
  i.destroy();
  postMessage({ tipo: "estado", estado: arr, info }, [arr.buffer]);
}
