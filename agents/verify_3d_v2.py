import asyncio, json, websockets, urllib.request

async def main():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9333/json/list').read())
    page = next((t for t in tabs if t['type']=='page' and 'Omnibox' not in t.get('title','')), None)
    ws_url = page['webSocketDebuggerUrl']
    print('Target:', page.get('title','')[:50])

    async with websockets.connect(ws_url, max_size=2**20, ping_interval=None, ping_timeout=None) as ws:
        pending, nid_counter = {}, [0]
        errors = []

        async def reader():
            while True:
                try:
                    data = await asyncio.wait_for(ws.recv(), timeout=0.1)
                except:
                    return
                msg = json.loads(data)
                mid = msg.get('id')
                if mid:
                    pending[mid] = msg
                elif msg.get('method') == 'Runtime.consoleAPICalled':
                    lvl = msg.get('params',{}).get('level','')
                    txt = ' '.join(str(a.get('value','')) for a in msg.get('params',{}).get('args',[]))
                    if lvl == 'error' or 'error' in txt.lower():
                        errors.append('[' + lvl + '] ' + txt[:200])
                elif msg.get('method') == 'Runtime.exceptionThrown':
                    t = msg.get('params',{}).get('exceptionDetails',{}).get('text','')
                    errors.append(t[:150])

        rt = asyncio.create_task(reader())

        async def eval_expr(expr):
            nid_counter[0] += 1
            mid = nid_counter[0]
            msg = {'method': 'Runtime.evaluate', 'params': {'expression': expr, 'returnByValue': True}, 'id': mid}
            await ws.send(json.dumps(msg))
            for _ in range(30):
                if mid in pending:
                    r = pending.pop(mid)
                    return r.get('result', {}).get('result', {}).get('value', None)
                await asyncio.sleep(0.1)
            return None

        # Wait for page to render
        await asyncio.sleep(7)

        print()
        print('=== Scene Verification ===')
        checks = [
            ('THREE', 'typeof THREE'),
            ('ThreeVideoPlayer', 'typeof window.ThreeVideoPlayer'),
            ('fleetWaves', 'typeof window.fleetWaves'),
            ('__renderFrame', 'typeof window.__renderFrame'),
            ('bootDone', 'document.getElementById("boot")?.classList?.contains("done") || false'),
            ('canvas', 'document.querySelector("canvas") ? "yes" : "no"'),
            ('bootText', '(document.getElementById("boot")?.textContent || "none").trim().substring(0,80)'),
            ('fleetApi', 'window.fleetWaves ? Object.keys(window.fleetWaves).join(",") : "none"'),
            ('hud', 'document.getElementById("hud") ? "yes" : "no"'),
            ('bPlay', 'document.getElementById("bPlay") ? "yes" : "no"'),
        ]

        for label, expr in checks:
            v = await eval_expr(expr)
            ok = v not in ('undefined', 'no', 'none', 0, False, None)
            print('  ' + ('✅' if ok else '❌') + ' ' + label + ': ' + repr(v))

        if errors:
            print()
            print('Errors:')
            for e in errors:
                print('  ❌', e)
        else:
            print()
            print('No console errors')

        rt.cancel()
        try: await rt
        except: pass

asyncio.run(main())
