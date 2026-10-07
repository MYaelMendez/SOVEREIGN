// Test three-import-test.html and capture ALL console messages (log, error, warning)
// This tests whether ES module imports work in headless Chrome
const tabs = JSON.parse(await (await fetch("http://127.0.0.1:9334/json/list")).text());
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
  if (m.method === "Runtime.consoleAPICalled" || m.method === "Runtime.exceptionThrown") {
    const lvl = m.params?.level || m.params?.exceptionDetails?.level || m.method;
    let txt = "";
    if (m.method === "Runtime.consoleAPICalled") {
      txt = (m.params?.args || []).map(a => a.value ?? "").join(" ");
    } else {
      txt = m.params?.exceptionDetails?.text || "";
    }
    consoleMsgs.push("[" + lvl + "] " + txt.substring(0, 250));
  }
});

const wait = (ms) => new Promise(r => setTimeout(r, ms));

ws.addEventListener("open", async () => {
  try {
    await send("Runtime.enable");
    await send("Page.enable");
    await send("Page.navigate", { url: "http://127.0.0.1:8125/aipodcast_me/three-import-test.html" });
    console.log("Navigated, waiting 5s...");
    await wait(5000);

    console.log("\n=== Console Messages ===");
    if (consoleMsgs.length === 0) {
      console.log("  (none captured)");
    } else {
      for (const m of consoleMsgs) console.log("  " + m);
    }

    console.log("\n=== Status Check ===");
    const r = await send("Runtime.evaluate", { expression: "document.getElementById('status')?.textContent || 'ELEMENT_NOT_FOUND'" });
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
