/**
 * SOVÆREIGN STUDIO — one pane for the whole robot loop.
 *
 * Unifies three panes that were one workflow split across ~1,100px of rail:
 *   asimov://        the companion + policy verdicts
 *   soværeign voice  the cast + speech
 *   VLC Player       the truth pane — the human watches the film
 *
 * The loop they serve is a single thing:
 *   tinyPython → tinyGPU → gate → receipt → VLC
 *     physics     pixels    verdict   proof    human
 *
 * One pane, three tabs, shared state. The film you just rendered is one click
 * from the pane that rendered it, and the voice that narrates it is the same
 * cast the companion shows.
 *
 * Theme: #D4AF37 gold on #050505 void + scanlines.
 */

import { cn, host, haptic, useValue } from '@hermes/plugin-sdk'
import { jsx, jsxs } from 'react/jsx-runtime'
import React from 'react'

const ID = 'sovereign-studio'
const GOLD = '#D4AF37'
const VOID = '#050505'
const DIM = 'rgba(212,175,55,0.35)'
const FAINT = 'rgba(212,175,55,0.10)'
const CYAN = '#00ccff'
const GREEN = '#00ff9f'
const MAGENTA = '#ff40dc'

const COMPANION = 'http://127.0.0.1:8161/index.html'
const ENV = 'http://127.0.0.1:8162/env'
const VLC = 'http://127.0.0.1:8081'
// ctx.rest() mounts at /api/plugins/<this-plugin-id>/ — sovereign-studio has no
// Python backend of its own. The voice routes belong to tiny-voca-voice, so we
// address that router directly rather than 404 against a backend we never wrote.
const VOICE_API = '/api/plugins/tiny-voca-voice'
// VLC sends no CORS headers. The local proxy adds them; when it is absent the
// direct fetch is attempted and the failure is reported as CORS, not as down.
const PROXY = 'http://127.0.0.1:8164'

async function voiceRest(path, opts) {
  const r = await fetch(VOICE_API + path, {
    method: (opts && opts.method) || 'GET',
    headers: { 'Content-Type': 'application/json' },
    body: opts && opts.body ? JSON.stringify(opts.body) : undefined,
    cache: 'no-store',
  })
  if (!r.ok) throw new Error(`${r.status} ${r.statusText}`)
  return r.json()
}

// --- small pieces ---

function Label({ children }) {
  return jsx('div', {
    style: { fontSize: 9.5, letterSpacing: '0.16em', color: DIM, marginBottom: 6 },
    children,
  })
}

function Dot({ ok, colour }) {
  return jsx('span', {
    style: {
      display: 'inline-block', width: 6, height: 6, borderRadius: 3,
      background: ok ? (colour || GREEN) : '#4a4436', marginRight: 6,
      boxShadow: ok ? `0 0 6px ${colour || GREEN}` : 'none',
    },
  })
}

function Btn({ children, onClick, active, tone }) {
  return jsx('button', {
    onClick: () => { haptic('light'); onClick && onClick() },
    style: {
      background: active ? FAINT : 'none',
      border: `1px solid ${active ? (tone || GOLD) : 'rgba(212,175,55,0.18)'}`,
      color: active ? (tone || GOLD) : DIM,
      padding: '5px 10px', fontSize: 10.5, letterSpacing: '0.06em',
      cursor: 'pointer', fontFamily: 'inherit',
    },
    children,
  })
}

// --- tab 1: the companion ---

function CompanionTab() {
  const [live, setLive] = React.useState(true)
  const [env, setEnv] = React.useState(null)
  const [up, setUp] = React.useState(null)

  React.useEffect(() => {
    let stop = false
    const tick = async () => {
      try {
        const r = await fetch(ENV, { cache: 'no-store' })
        const d = await r.json()
        if (!stop) { setEnv(d); setUp(true) }
      } catch (e) { if (!stop) setUp(false) }
    }
    tick()
    const t = setInterval(tick, 5000)
    return () => { stop = true; clearInterval(t) }
  }, [])

  const gpu = env && env.gpu
  const ram = env && env.memory
  return jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', gap: 8, height: '100%' },
    children: [
      jsxs('div', {
        style: { display: 'flex', alignItems: 'center', gap: 8 },
        children: [
          jsx(Dot, { ok: up === true }),
          jsx('span', { style: { fontSize: 10, color: DIM }, children: up === true ? 'AWARE' : up === false ? 'perception offline' : 'probing…' }),
          jsx('div', { style: { flex: 1 } }),
          jsx(Btn, { active: live, onClick: () => setLive(!live), children: live ? 'LIVE' : 'PAUSED' }),
        ],
      }),
      jsx('div', {
        style: {
          position: 'relative', flex: 1, minHeight: 300,
          border: `1px solid ${DIM}`, background: '#07090e', overflow: 'hidden',
        },
        children: live
          ? jsx('iframe', {
              src: COMPANION, title: 'asimov companion',
              style: { width: '100%', height: '100%', border: 0, display: 'block' },
            })
          : jsx('div', {
              style: { padding: 20, color: DIM, fontSize: 11, textAlign: 'center' },
              children: 'paused — the robot keeps its last pose',
            }),
      }),
      // The companion iframe already prints GPU / VRAM / RAM / receipts.
      // Repeating them here showed the same numbers twice in one 420px pane.
      // Show only what the companion does NOT: the ledger total across ALL
      // ledgers, and the standing rule. When the iframe is paused, the pane
      // is the only source, so the full block returns.
      gpu && gpu.available ? jsxs('div', {
        style: { fontSize: 10, color: DIM, lineHeight: 1.7 },
        children: live ? [
          env.ledgers ? jsx('div', {
            children: `${Object.values(env.ledgers).reduce((a, b) => a + b, 0)} receipts · ${Object.keys(env.ledgers).length} ledgers`,
          }) : null,
          jsx('div', { style: { color: 'rgba(212,175,55,0.25)' }, children: 'perception grants nothing' }),
        ] : [
          jsx('div', { children: `${gpu.name} · ${gpu.util_pct}% · ${gpu.temp_c}°C · ${gpu.pstate}` }),
          jsx('div', { children: `VRAM ${gpu.mem_used_mib}/${gpu.mem_total_mib} MiB` }),
          ram && ram.available
            ? jsx('div', { children: `RAM ${ram.load_pct}% · ${ram.free_gb} GB free · ${env.host.cpus} threads` })
            : null,
          env.ledgers ? jsx('div', {
            children: `${Object.values(env.ledgers).reduce((a, b) => a + b, 0)} receipts across ${Object.keys(env.ledgers).length} ledgers`,
          }) : null,
          jsx('div', { style: { color: 'rgba(212,175,55,0.25)' }, children: 'perception grants nothing' }),
        ],
      }) : null,
    ],
  })
}

// --- tab 2: the voice ---

function VoiceTab() {
  const [text, setText] = React.useState('')
  const [voice, setVoice] = React.useState('M2')
  const [busy, setBusy] = React.useState(false)
  const [receipts, setReceipts] = React.useState([])
  const [ledger, setLedger] = React.useState('probing')   // probing | ok | unreachable
  const [err, setErr] = React.useState(null)

  const load = React.useCallback(async () => {
    try {
      const d = await voiceRest('/receipts?limit=6')
      setReceipts(Array.isArray(d) ? d : (d && d.receipts) || [])
      setLedger('ok')
    } catch (e) {
      // EMPTY and UNREACHABLE are different facts. Reporting 'no receipts yet'
      // when the ledger cannot be read is a false statement about the world.
      // the plugin API is desktop-only; the proxy reads the same files from disk
      try {
        const r = await fetch(`${PROXY}/ledgers`, { cache: 'no-store' })
        const d = await r.json()
        const n = d.ledgers && d.ledgers['tiny-voca-receipts']
        setReceipts(n != null
          ? [{ text: `${n} speech receipts on disk`, sha: 'via studio proxy' }]
          : [])
        setLedger(n != null ? 'proxy' : 'unreachable')
      } catch (e2) { setLedger('unreachable') }
    }
  }, [])

  React.useEffect(() => { load() }, [load])

  const speak = async () => {
    if (!text.trim() || busy) return
    setBusy(true); setErr(null)
    try {
      await voiceRest('/speak', { method: 'POST', body: { text, voice } })
      setText(''); await load()
    } catch (e) { setErr(String(e && e.message || e)) }
    finally { setBusy(false) }
  }

  const CAST = [
    { id: 'F2', name: 'nous', colour: MAGENTA },
    { id: 'M2', name: 'hermes', colour: CYAN },
  ]

  return jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', gap: 10 },
    children: [
      jsx(Label, { children: 'CAST' }),
      jsx('div', {
        style: { display: 'flex', gap: 6 },
        children: CAST.map((c) => jsx(Btn, {
          active: voice === c.id, tone: c.colour,
          onClick: () => setVoice(c.id), children: `${c.name} · ${c.id}`,
        }, c.id)),
      }),
      jsx(Label, { children: 'SPEAK' }),
      jsx('textarea', {
        value: text, onChange: (e) => setText(e.target.value),
        placeholder: 'what should the robot say…',
        style: {
          background: '#0d0c08', border: `1px solid ${FAINT}`, color: '#f5eed6',
          padding: 10, fontSize: 12, fontFamily: 'inherit', minHeight: 70,
          resize: 'vertical', outline: 'none',
        },
      }),
      jsx(Btn, { active: true, onClick: speak, children: busy ? 'SPEAKING…' : 'SPEAK' }),
      err ? jsx('div', { style: { color: MAGENTA, fontSize: 10.5 }, children: err }) : null,
      jsx(Label, { children: ledger === 'proxy' ? 'LEDGER (via proxy)' : 'RECENT RECEIPTS' }),
      jsxs('div', {
        style: { display: 'flex', flexDirection: 'column', gap: 4, maxHeight: 180, overflowY: 'auto' },
        children: receipts.length
          ? receipts.map((r, i) => jsxs('div', {
              style: { fontSize: 10, color: DIM, borderLeft: `2px solid ${FAINT}`, paddingLeft: 8 },
              children: [
                jsx('div', { style: { color: '#cfc4a4' }, children: String(r.text || r.intent || '').slice(0, 60) }),
                jsx('div', { children: String(r.sha || r.hash || '').slice(0, 16) }),
              ],
            }, i))
          : jsx('div', { style: { fontSize: 10, color: ledger === 'unreachable' ? MAGENTA : DIM },
              children: ledger === 'unreachable'
                ? 'ledger unreachable — the plugin API is served by the desktop app, not a plain browser. Receipts exist; this view cannot read them.'
                : ledger === 'probing' ? 'reading the ledger…' : 'the ledger is empty' }),
      }),
    ],
  })
}

// --- tab 3: the truth pane ---

function WatchTab() {
  const [st, setSt] = React.useState(null)
  const [err, setErr] = React.useState(null)
  const [file, setFile] = React.useState('')

  const auth = 'Basic ' + btoa(':asimov')
  const [via, setVia] = React.useState(null)
  const req = React.useCallback(async (q) => {
    // try the proxy first: it is the path that works from a browser
    try {
      const r = await fetch(`${PROXY}/vlc/requests/status.json${q || ''}`, { cache: 'no-store' })
      if (r.ok) { const d = await r.json(); if (d && d.state !== undefined) { setVia('proxy'); return d } }
    } catch (e) { /* fall through to direct */ }
    const r = await fetch(`${VLC}/requests/status.json${q || ''}`, {
      headers: { Authorization: auth }, cache: 'no-store',
    })
    setVia('direct')
    return r.json()
  }, [])

  const poll = React.useCallback(async () => {
    try { setSt(await req()); setErr(null) }
    catch (e) {
      // A browser fetch to :8081 is cross-origin and VLC sends no CORS headers.
      // That is NOT the same as VLC being down — distinguish them.
      setErr('VLC blocked by CORS from a browser (it sends no CORS headers). '
           + 'In the desktop pane this may succeed; from a plain page use the '
           + 'proxy at :8164, or drive VLC over HTTP directly.')
    }
  }, [req])

  React.useEffect(() => {
    poll()
    const t = setInterval(poll, 2500)
    return () => clearInterval(t)
  }, [poll])

  const cmd = async (c) => { try { await req(`?command=${c}`); await poll() } catch (e) {} }
  const open = async () => {
    if (!file.trim()) return
    try { await req(`?command=in_play&input=${encodeURIComponent(file.trim())}`); await poll() }
    catch (e) { setErr(String(e && e.message || e)) }
  }

  const playing = st && st.state === 'playing'
  const pos = st && st.length ? Math.round((st.time / st.length) * 100) : 0

  return jsxs('div', {
    style: { display: 'flex', flexDirection: 'column', gap: 10 },
    children: [
      jsxs('div', {
        style: { display: 'flex', alignItems: 'center', gap: 8 },
        children: [
          jsx(Dot, { ok: playing, colour: GOLD }),
          jsx('span', { style: { fontSize: 10.5, color: playing ? GOLD : DIM },
            children: st ? `${st.state} · ${st.time ?? 0}/${st.length ?? 0}s${via ? ' · via ' + via : ''}` : 'probing…' }),
        ],
      }),
      jsx('div', {
        style: { height: 3, background: FAINT },
        children: jsx('div', { style: { height: 3, width: `${pos}%`, background: GOLD } }),
      }),
      jsx('div', {
        style: { display: 'flex', gap: 6 },
        children: [
          jsx(Btn, { onClick: () => cmd(playing ? 'pl_pause' : 'pl_play'), children: playing ? 'PAUSE' : 'PLAY' }),
          jsx(Btn, { onClick: () => cmd('pl_stop'), children: 'STOP' }),
          jsx(Btn, { onClick: () => cmd('pl_previous'), children: 'PREV' }),
          jsx(Btn, { onClick: () => cmd('pl_next'), children: 'NEXT' }),
        ],
      }),
      jsx(Label, { children: 'OPEN A FILM — absolute path' }),
      jsxs('div', {
        style: { display: 'flex', gap: 6 },
        children: [
          jsx('input', {
            value: file, onChange: (e) => setFile(e.target.value),
            placeholder: 'C:\\æ\\github-pages\\asimov-walk-916.mp4',
            style: {
              flex: 1, background: '#0d0c08', border: `1px solid ${FAINT}`,
              color: '#f5eed6', padding: '7px 9px', fontSize: 10.5,
              fontFamily: 'inherit', outline: 'none',
            },
          }),
          jsx(Btn, { active: true, onClick: open, children: 'OPEN' }),
        ],
      }),
      err ? jsx('div', { style: { color: MAGENTA, fontSize: 10 }, children: err }) : null,
      jsx('div', {
        style: { fontSize: 9.5, color: DIM, lineHeight: 1.7, borderTop: `1px solid ${FAINT}`, paddingTop: 8 },
        children: 'The supervisor verdict is not the whole gate. The human watches the film. That is why this tab exists.',
      }),
    ],
  })
}

// --- the unified pane ---

function Studio({ ctx }) {
  const [tab, setTab] = React.useState('robot')
  const TABS = [
    { id: 'robot', label: 'ROBOT' },
    { id: 'voice', label: 'VOICE' },
    { id: 'watch', label: 'WATCH' },
  ]
  return jsxs('div', {
    style: {
      background: VOID, color: '#f5eed6', height: '100%',
      fontFamily: "'JetBrains Mono', Consolas, monospace",
      display: 'flex', flexDirection: 'column', overflow: 'hidden',
    },
    children: [
      jsxs('div', {
        style: { padding: '10px 12px', borderBottom: `1px solid ${GOLD}`, flexShrink: 0 },
        children: [
          jsx('div', { style: { fontSize: 9.5, letterSpacing: '0.22em', color: GOLD }, children: '>_æ://' }),
          jsx('div', { style: { fontSize: 14, color: GOLD, letterSpacing: '0.06em', marginTop: 2 }, children: 'SOVÆREIGN STUDIO' }),
          jsx('div', { style: { fontSize: 9, color: DIM, marginTop: 3 }, children: 'physics → pixels → verdict → receipt → human' }),
        ],
      }),
      jsx('div', {
        style: { display: 'flex', gap: 4, padding: '8px 12px', flexShrink: 0 },
        children: TABS.map((t) => jsx(Btn, {
          active: tab === t.id, onClick: () => setTab(t.id), children: t.label,
        }, t.id)),
      }),
      jsxs('div', {
        style: { flex: 1, overflowY: 'auto', padding: '4px 12px 14px' },
        children: [
          tab === 'robot' ? jsx(CompanionTab, {}) : null,
          tab === 'voice' ? jsx(VoiceTab, {}) : null,
          tab === 'watch' ? jsx(WatchTab, {}) : null,
        ],
      }),
    ],
  })
}

export default {
  id: ID,
  name: 'Sovereign Studio',
  defaultEnabled: true,
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'soværeign studio',
      data: { placement: 'right', width: '420px' },
      render: () => jsx(Studio, { ctx }),
    })
  },
}
