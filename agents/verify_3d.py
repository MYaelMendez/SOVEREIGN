import asyncio, json, websockets, urllib.request, base64

async def main():
    tabs = json.loads(urllib.request.urlopen('http://127.0.0.1:9333/json/list').read())
    page = next((t for t in tabs if t['type']=='page' and 'Omnibox' not in t.get('title','')), None)
    if not page:
        print('No page'); return
    print('Target:', page.get('title','')[:50])
    ws_url = page['webSocketDebuggerUrl']

    async with websockets.connect(ws_url, max_size=2**20, ping_interval=None, ping_timeout=None) as ws:
        nid = [0]
        pending = {}
        errors = []

        async def reader():
            while True:
                try:
                    data = await asyncio.wait_for(ws.recv(), timeout=0.2)
                except (asyncio.TimeoutError, websockets.exceptions.ConnectionClosed):
                    return
                msg = json.loads(data)
                mid = msg.get('id')
                if mid:
                    pending[mid] = msg
                elif msg.get('method') == 'Runtime.exceptionThrown':
                    t = msg.get('params',{}).get('exceptionDetails',{}).get('text','')
                    errors.append(t[:150])
                elif msg.get('method') == 'Runtime.consoleAPICalled':
                    lvl = msg.get('params',{}).get('level','')
                    txt = ' '.join(str(a.get('value','')) for a in msg.get('params',{}).get('args',[]))
                    if lvl == 'error' or 'error' in txt.lower():
                        errors.append('[' + lvl + '] ' + txt[:200])

        async def cmd(method, params=None):
            nid[0] += 1
            mid = nid[0]
            await ws.send(json.dumps({'method': method, 'params': params or {}, 'id': mid}))
            for _ in range(60):
                if mid in pending:
                    return pending.pop(mid)
                await asyncio.sleep(0.1)
            return None

        reader_task = asyncio.create_task(reader())

        await cmd('Runtime.enable')
        await cmd('Page.enable')
        await cmd('Page.navigate', {'url': 'http://127.0.0.1:8125/aipodcast_me/video-edit-3d.html'})
        print('Waiting 6s for render...')
        await asyncio.sleep(6)

        if errors:
            print('Errors:')
            for e in errors:
                print('  ', e)
        else:
            print('No console errors')

        # Evaluate all checks in one batch
        script = """
const results = {};
results.THREE = typeof THREE;
results.ThreeVideoPlayer = typeof window.ThreeVideoPlayer;
results.fleetWaves = typeof window.fleetWaves;
results.__renderFrame = typeof window.__renderFrame;
results.bootDone = document.getElementById('boot')?.classList?.contains('done') || false;
results.canvas = document.querySelector('canvas') ? 'yes' : 'no';
results.hud = document.getElementById('hud') ? 'yes' : 'no';
results.bPlay = document.getElementById('bPlay') ? 'yes' : 'no';
results.selector = document.querySelectorAll('#selector .obj').length;
results.scanlines = document.querySelector('.scan') ? 'yes' : 'no';
if (window.fleetWaves) results.fleetApi = Object.keys(window.fleetWaves).join(',');
JSON.stringify(results)
"""
        r = await cmd('Runtime.evaluate', {'expression': script, 'returnByValue': True})
        if r:
            val = r.get('result', {}).get('result', {}).get('value', {})
            print()
            print('=== Scene Verification ===')
            for k, v in val.items():
                ok = v not in ('undefined', 'no', 'none', 0, False, None)
                print('  ' + ('✅' if ok else '❌') + ' ' + str(k) + ': ' + repr(v))
        else:
            print('Evaluation timed out')

        # Screenshot
        r2 = await cmd('Page.captureScreenshot', {'format': 'png', 'quality': 100})
        if r2 and r2.get('result', {}).get('data'):
            img = base64.b64decode(r2['result']['data'])
            with open('C:/Users/yaelm/AppData/Local/Temp/video-edit-3d-final.png', 'wb') as f:
                f.write(img)
            print()
            print('Screenshot: ' + str(len(img)) + ' bytes')
            if len(img) > 100000:
                print('  -> >100KB, scene rendered with content')
            else:
                print('  -> <100KB, may be mostly black')

        reader_task.cancel()
        try:
            await reader_task
        except:
            pass

asyncio.run(main())
