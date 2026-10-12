#!/usr/bin/env python3
"""Kill all processes on a given port."""
import subprocess, sys, socket, time

port = int(sys.argv[1]) if len(sys.argv) > 1 else 8123

for attempt in range(3):
    r = subprocess.run(['netstat', '-ano'], capture_output=True, text=True)
    pids = set()
    for line in r.stdout.splitlines():
        if f':{port}' in line and 'LISTENING' in line:
            pid = line.split()[-1]
            if pid.isdigit() and pid != '0':
                pids.add(pid)
    if not pids:
        break
    for pid in pids:
        subprocess.run(['taskkill', '/F', '/PID', pid], capture_output=True)
    time.sleep(2)

# Verify
s = socket.socket()
s.settimeout(2)
r2 = s.connect_ex(('127.0.0.1', port))
status = 'FREE' if r2 != 0 else 'OPEN'
s.close()
print(f'port {port}: {status}')
