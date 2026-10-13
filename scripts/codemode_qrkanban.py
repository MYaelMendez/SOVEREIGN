# æ://code_mode — /qr-kanban through the DSL
# This code is model-written and sandboxed: no import, no open, no subprocess.
# The æ.* bindings it calls run trusted in the executor.

board = æ.kanban.board()
print(f"board: {len(board)} task(s)")
for t in board:
    print(f"  {t['id']}  {t['status']:8}  {t['title'][:44]}")

verbs = æ.kanban.verbs()
print(f"verbs: {len(verbs)} -> {sorted(verbs)}")

if board:
    tid = board[0]["id"]
    task = æ.kanban.inspect(tid)
    print(f"inspect {tid}: status={task['status']} created_by={task['created_by']}")

# audit the kanban substrate — a real probe, not an assumption
audit = æ.keeper.audit("kanban")
print(f"audit: {audit['verdict']} -> {audit['evidence'][0]['evidence']}")

# reconcile: the shim must delegate to a module that actually defines produce()
shim_ok = "ae.supervision" in æ.storage.read("C:/æ/site/agents/qr_supervision.py")
canon_ok = "def produce" in æ.storage.read("C:/æ/aeqr/ae/supervision.py")
rec = æ.keeper.reconcile(str(shim_ok), str(canon_ok))
print(f"reconcile shim->canonical: match={rec['match']}")

# dry dispatch — no board write, signature gate not exercised
dry = æ.kanban.dispatch("claim", board[0]["id"], dry=True) if board else {}
print(f"dry dispatch: {dry.get('rest')} ok={dry.get('ok')}")

# ledger the receipt — evidence required; a claim without proof is refused
sig = æ.keeper.ledger({
    "kind": "verification",
    "action": "code-mode /qr-kanban",
    "evidence": f"board={len(board)} verbs={len(verbs)} audit={audit['verdict']} recon={rec['match']} dry_ok={dry.get('ok')}",
})
print(f"ledger sig: {sig}")
