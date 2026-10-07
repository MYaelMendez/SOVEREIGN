// Test three.global.js (non-module script) in headless Chrome
const tabs = JSON.parse(await (await fetch("http://127.0.0.1:9444/json/list")).text());
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

const consoleMsgs = [];

ws.addEventListener("message", (event) => {
  const m = JSON.parse(event.data);
  if (m.id && pending.has(m.id)) {
    pending.get(m.id)(m);
    pending.delete(m.id);
  }
  if (m.method === "Runtime.consoleAPICalled") {
    const lvl = m.params?.level || "";
    const txt = (m.params?.args || []).map(a => a.value ?? "").join(" ");
    consoleMsgs.push("[" + lvl + "] " + txt.substring(0, 250));
  }
  if (m.method === "Runtime.exceptionThrown") {
    consoleMsgs.push("[EXCEPTION] " + (m.params?.exceptionDetails?.text || "").substring(0, 300));
  }
});

const wait = (ms) => new Promise(r => setTimeout(r, ms));

ws.addEventListener("open", async () => {
  try {
    await send("Runtime.enable");
    await send("Page.enable");
    await send("Page.navigate", { url: "http://127.0.0.1:8125/aipodcast_me/three-global-test.html" });
    console.log("Navigated, waiting 5s...");
    await wait(5000);

    console.log("\n=== Console Messages ===");
    if (consoleMsgs.length === 0) {
      console.log("  (none captured)");
    } else {
      for (const m of consoleMsgs) console.log("  " + m);
    }

    console.log("\n=== Status Check ===");
    const r = await send("Runtime.evaluate", { expression: "document.getElementById('status')?.textContent || 'NOT_FOUND'" });
    console.log("  statusText:", r?.result?.result?.value ?? "(no-response)");

    const r2 = await send("Runtime.evaluate", { expression: "typeof window.THREE" });
    console.log("  window.THREE:", r2?.result?.result?.value ?? "(no-response)");

    ws.close();
    process.exit(0);
  } catch (e) {
    console.log("Error:", e.message);
    ws.close();
    process.exit(1);
  }
});
