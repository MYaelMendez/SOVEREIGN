#!/usr/bin/env python3
"""Patch vps_node.py with audit endpoint."""
import sys

path = "/opt/aevps/vps_node.py"

with open(path, 'r') as f:
    src = f.read()

# 1. Add audit GET handler after status
old_get = '        if self.path.startswith("/xrpc/ae.vps.status"):\n            return self._send(200, route("status"))'
new_get = '        if self.path.startswith("/xrpc/ae.vps.status"):\n            return self._send(200, route("status"))\n        if self.path.startswith("/xrpc/ae.vps.audit"):\n            return self._send(200, route("audit"))'
src = src.replace(old_get, new_get)

# 2. Add audit route
old_route = '    if path == "markets":'
new_route = '    if path == "audit":\n        events = _STORE.get("ae.core#ledgerEvent", [])\n        posts = _STORE.get("ae.social#post", [])\n        return {"vps": "up", "ledger": len(events), "posts": len(posts), "audit": True}\n    if path == "markets":'
src = src.replace(old_route, new_route)

with open(path, 'w') as f:
    f.write(src)

print("patched")
