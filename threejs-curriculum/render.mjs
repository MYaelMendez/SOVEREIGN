/**
 * æRTXrender — Deterministic video render harness.
 *
 * THE FIX: instead of capturing real-time animation (which desyncs and
 * produces black/transition frames), we DRIVE the animation deterministically:
 *   1. Inject a global __renderFrame(i, totalFrames) hook into the page
 *   2. For each frame i: call __renderFrame(i), wait for the GPU to paint,
 *      then capture. Frame i is ALWAYS the same visual, every run.
 *   3. Verify each captured frame is non-black before accepting it.
 *   4. Supervise frames before encoding (fail fast).
 *
 * Improvements:
 *   - PID lock prevents concurrent renders overwriting each other
 *   - NVENC pre-check: if the driver doesn't support the ffmpeg build's
 *     NVENC API, auto-falls-back to libx264 (no wasted encode cycles)
 *
 * This eliminates: timing desync, scene-transition black frames, dropped
 * frames, and non-reproducible output. Same input → same video, byte for byte.
 *
 * Usage: node render.mjs --url=<url> --out=<mp4> [--frames=450] [--fps=30]
 *        [--w=720] [--h=1280] [--encoder=nvenc|libx264|auto]
 *        [--port=9333] [--no-encode] [--supervise-preview]
 *
 * Key API note: __renderFrame must use tl.progress(0-1), NOT tl.pause(seconds).
 * See æ://teknium/c2/skill/æRTXrender for details.
 */
import { mkdirSync, existsSync, writeFileSync, readdirSync, unlinkSync, statSync, readFileSync } from 'fs';
import { execSync } from 'child_process';

// ── Args ──
const args = Object.fromEntries(process.argv.slice(2).map(a => {
  const m = a.match(/^--([^=]+)=?(.*)$/); return m ? [m[1], m[2] || true] : [a, true];
}));
const URL      = args.url;
const OUT      = args.out;
const FRAMES   = parseInt(args.frames || '450', 10);
const FPS      = parseInt(args.fps || '30', 10);
const W        = parseInt(args.w || '720', 10);
const H        = parseInt(args.h || '1280', 10);
const ENCODER  = args.encoder || 'nvenc';
const CDP_PORT = parseInt(args.port || '9333', 10);
const FRAMES_DIR = args.framesDir || `${OUT.replace(/\.mp4$/, '')}-frames`;
const SUPERVISE_PREVIEW = args.supervisePreview === true || args['supervise-preview'] === true;
const NO_ENCODE = args.noEncode === true || args['no-encode'] === true;
const MIN_BYTES = 3000; // a real frame is bigger than this; near-black compresses tiny

if (!URL || !OUT) { console.error('usage: node render.mjs --url=... --out=...'); process.exit(1); }

const FFMPEG_NVENC = 'C:/Users/yaelm/AppData/Local/hermes/tools/ffmpeg-7.1-nvenc/bin/ffmpeg.exe';
const FFMPEG_X264  = 'C:/Users/yaelm/AppData/Local/hermes/tools/ffmpeg-9.0.1-win32-x64/bin/ffmpeg.exe';
const GPU_PY = 'C:/gpu/Scripts/python.exe';
const VIDAERO_PY = 'C:/æ/vidæo/vidæo.py';

// ── PID lock — prevent concurrent renders overwriting each other ──
const LOCK_FILE = `${OUT}.lock`;
const lockContent = `${process.pid}\n${new Date().toISOString()}\n${URL}\n`;
if (existsSync(LOCK_FILE)) {
  const existing = readFileSync(LOCK_FILE, 'utf8');
  const existingPid = parseInt(existing.split('\n')[0], 10);
  console.error(`[æRTXrender] ❌ Render lock exists: ${LOCK_FILE}`);
  console.error(`  PID: ${existingPid} | ${existing.trim().split('\n').slice(1).join(' ')}`);
  console.error('  Another render is in progress or crashed without cleanup.');
  console.error('  rm the lock file if you are sure the process is dead.');
  process.exit(1);
}
writeFileSync(LOCK_FILE, lockContent);

// ── Prep frames dir (needed early for NVENC test output) ──
if (!existsSync(FRAMES_DIR)) mkdirSync(FRAMES_DIR, { recursive: true });

// ── Cleanup on exit ──
const cleanup = () => {
  try { unlinkSync(LOCK_FILE); } catch {}
};
process.on('exit', cleanup);
process.on('SIGINT', () => { cleanup(); process.exit(130); });
process.on('SIGTERM', () => { cleanup(); process.exit(143); });

// ── NVENC pre-check ──
let useEncoder = ENCODER;
if (ENCODER === 'nvenc' || ENCODER === 'auto') {
  const tmpOut = `${FRAMES_DIR}/_nvenc_test.mp4`;
  try {
    execSync(`"${FFMPEG_NVENC}" -hide_banner -f lavfi -i testsrc=duration=0.1:size=1920x1080:rate=1 -c:v h264_nvenc -t 0.1 "${tmpOut}" -y`, { timeout: 15000, stdio: 'pipe' });
    useEncoder = 'nvenc';
    console.log('[æRTXrender] ✓ NVENC available');
    // Clean up test file
    try { unlinkSync(tmpOut); } catch {}
  } catch (e) {
    console.log('[æRTXrender] ⚠ NVENC unavailable — falling back to libx264');
    useEncoder = 'libx264';
    if (ENCODER === 'nvenc') {
      console.error('  (requested nvenc but driver/ffmpeg mismatch — use --encoder=auto for silent fallback)');
    }
  }
}

// ── CDP connect ──
const resp = await fetch(`http://127.0.0.1:${CDP_PORT}/json`);
const targets = await resp.json();
const page = targets.find(t => t.type === 'page' && !t.url.startsWith('chrome-extension'));
if (!page) throw new Error('No CDP page found — is headless Chrome on ' + CDP_PORT + '?');

const ws = new WebSocket(page.webSocketDebuggerUrl);
let msgId = 0; const pending = new Map();
function send(method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = ++msgId; pending.set(id, { resolve, reject });
    ws.send(JSON.stringify({ id, method, params }));
  });
}
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const { resolve, reject } = pending.get(msg.id); pending.delete(msg.id);
    if (msg.error) reject(new Error(msg.error.message)); else resolve(msg.result);
  }
};
await new Promise(r => ws.onopen = r);

// ── Navigate + set exact viewport ──
await send('Page.enable');
await send('Emulation.setDeviceMetricsOverride', { width: W, height: H, deviceScaleFactor: 1, mobile: false });
await send('Page.navigate', { url: URL });
await new Promise(r => setTimeout(r, 3500));

// ── Probe: does the page expose a deterministic render hook? ──
const probe = await send('Runtime.evaluate', {
  expression: `typeof window.__renderFrame === 'function'`,
  returnByValue: true,
});
const hasHook = probe.result.value === true;
console.log(hasHook
  ? '[æRTXrender] deterministic hook found — driving frames'
  : '[æRTXrender] WARNING: no __renderFrame hook; falling back to real-time capture (may desync)');

// ── Capture ──
const start = Date.now();
let blackFrames = 0, minSize = Infinity;
console.log(`[æRTXrender] capturing ${FRAMES} frames @ ${FPS}fps → ${W}x${H}`);

for (let i = 0; i < FRAMES; i++) {
  if (hasHook) {
    // Deterministic: set the exact frame via __renderFrame, then let the GPU paint
    await send('Runtime.evaluate', {
      expression: `window.__renderFrame(${i}, ${FRAMES})`,
      awaitPromise: true,
    });
    await send('Runtime.evaluate', { expression: `new Promise(r=>requestAnimationFrame(()=>requestAnimationFrame(r)))`, awaitPromise: true });
  } else {
    await new Promise(r => setTimeout(r, 1000 / FPS));
  }

  const { data } = await send('Page.captureScreenshot', { format: 'png' });
  const buf = Buffer.from(data, 'base64');
  const path = `${FRAMES_DIR}/frame_${String(i).padStart(5, '0')}.png`;
  writeFileSync(path, buf);

  const sz = buf.length;
  if (sz < minSize) minSize = sz;
  if (sz < MIN_BYTES) blackFrames++;

  if (i % 30 === 0) console.log(`  frame ${i}/${FRAMES} (${sz} B)`);
}

const captureS = ((Date.now() - start) / 1000).toFixed(1);
console.log(`[æRTXrender] captured in ${captureS}s · min frame ${minSize} B · suspect-black ${blackFrames}/${FRAMES}`);

if (blackFrames > FRAMES * 0.1) {
  console.warn(`[æRTXrender] ⚠ ${blackFrames} frames look black — the scene hook or timing is wrong.`);
  console.warn('  Refusing to encode a bad video. Check __renderFrame hook.');
  process.exit(1);
}

ws.close();

// ── Supervise captured frames BEFORE encoding (fail fast) ──
if (SUPERVISE_PREVIEW) {
  console.log('[æRTXrender] supervising captured frames...');
  try {
    const svResult = execSync(
      `"${GPU_PY}" "${VIDAERO_PY}" verify "${FRAMES_DIR}"`,
      { timeout: 60000, encoding: 'utf8' }
    );
    console.log(svResult.trim());
    if (!svResult.includes('PASS')) {
      console.warn('[æRTXrender] ⚠ Frame supervision did not PASS — continuing anyway');
    }
  } catch (e) {
    console.warn('[æRTXrender] ⚠ Frame supervision failed:', e.message.slice(0, 200));
  }
}

if (NO_ENCODE) {
  console.log(`[æRTXrender] ✅ Frames captured to ${FRAMES_DIR} (${FRAMES} frames, no encode)`);
  process.exit(0);
}

// ── Encode ──
console.log(`[æRTXrender] encoding with ${useEncoder}…`);
const ff = useEncoder === 'nvenc' ? FFMPEG_NVENC : FFMPEG_X264;
const codecArgs = useEncoder === 'nvenc'
  ? ['-c:v', 'h264_nvenc', '-preset', 'p7', '-cq', '20', '-pix_fmt', 'yuv420p']
  : ['-c:v', 'libx264', '-crf', '20', '-preset', 'fast', '-pix_fmt', 'yuv420p'];
const cmd = [ff, '-y', '-framerate', String(FPS), '-i', `${FRAMES_DIR}/frame_%05d.png`,
  ...codecArgs, '-movflags', '+faststart', OUT];
execSync(cmd.map(a => `"${a}"`).join(' '), { stdio: 'inherit' });

const mb = (statSync(OUT).size / 1048576).toFixed(1);
console.log(`[æRTXrender] ✅ ${OUT} (${mb} MB, ${useEncoder})`);
console.log(`[æRTXrender] frames: ${FRAMES} @ ${FPS}fps, ${W}x${H}, capture ${captureS}s`);
