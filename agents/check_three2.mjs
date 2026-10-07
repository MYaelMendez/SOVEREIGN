// Test both three-test.html and three-test2.html
const res = await (await fetch("http://127.0.0.1:9334/json/list")).text();
const tabs = JSON.parse(res);
const page = tabs.find(t => t.type === "page");
console.log("Page:", page.title, "(URL:", page.url, ")");

const ws = new WebSocket(page.webSocketDebuggerUrl);
const pending = new Map();
let msgId = 0;

const send = (method, params = {}) => {
  const id = ++msgId;
  const fut = new Promise((resolve) => pending.set(id, resolve));
  ws.send(JSON.stringify({ method, params, id }));
  return fut;
};

const errors = [];

ws.addEventListener("message", (event) => {
  const m = JSON.parse(event.data);
  if (m.id && pending.has(m.id)) {
    pending.get(m.id)(m);
    pending.delete(m.id);
  }
  if (m.method === "Runtime.exceptionThrown") {
    const t = m.params?.exceptionDetails?.text || "";
    errors.push(t.substring(0, 300));
  }
  if (m.method === "Runtime.consoleAPICalled") {
    const lvl = m.params?.level || "";
    const txt = (m.params?.args || []).map(a => JSON.stringify(a.value)).join(" ");
    errors.push("[" + lvl + "] " + txt.substring(0, 200));
  }
});

ws.addEventListener("error", (e) => console.log("WS error:", e.message || e));

const wait = (ms) => new Promise(r => setTimeout(r, ms));

ws.addEventListener("open", async () => {
  try {
    await send("Runtime.enable");
    await send("Page.enable");
    
    // Navigate to three-test2.html (absolute URL in importmap)
    await send("Page.navigate", { url: "http://127.0.0.1:8125/aipodcast_me/three-test2.html" });
    console.log("Navigated to three-test2.html, waiting 3s...");
    await wait(3000);
    
    console.log("\n=== three-test2.html (absolute importmap) ===");
    const checks = [
      ["statusText", "document.getElementById('status')?.textContent || 'not found'"],
      ["typeof THREE", "typeof THREE"],
      ["THREE.REVISION", "THREE?.REVISION"],
      ["WebGLRenderer", "typeof THREE?.WebGLRenderer"],
    ];
    
    for (const [label, expr] of checks) {
      const r = await send("Runtime.evaluate", { expression: expr });
      const v = r?.result?.result?.value ?? "(none)";
      console.log("  " + label + ": " + JSON.stringify(v));
    }
    
    if (errors.length) {
      console.log("\n=== Errors ===");
      for (const e of errors) console.log("  ", e);
    } else {
      console.log("\nNo errors captured");
    }
    
    ws.close();
    process.exit(0);
  } catch (e) {
    console.log("Error:", e.message);
    ws.close();
    process.exit(1);
  }
});
