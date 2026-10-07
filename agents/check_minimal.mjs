// Test minimal ES module execution in headless Chrome
const tabs = JSON.parse(await (await fetch("http://127.0.0.1:9335/json/list")).text());
const page = tabs.find(t => t.type === "page");
console.log("Opened:", page?.url);

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
    console.log("  EXCEPTION:", m.params?.exceptionDetails?.text?.substring(0, 300));
  }
  if (m.method === "Runtime.consoleAPICalled") {
    const lvl = m.params?.level || "";
    const txt = (m.params?.args || []).map(a => JSON.stringify(a.value || "")).join(" ");
    console.log("  CONSOLE[" + lvl + "]:", txt.substring(0, 200));
  }
});

const wait = (ms) => new Promise(r => setTimeout(r, ms));

ws.addEventListener("open", async () => {
  try {
    await send("Runtime.enable");
    await send("Page.enable");
    await wait(3000);

    console.log("\n=== Minimal Module Test ===");
    const r = await send("Runtime.evaluate", { expression: "document.getElementById('status')?.textContent || 'none'" });
    console.log("  statusText:", r?.result?.result?.value ?? "(no-response)");

    ws.close();
    process.exit(0);
  } catch (e) {
    console.log("Error:", e.message);
    ws.close();
    process.exit(1);
  }
});
