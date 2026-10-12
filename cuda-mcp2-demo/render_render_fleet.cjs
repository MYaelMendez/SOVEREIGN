#!/usr/bin/env node
/**
 * Render fleet-waves.html to MP4 via Chrome CDP + ffmpeg NVENC.
 * Uses chrome-remote-interface for clean CDP access.
 */
const http = require('http');
const fs = require('fs');
const os = require('os');
const { execSync, spawn, execFile } = require('child_process');
const path = require('path');

const CHROME = '"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"';
const FFMPEG = '"C:\\Users\\yaelm\\AppData\\Local\\hermes\\tools\\ffmpeg-9.0.1-win32-x64\\bin\\ffmpeg.exe"';
const SITE_DIR = 'C:\\æ\\site';
const SCENE_URL = 'http://127.0.0.1:8125/aipodcast_me/fleet-waves.html';
const OUTPUT = 'C:\\æ\\site\\aipodcast_me\\fleet-waves-development.mp4';
const PORT = 9222;
const W = 1920, H = 1080;
const DURATION = 12, FPS = 30;

// Start local HTTP server
const server = http.createServer((req, res) => {
  const filePath = path.join(SITE_DIR, req.url === '/' ? 'index.html' : req.url);
  fs.readFile(filePath, (err, data) => {
    if (err) { res.writeHead(404); res.end('Not found'); return; }
    res.end(data);
  });
});
server.listen(8125, () => console.log('HTTP server on :8125'));

async function main() {
  const CDP = require('chrome-remote-interface');

  // Start Chrome
  const chromeProc = spawn(CHROME, [
    '--headless=new', '--disable-gpu', '--no-sandbox',
    '--no-first-run', '--no-default-browser-check',
    '--disable-extensions', '--disable-dev-shm-usage',
    `--remote-debugging-port=${PORT}`,
    `--window-size=${W},${H}`, '--mute-audio',
    '--autoplay-policy=no-user-gesture-required',
    SCENE_URL
  ], { shell: true, stdio: 'pipe' });

  console.log(`Chrome pid=${chromeProc.pid}`);

  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'fleetwaves_'));
  let frameCount = 0;
  const nFrames = Math.floor(DURATION * FPS);

  try {
    // Connect via CDP
    const client = await CDP({ port: PORT });
    const { Runtime, Page } = client;

    await Page.enable();
    await Runtime.enable();

    // Wait for page load
    await Page.loadEventFired();
    console.log('Page loaded');

    // Wait for GSAP timeline
    for (let i = 0; i < 200; i++) {
      const { result } = await Runtime.evaluate({
        expression: "typeof window.__timelines !== 'undefined' && window.__timelines['fleet-waves-dev'] ? 'READY' : 'WAIT'",
        returnByValue: true
      });
      if (result?.result?.value === 'READY') {
        console.log('Timeline registered ✓');
        break;
      }
      await new Promise(r => setTimeout(r, 100));
    }

    // Give GSAP timeline a moment to play
    await new Promise(r => setTimeout(r, 500));

    console.log(`Capturing ${nFrames} frames @ ${FPS}fps...`);

    for (let i = 0; i < nFrames; i++) {
      const progress = (i / FPS) / DURATION;

      // Seek the GSAP timeline
      await Runtime.evaluate({
        expression: `var tl=window.__timelines&&window.__timelines['fleet-waves-dev'];if(tl)tl.pause(${progress});`,
        returnByValue: true
      });

      // Small delay for canvas re-render
      await new Promise(r => setTimeout(r, 5));

      // Capture screenshot
      const { data } = await Page.captureScreenshot({
        format: 'png', quality: 100,
        clip: { x: 0, y: 0, width: W, height: H, scale: 1 }
      });

      const buf = Buffer.from(data, 'base64');
      const fpath = path.join(tmpDir, `${String(i).padStart(5, '0')}.png`);
      fs.writeFileSync(fpath, buf);
      frameCount++;

      if ((i + 1) % 30 === 0) {
        console.log(`  ${Math.round((i + 1) / nFrames * 100)}%  (${i + 1}/${nFrames})`);
      }
    }

    await client.close();
    console.log(`Captured ${frameCount} frames`);

    // Build ffmpeg concat list
    const listFile = path.join(tmpDir, 'list.txt');
    let listContent = '';
    for (let i = 0; i < frameCount; i++) {
      listContent += `file '${path.join(tmpDir, `${String(i).padStart(5, '0')}.png`).replace(/\\/g, '/')}'\n`;
      listContent += 'duration 0.033\n';
    }
    // Remove trailing duration (ffmpeg needs it only between frames)
    const lines = listContent.trim().split('\n');
    lines.pop(); // remove last "duration" line
    fs.writeFileSync(listFile, lines.join('\n') + '\n');

    // Encode with NVENC
    const outDir = path.dirname(OUTPUT);
    fs.mkdirSync(outDir, { recursive: true });

    const ffmpegCmd = [
      '-y', '-f', 'concat', '-safe', '0', '-i', listFile,
      '-c:v', 'h264_nvenc', '-b:v', '6M', '-pix_fmt', 'yuv420p',
      '-r', String(FPS), '-vf', 'format=yuv420p', OUTPUT
    ];

    console.log('Encoding MP4 (h264_nvenc)...');
    try {
      execFile(FFMPEG.replace(/"/g, ''), ffmpegCmd, { timeout: 120000, stdio: 'pipe' }, (err, stdout, stderr) => {
        if (err && stderr && !stderr.toString().includes('nvenc')) {
          console.log('NVENC failed, trying libx264...');
          const cmd2 = ffmpegCmd.map(c => c === 'h264_nvenc' ? 'libx264' : c);
          execFile(FFMPEG.replace(/"/g, ''), cmd2, { timeout: 300000, stdio: 'pipe' }, (e2) => {
            finish(e2);
          });
        } else {
          finish(err);
        }
      });
    } catch(e) { finish(e); }

    function finish(err) {
      if (err) console.error('ffmpeg error:', err.message);
      if (fs.existsSync(OUTPUT)) {
        const sz = fs.statSync(OUTPUT).size;
        console.log(`✅ ${OUTPUT}  (${(sz / 1024 / 1024).toFixed(1)} MB)`);
      } else {
        console.log('❌ Output not created');
      }
      server.close();
      chromeProc.terminate();
      process.exit(0);
    }

  } catch (e) {
    console.error('Error:', e.message);
    chromeProc.terminate();
    server.close();
    process.exit(1);
  }
}

main();
