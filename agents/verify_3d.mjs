// CDP verification using Node 26 native WebSocket
const tabs = JSON.parse(await (await fetch("http://127.0.0.1:9333/json/list")).text());
const page = tabs.find(t => t.type === "page" && !t.title.includes("Omnibox"));
if (!page) {
  console.log("No page target");
  process.exit(0);
}
console.log("Target:", page.title);

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
  const msg = JSON.parse(event.data);
  if (msg.id && pending.has(msg.id)) {
    pending.get(msg.id)(msg);
    pending.delete(msg.id);
  }
  // Capture console errors
  if (msg.method === "Runtime.exceptionThrown") {
    const t = msg.params?.exceptionDetails?.text || "";
    console.log("  EXCEPTION:", t.substring(0, 200));
  }
  if (msg.method === "Runtime.consoleAPICalled") {
    const lvl = msg.params?.level;
    const text = (msg.params?.args || []).map(a => a.value || "").join(" ");
    if (lvl === "error" || text.toLowerCase().includes("error")) {
      console.log("  CONSOLE[" + lvl + "]:", text.substring(0, 200));
    }
  }
});

ws.addEventListener("error", (e) => console.log("WS error:", e.message || e));

const wait = (ms) => new Promise(r => setTimeout(r, ms));

ws.addEventListener("open", async () => {
  try {
    await send("Runtime.enable");
    await send("Page.enable");
    // Force hard reload to pick up updated modules
    await send("Page.navigate", { url: "http://127.0.0.1:8125/aipodcast_me/video-edit-3d.html?_t=" + Date.now() });
    console.log("Navigated, waiting 7s...");
    await wait(7000);

    console.log("\n=== Scene Verification ===");
    const checks = [
      ["THREE", "typeof THREE"],
      ["ThreeVideoPlayer", "typeof window.ThreeVideoPlayer"],
      ["fleetWaves", "typeof window.fleetWaves"],
      ["__renderFrame", "typeof window.__renderFrame"],
      ["bootDone", "document.getElementById('boot')?.classList?.contains('done') || false"],
      ["canvas", "document.querySelector('canvas') ? 'yes' : 'no'"],
      ["bootText", "(document.getElementById('boot')?.textContent || 'none').trim().substring(0,80)"],
      ["fleetApi", "window.fleetWaves ? Object.keys(window.fleetWaves).join(',') : 'none'"],
      ["hud", "document.getElementById('hud') ? 'yes' : 'no'"],
      ["bPlay", "document.getElementById('bPlay') ? 'yes' : 'no'"],
      ["selector", "document.querySelectorAll('#selector .obj').length"],
      ["scanlines", "document.querySelector('.scan') ? 'yes' : 'no'"],
    ];

    for (const [label, expr] of checks) {
      const r = await send("Runtime.evaluate", { expression: expr });
      const v = r?.result?.result?.value ?? "(no-response)";
      const ok = v !== "undefined" && v !== "(no-response)" && v !== "no" && v !== 0 && v !== "none" && v !== false;
      console.log("  " + (ok ? "✅" : "❌") + " " + label + ": " + JSON.stringify(v));
    }

    // Screenshot
    const cd = await send("Page.captureScreenshot", { format: "png", quality: 100 });
    if (cd?.result?.data) {
      const buf = Buffer.from(cd.result.data, "base64");
      // Write via process binding (no require needed in this context)
      const { writeFileSync } = await import("fs");
      writeFileSync("C:/Users/yaelm/AppData/Local/Temp/video-edit-3d-cdp.png", buf);
      console.log("\nScreenshot:", buf.length, "bytes");
      if (buf.length > 100000) console.log("  -> >100KB: scene has content");
      else console.log("  -> <100KB: mostly empty");
    }

    ws.close();
    process.exit(0);
  } catch (e) {
    console.log("Error:", e.message);
    ws.close();
    process.exit(1);
  }
});
