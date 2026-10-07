// CDP verify for three-test.html - using Node 26 native WebSocket
const res = await (await fetch("http://127.0.0.1:9334/json/list")).text();
const tabs = JSON.parse(res);
const page = tabs.find(t => t.type === "page");
if (!page) {
  console.log("No page target. Available:", tabs.map(t => t.title + " (" + t.type + ")").join(", "));
  process.exit(0);
}
console.log("Page:", page.title);

const ws = new WebSocket(page.webSocketDebuggerUrl);
const pending = new Map();
let msgId = 0;

const send = (method, params = {}) => {
  const id = ++msgId;
  const fut = new Promise((resolve) => pending.set(id, resolve));
  ws.send(JSON.stringify({ method, params, id }));
  return fut;
};

ws.addEventListener("message", (event) => {
  const m = JSON.parse(event.data);
  if (m.id && pending.has(m.id)) {
    pending.get(m.id)(m);
    pending.delete(m.id);
  }
  if (m.method === "Runtime.exceptionThrown") {
    console.log("  EXCEPTION:", m.params?.exceptionDetails?.text?.substring(0, 150));
  }
  if (m.method === "Runtime.consoleAPICalled") {
    const lvl = m.params?.level;
    const txt = (m.params?.args || []).map(a => a.value || "").join(" ");
    console.log("  CONSOLE[" + lvl + "]:", txt.substring(0, 200));
  }
});

ws.addEventListener("error", (e) => console.log("WS error:", e.message || e));

const wait = (ms) => new Promise(r => setTimeout(r, ms));

ws.addEventListener("open", async () => {
  try {
    await send("Runtime.enable");
    await send("Page.enable");
    await wait(3000);

    console.log("\n=== Three.js Module Test ===");
    const checks = [
      ["statusText", "document.getElementById('status')?.textContent || 'not found'"],
      ["typeof THREE", "typeof THREE"],
      ["THREE.REVISION", "THREE.REVISION"],
      ["WebGLRenderer", "typeof THREE?.WebGLRenderer"],
      ["VideoTexture", "typeof THREE?.VideoTexture"],
    ];

    for (const [label, expr] of checks) {
      const r = await send("Runtime.evaluate", { expression: expr });
      const v = r?.result?.result?.value ?? "(none)";
      console.log("  " + label + ": " + JSON.stringify(v));
    }

    ws.close();
    process.exit(0);
  } catch (e) {
    console.log("Error:", e.message);
    ws.close();
    process.exit(1);
  }
});
