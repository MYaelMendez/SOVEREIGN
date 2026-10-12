#!/usr/bin/env node
/**
 * Render fleet-waves.html to MP4 via Chrome CDP + ffmpeg NVENC.
 * Connects to a running Chrome instance on port 9222.
 */
const http = require('http');
const fs = require('fs');
const os = require('os');
const { execFile, spawn } = require('child_process');
const path = require('path');

const FFMPEG = '"C:\\Users\\yaelm\\AppData\\Local\\hermes\\tools\\ffmpeg-9.0.1-win32-x64\\bin\\ffmpeg.exe"';
const SITE_DIR = 'C:\\æ\\site';
const OUTPUT = 'C:\\æ\\site\\aipodcast_me\\fleet-waves-development.mp4';
const PORT = 9222;
const W = 1920, H = 1080;
const DURATION = 12, FPS = 30;
const SCENE_URL = 'http://127.0.0.1:8125/aipodcast_me/fleet-waves.html';

// Start local HTTP server if not already running
const server = http.createServer((req, res) => {
  const filePath = path.join(SITE_DIR, req.url === '/' ? 'index.html' : req.url);
  fs.readFile(filePath, (err, data) => {
    if (err) { res.writeHead(404); res.end('Not found'); return; }
    res.end(data);
  });
});

async function main() {
  // Ensure HTTP server is running
  try {
    server.listen(8125);
    console.log('HTTP server on :8125');
  } catch(e) {
    console.log('HTTP server already running on :8125');
  }

  const CDP = require('chrome-remote-interface');

  // Connect to running Chrome
  const client = await CDP({ port: PORT });
  const { Runtime, Page } = client;

  await Page.enable();
  await Runtime.enable();

  // Navigate
  await Page.navigate({ url: SCENE_URL });
  await Page.loadEventFired();
  console.log('Page loaded ✓');

  // Wait for GSAP timeline
  let timelineReady = false;
  for (let i = 0; i < 100; i++) {
    const { result } = await Runtime.evaluate({
      expression: "typeof gsap !== 'undefined' && typeof window.__timelines !== 'undefined' && window.__timelines['fleet-waves-dev'] ? 'READY' : 'WAIT'",
      returnByValue: true
    });
    if (result?.result?.value === 'READY') {
      console.log('Timeline registered ✓');
      timelineReady = true;
      break;
    }
    await new Promise(r => setTimeout(r, 200));
  }
  if (!timelineReady) console.log('Timeline not found — rendering anyway');

  // Give the timeline a moment to play
  await new Promise(r => setTimeout(r, 500));

  const nFrames = Math.floor(DURATION * FPS);
  console.log(`Capturing ${nFrames} frames @ ${FPS}fps...`);

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fleetwaves_'));
  let captured = 0;

  for (let i = 0; i < nFrames; i++) {
    const progress = (i / FPS) / DURATION;

    // Seek GSAP timeline for deterministic frame (no returnByValue to avoid CDP errors)
    await Runtime.evaluate({
      expression: `var tl=window.__timelines&&window.__timelines['fleet-waves-dev'];if(tl)tl.pause(${progress});`,
    });

    await new Promise(r => setTimeout(r, 5));

    const { data } = await Page.captureScreenshot({
      format: 'png', quality: 100,
      clip: { x: 0, y: 0, width: W, height: H, scale: 1 }
    });

    const buf = Buffer.from(data, 'base64');
    const fpath = path.join(tmpDir, `${String(i).padStart(5, '0')}.png`);
    fs.writeFileSync(fpath, buf);
    captured++;

    if ((i + 1) % 30 === 0) {
      console.log(`  ${Math.round((i + 1) / nFrames * 100)}%  (${i + 1}/${nFrames})`);
    }
  }

  await client.close();
  console.log(`Captured ${captured} frames`);

  // Build ffmpeg concat list
  const listFile = path.join(tmpDir, 'list.txt');
  let listContent = '';
  for (let i = 0; i < captured; i++) {
    const p = path.join(tmpDir, `${String(i).padStart(5, '0')}.png`).replace(/\\/g, '/');
    listContent += `file '${p}'\n`;
    if (i < captured - 1) listContent += 'duration 0.033\n';
  }
  fs.writeFileSync(listFile, listContent);

  // Encode with NVENC
  fs.mkdirSync(path.dirname(OUTPUT), { recursive: true });

  const ffmpegBin = FFMPEG.replace(/"/g, '');
  const args = [
    '-y', '-f', 'concat', '-safe', '0', '-i', listFile,
    '-c:v', 'h264_nvenc', '-b:v', '6M', '-pix_fmt', 'yuv420p',
    '-r', String(FPS), '-vf', 'format=yuv420p', OUTPUT
  ];

  console.log('Encoding MP4 (h264_nvenc)...');
  execFile(ffmpegBin, args, { timeout: 120000, maxBuffer: 100 * 1024 * 1024 }, (err, stdout, stderr) => {
    if (err && stderr && stderr.toString().toLowerCase().includes('nvenc')) {
      console.log('NVENC unavailable, falling back to libx264...');
      args[8] = 'libx264';
      execFile(ffmpegBin, args, { timeout: 300000, maxBuffer: 100 * 1024 * 1024 }, (e2) => {
        done(e2);
      });
    } else {
      done(err);
    }
  });

  function done(err) {
    if (err) console.error('ffmpeg:', err.message);
    if (fs.existsSync(OUTPUT)) {
      const sz = fs.statSync(OUTPUT).size;
      console.log(`✅ ${OUTPUT}  (${(sz / 1024 / 1024).toFixed(1)} MB)`);
    } else {
      console.log('❌ Output not created');
    }
    server.close();
    process.exit(0);
  }
}

main().catch(e => {
  console.error('Error:', e.message);
  process.exit(1);
});
