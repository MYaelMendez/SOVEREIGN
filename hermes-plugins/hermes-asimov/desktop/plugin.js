/**
 * hermes-asimov — governance console pane for the humanoid robot.
 *
 *   HUMAN://ROOT → æ POLICY → asimov:// → RECEIPT
 *   An address is not a permission.
 *
 * Backend (built in parallel): plugins/hermes-asimov/dashboard/plugin_api.py
 *   GET  /status  — sdk / robot configured / dry-run
 *   GET  /cast    — the five heads
 *   GET  /ledger  — receipt chains
 *   POST /plan    — {verb} → policy decision (a refusal is a RESULT)
 *
 * ESM, jsx()/jsxs() only — no JSX syntax. ctx flows as a prop, never a closure.
 */

import React from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'
import { cn, host, haptic, useValue } from '@hermes/plugin-sdk'

const ID = 'hermes-asimov'

// Head colours are the physical robot LEDs — fixed by hardware, not theme.
const HEAD_COLOURS = {
  'nous girl': 'rgb(255,64,220)',
  'hermes-agent': 'rgb(0,170,255)',
  'wætz': 'rgb(245,245,250)',
  'menlo-research': 'rgb(255,150,0)',
  'asimov-agent': 'rgb(0,255,120)',
}
const CAST_ORDER = ['nous girl', 'hermes-agent', 'wætz', 'menlo-research', 'asimov-agent']

const VERBS = [
  'status', 'state', 'stand', 'damp', 'balance',
  'set_velocity', 'trajectory', 'set_joints', 'photo', 'play_pcm',
]

const MONO = "'Consolas', 'JetBrains Mono', 'Monaco', monospace"
const SCANLINES =
  'repeating-linear-gradient(0deg, transparent 0px, transparent 2px, rgba(212,175,55,0.015) 2px, rgba(212,175,55,0.015) 4px)'

// Decision palette: allow = green, require_approval = gold (theme accent),
// deny = magenta. A deny is a RESULT — rendered, never toasted as an error.
const DECISION_STYLE = {
  allow: { color: 'rgb(0,255,120)', label: 'ALLOW' },
  require_approval: { color: 'var(--ui-accent)', label: 'REQUIRE_APPROVAL' },
  deny: { color: 'rgb(255,64,220)', label: 'DENY' },
}

// --- small pieces ---

function SectionLabel({ children }) {
  return jsx('div', {
    className: 'text-[0.5625rem] tracking-[0.2em] text-(--ui-text-secondary) uppercase',
    style: { fontFamily: MONO },
    children,
  })
}

function StatusDot({ ok, label, colour }) {
  return jsxs('span', {
    className: 'inline-flex items-center gap-1',
    children: [
      jsx('span', {
        style: {
          width: '7px', height: '7px', display: 'inline-block',
          background: ok ? (colour || 'rgb(0,255,120)') : 'var(--ui-stroke-secondary)',
          boxShadow: ok ? `0 0 6px ${colour || 'rgb(0,255,120)'}` : 'none',
        },
      }),
      jsx('span', {
        className: 'text-[0.5625rem] text-(--ui-text-secondary)',
        style: { fontFamily: MONO },
        children: label,
      }),
    ],
  })
}

function CastChip({ member }) {
  const name = member.name || member.id || 'unknown'
  const colour = HEAD_COLOURS[name] || member.color || 'var(--ui-accent)'
  const isHuman = name === 'wætz'
  return jsxs('div', {
    className: cn(
      'flex items-center gap-2 border px-2 py-1.5',
      isHuman ? 'border-dashed' : 'border-solid'
    ),
    style: {
      fontFamily: MONO,
      borderColor: isHuman ? 'var(--ui-accent)' : 'var(--ui-stroke-secondary)',
      background: 'rgba(0,0,0,0.4)',
    },
    children: [
      jsx('span', {
        style: {
          width: '10px', height: '10px', flexShrink: 0,
          background: colour, boxShadow: `0 0 8px ${colour}`,
        },
      }),
      jsxs('span', {
        className: 'flex flex-col min-w-0',
        children: [
          jsx('span', {
            className: 'text-[0.6875rem] truncate',
            style: { color: isHuman ? 'var(--ui-accent)' : 'var(--ui-text-secondary)' },
            children: name,
          }),
          isHuman && jsx('span', {
            className: 'text-[0.5rem] tracking-[0.15em]',
            style: { color: 'var(--ui-accent)' },
            children: 'HUMAN · DIGITAL TWIN · TEST PILOT',
          }),
        ],
      }),
      member.role && !isHuman && jsx('span', {
        className: 'ml-auto text-[0.5rem] text-(--ui-text-secondary) truncate',
        children: member.role,
      }),
    ],
  })
}

// --- the live robot companion -------------------------------------------------
// The browser IS the robot's body surface. This embeds the WebGL companion
// (ANGLE/D3D11 on the discrete GPU) rather than re-implementing a renderer in
// the pane. The agent drives it over CDP; the human watches it here.
const COMPANION_URL = 'http://127.0.0.1:8161/index.html'

function Companion({ ctx }) {
  const [live, setLive] = React.useState(true)
  const [err, setErr] = React.useState(null)
  const ref = React.useRef(null)

  return jsxs('div', {
    className: 'flex flex-col gap-1.5',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between',
        children: [
          jsx(SectionLabel, { children: 'COMPANION · LIVE' }),
          jsx('button', {
            className: 'text-[0.5625rem] px-1.5 py-0.5 border border-(--ui-stroke-secondary) rounded-sm',
            style: { color: live ? 'rgb(0,255,120)' : 'var(--ui-text-secondary)', fontFamily: MONO },
            onClick: () => { setLive(!live); haptic('tap') },
            children: live ? 'LIVE' : 'PAUSED',
          }),
        ],
      }),
      jsx('div', {
        className: 'relative w-full overflow-hidden rounded-sm border border-(--ui-stroke-secondary)',
        style: { aspectRatio: '9 / 16', background: '#05070c' },
        children: jsx('iframe', {
          ref,
          src: COMPANION_URL,
          title: 'asimov companion',
          className: 'w-full h-full border-0',
          style: { pointerEvents: live ? 'auto' : 'none', opacity: live ? 1 : 0.55 },
          allow: 'autoplay',
          onError: () => setErr('companion surface unreachable'),
        }),
      }),
      err && jsx('div', {
        className: 'text-[0.5625rem]',
        style: { color: 'rgb(255,64,220)', fontFamily: MONO },
        children: err,
      }),
      jsx('div', {
        className: 'text-[0.5625rem] text-(--ui-text-secondary)',
        style: { fontFamily: MONO },
        children: 'WebGL · ANGLE D3D11 · RTX · shows anything, grants nothing',
      }),
    ],
  })
}

function DecisionCard({ decision }) {
  const d = decision.decision || decision.verdict || 'unknown'
  const style = DECISION_STYLE[d] || { color: 'var(--ui-text-secondary)', label: String(d).toUpperCase() }
  const rules = Array.isArray(decision.rules) ? decision.rules : []
  return jsxs('div', {
    className: 'border p-2 flex flex-col gap-1.5',
    style: { fontFamily: MONO, borderColor: style.color, background: 'rgba(0,0,0,0.4)' },
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between gap-2',
        children: [
          jsx('span', {
            className: 'text-sm font-bold tracking-[0.1em]',
            style: { color: style.color, textShadow: `0 0 10px ${style.color}` },
            children: style.label,
          }),
          jsx('span', {
            className: 'text-[0.625rem] text-(--ui-text-secondary)',
            children: decision.verb ? `verb: ${decision.verb}` : '',
          }),
        ],
      }),
      rules.length > 0 && jsxs('div', {
        className: 'flex flex-wrap gap-1',
        children: rules.map((r, i) =>
          jsx('span', {
            className: 'border px-1 py-0.5 text-[0.5625rem]',
            style: { borderColor: 'var(--ui-stroke-secondary)', color: 'var(--ui-text-secondary)' },
            children: typeof r === 'string' ? r : (r && (r.id || r.rule)) || JSON.stringify(r),
          }, `rule-${i}`)
        ),
      }),
      decision.reason && jsx('div', {
        className: 'text-[0.625rem] text-(--ui-text-secondary)',
        children: decision.reason,
      }),
      jsx('div', {
        className: 'text-[0.625rem]',
        style: { color: 'var(--ui-accent)' },
        children: `executed: ${decision.executed === true ? 'true' : 'false'}`,
      }),
    ],
  })
}

function LedgerRow({ ledger }) {
  const name = ledger.name || ledger.ledger || 'ledger'
  const count = ledger.entry_count ?? ledger.entries ?? ledger.count ?? 0
  const verified = ledger.chain_verified === true
  const head = String(ledger.head_hash || ledger.head || '').slice(0, 16)
  return jsxs('div', {
    className: 'border border-(--ui-stroke-secondary) px-2 py-1.5 flex flex-col gap-0.5',
    style: { fontFamily: MONO, background: 'rgba(0,0,0,0.4)' },
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between gap-2',
        children: [
          jsx('span', { className: 'text-[0.6875rem] truncate', children: name }),
          jsx('span', {
            className: 'text-[0.5rem] px-1 py-0.5 border shrink-0',
            style: verified
              ? { color: 'rgb(0,255,120)', borderColor: 'rgb(0,255,120)' }
              : { color: 'rgb(255,64,220)', borderColor: 'rgb(255,64,220)' },
            children: verified ? 'CHAIN ✓' : 'CHAIN ✗',
          }),
        ],
      }),
      jsxs('div', {
        className: 'flex items-center justify-between text-[0.5625rem] text-(--ui-text-secondary)',
        children: [
          jsx('span', { children: `${count} entries` }),
          jsx('span', { children: head ? `head ${head}` : 'head —' }),
        ],
      }),
    ],
  })
}

// --- the pane ---

function Pane({ ctx }) {
  const [status, setStatus] = React.useState(null)
  const [cast, setCast] = React.useState(null)
  const [ledger, setLedger] = React.useState(null)
  const [backendUp, setBackendUp] = React.useState(null) // null = probing
  const [verb, setVerb] = React.useState('status')
  const [decision, setDecision] = React.useState(null)
  const [planning, setPlanning] = React.useState(false)
  const [planError, setPlanError] = React.useState(null)

  // Poll status + ledger every 5s, cast every 5s (never faster than 2s).
  React.useEffect(() => {
    let alive = true
    async function tick() {
      let anyOk = false
      try {
        const s = await ctx.rest('/status')
        if (alive) setStatus(s)
        anyOk = true
      } catch (_e) { /* backend unavailable — handled below */ }
      try {
        const c = await ctx.rest('/cast')
        if (alive) setCast(Array.isArray(c) ? c : (c && c.cast) || null)
        anyOk = true
      } catch (_e) { /* ignore */ }
      try {
        const l = await ctx.rest('/ledger')
        if (alive) setLedger(Array.isArray(l) ? l : (l && l.ledgers) || null)
        anyOk = true
      } catch (_e) { /* ignore */ }
      if (alive) setBackendUp(anyOk)
    }
    tick()
    const t = setInterval(tick, 5000)
    return () => { alive = false; clearInterval(t) }
  }, [ctx])

  async function plan() {
    haptic('tap')
    setPlanning(true)
    setPlanError(null)
    try {
      const res = await ctx.rest('/plan', {
        method: 'POST',
        body: JSON.stringify({ verb }),
      })
      // A refusal is a RESULT — render the decision, never an error toast.
      setDecision(res && typeof res === 'object' ? res : { decision: 'unknown' })
    } catch (e) {
      setDecision(null)
      setPlanError('backend unavailable — /plan unreachable')
    } finally {
      setPlanning(false)
    }
  }

  const sdkOk = !!(status && (status.sdk ?? status.sdk_present ?? backendUp))
  const robotOk = !!(status && (status.robot_configured ?? status.configured ?? status.robot))
  const dryRun = !!(status && (status.dry_run ?? status.dryRun))

  const castMembers = React.useMemo(() => {
    if (!cast) return null
    const byName = {}
    for (const m of cast) {
      const n = m && (m.name || m.id)
      if (n) byName[n] = m
    }
    // Canonical five, in order; keep any extras the backend reports.
    const ordered = CAST_ORDER.map((n) => byName[n] || { name: n })
    const extras = cast.filter((m) => m && !CAST_ORDER.includes(m.name || m.id))
    return ordered.concat(extras)
  }, [cast])

  return jsxs('div', {
    className: 'flex h-full flex-col gap-3 p-2 overflow-y-auto text-sm',
    style: { fontFamily: MONO, backgroundImage: SCANLINES },
    children: [
      // 1 — header + live status dots
      jsxs('div', {
        className: 'flex flex-col gap-1.5 border-b border-(--ui-stroke-secondary) pb-2',
        children: [
          jsxs('div', {
            className: 'flex items-center justify-between',
            children: [
              jsx('span', {
                className: 'font-bold tracking-[0.15em]',
                style: { color: 'var(--ui-accent)' },
                children: 'asimov://',
              }),
              jsx('span', {
                className: 'text-[0.5rem] text-(--ui-text-secondary)',
                children: 'GOVERNANCE CONSOLE',
              }),
            ],
          }),
          jsxs('div', {
            className: 'flex items-center gap-3 flex-wrap',
            children: [
              jsx(StatusDot, { ok: sdkOk, label: 'SDK' }),
              jsx(StatusDot, { ok: robotOk, label: 'ROBOT' }),
              jsx(StatusDot, { ok: dryRun, label: 'DRY-RUN', colour: 'var(--ui-accent)' }),
            ],
          }),
          backendUp === false && jsx('div', {
            className: 'text-[0.5625rem] border px-1.5 py-1',
            style: { color: 'var(--ui-text-secondary)', borderColor: 'var(--ui-stroke-secondary)' },
            children: 'backend unavailable — waiting for plugin_api.py',
          }),
        ],
      }),

      // 2 — the cast
      jsxs('div', {
        className: 'flex flex-col gap-1.5',
        children: [
          jsx(SectionLabel, { children: 'THE CAST' }),
          castMembers
            ? jsxs('div', {
                className: 'flex flex-col gap-1',
                children: castMembers.map((m, i) => jsx(CastChip, { member: m }, `cast-${i}`)),
              })
            : jsx('div', {
                className: 'text-[0.625rem] text-(--ui-text-secondary)',
                children: backendUp === false ? 'backend unavailable' : 'loading cast…',
              }),
        ],
      }),

      // 3 — verb planner
      jsxs('div', {
        className: 'flex flex-col gap-1.5',
        children: [
          jsx(SectionLabel, { children: 'VERB PLANNER' }),
          jsxs('div', {
            className: 'flex items-center gap-1.5',
            children: [
              jsx('select', {
                className: 'flex-1 border border-(--ui-stroke-secondary) bg-black/40 px-1.5 py-1 text-[0.6875rem] text-(--ui-text-secondary) outline-none',
                style: { fontFamily: MONO },
                value: verb,
                onChange: (e) => setVerb(e.target.value),
                children: VERBS.map((v) => jsx('option', { value: v, children: v }, v)),
              }),
              jsx('button', {
                type: 'button',
                disabled: planning,
                className: cn(
                  'border px-3 py-1 text-[0.6875rem] tracking-[0.1em] transition-colors',
                  planning ? 'opacity-50' : 'hover:bg-(--ui-accent)/10'
                ),
                style: { fontFamily: MONO, borderColor: 'var(--ui-accent)', color: 'var(--ui-accent)' },
                onClick: plan,
                children: planning ? 'PLANNING…' : 'PLAN',
              }),
            ],
          }),
          planError && jsx('div', {
            className: 'text-[0.5625rem] text-(--ui-text-secondary)',
            children: planError,
          }),
          decision && jsx(DecisionCard, { decision }),
        ],
      }),

      // 4 — receipt chain
      jsxs('div', {
        className: 'flex flex-col gap-1.5',
        children: [
          jsx(SectionLabel, { children: 'RECEIPT CHAIN' }),
          ledger && ledger.length > 0
            ? jsxs('div', {
                className: 'flex flex-col gap-1',
                children: ledger.map((l, i) => jsx(LedgerRow, { ledger: l }, `ledger-${i}`)),
              })
            : jsx('div', {
                className: 'text-[0.625rem] text-(--ui-text-secondary)',
                children: backendUp === false ? 'backend unavailable' : 'no ledger entries',
              }),
        ],
      }),

      // 4.5 — the live companion surface
      jsx('div', {
        className: 'px-3 pb-2',
        children: jsx(Companion, { ctx }),
      }),

      // 5 — footer
      jsxs('div', {
        className: 'mt-auto border-t border-(--ui-stroke-secondary) pt-2 flex flex-col gap-0.5 items-center',
        children: [
          jsx('div', {
            className: 'text-[0.5625rem] tracking-[0.08em]',
            style: { color: 'var(--ui-accent)' },
            children: 'HUMAN://ROOT → æ POLICY → asimov:// → RECEIPT',
          }),
          jsx('div', {
            className: 'text-[0.5625rem] text-(--ui-text-secondary) italic',
            children: 'An address is not a permission.',
          }),
        ],
      }),
    ],
  })
}

// --- plugin entry ---

export default {
  id: ID,
  name: 'Asimov',
  defaultEnabled: true,
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'asimov://',
      data: { placement: 'right', width: '420px' },
      render: () => jsx(Pane, { ctx }),
    })
  },
}
