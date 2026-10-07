// CDP screenshot — navigates to the page, waits for render, captures
import { WebSocket } from "ws";

async function run() {
  const res = await fetch("http://127.0.0.1:9333/json/list");
  const tabs = await res.json();
  const page = tabs.find(t => t.type === "page" && !t.title.includes("Omnibox"));
  if (!page) {
    console.log("No page target. Available:", tabs.map(t => t.title).join(", "));
    process.exit(1);
  }

  console.log("Target:", page.title || "untitled");
  const ws = new WebSocket(page.webSocketDebuggerUrl);

  let msgId = 0;
  const pending = new Map();

  ws.on("open", () => {
    const send = (method, params = {}) => {
      const id = ++msgId;
      const fut = new Promise((resolve) => pending.set(id, resolve));
      ws.send(JSON.stringify({ method, params, id }));
      return fut;
    };

    (async () => {
      try {
        await send("Runtime.enable");
        await send("Page.enable");

        // Listen for console errors
        const errors = [];
        ws.on("message", (data) => {
          const msg = JSON.parse(data);
          if (msg.id && pending.has(msg.id)) {
            pending.get(msg.id)(msg);
            pending.delete(msg.id);
          }
          if (msg.method === "Runtime.exceptionThrown") {
            const t = msg.params?.exceptionDetails?.text || "";
            errors.push(t.substring(0, 200));
          }
          if (msg.method === "Runtime.consoleAPICalled") {
            const lvl = msg.params?.level;
            const text = (msg.params?.args || []).map(a => a.value || "").join(" ");
            if (lvl === "error" || text.toLowerCase().includes("error")) {
              errors.push("[" + lvl + "] " + text.substring(0, 200));
            }
          }
        });

        console.log("Navigating to video-edit-3d.html...");
        await send("Page.navigate", {
          url: "http://127.0.0.1:8125/aipodcast_me/video-edit-3d.html"
        });

        // Wait 6 seconds for three.js to load and render
        console.log("Waiting 6s for scene to render...");
        await new Promise(r => setTimeout(r, 6000));

        // Check console for errors
        if (errors.length > 0) {
          console.log("\nConsole errors:");
          errors.forEach(e => console.log("  ❌ " + e));
        } else {
          console.log("\nNo console errors");
        }

        // Verify globals
        const globalChecks = [
          ["THREE", "typeof THREE"],
          ["ThreeVideoPlayer", "typeof window.ThreeVideoPlayer"],
          ["fleetWaves", "typeof window.fleetWaves"],
          ["__renderFrame", "typeof window.__renderFrame"],
          ["bootDone", "document.getElementById('boot')?.classList?.contains('done') || false"],
          ["canvas", "document.querySelector('canvas') ? 'yes' : 'no'"],
          ["fleetApi", "window.fleetWaves ? Object.keys(window.fleetWaves).join(',') : 'none'"],
        ];

        console.log("\n=== Verification ===");
        for (const [label, expr] of globalChecks) {
          const r = await send("Runtime.evaluate", { expression: expr });
          const v = r.result?.result?.value ?? "(error)";
          const ok = v !== "undefined" && v !== "(error)" && v !== "no" && v !== 0 && v !== "none" && v !== false;
          console.log("  " + (ok ? "✅" : "❌") + " " + label + ": " + JSON.stringify(v));
        }

        // Take screenshot
        console.log("\nCapturing screenshot...");
        const cd = await send("Page.captureScreenshot", {
          format: "png",
          quality: 100
        });

        if (cd.result?.data) {
          const fs = require("fs");
          const buf = Buffer.from(cd.result.data, "base64");
          fs.writeFileSync("C:/Users/yaelm/AppData/Local/Temp/video-edit-3d-verify2.png", buf);
          console.log("Screenshot saved: " + buf.length + " bytes");
          // Quick check: count non-black pixels by sampling
          // PNG is compressed, but file size gives a hint
          if (buf.length > 50000) {
            console.log("  → File > 50KB, likely has rendered content ✅");
          } else {
            console.log("  → File < 50KB, may be mostly black ❌");
          }
        }

        ws.close();
        process.exit(0);
      } catch (e) {
        console.log("Error:", e.message);
        ws.close();
        process.exit(1);
      }
    })();
  });

  ws.on("error", (e) => console.log("WS error:", e.message || e));
}

run();
