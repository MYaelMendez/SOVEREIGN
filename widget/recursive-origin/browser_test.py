"""Local Chromium smoke tests. Tests the shipped fixture, not a deployed Site.
Run: python browser_test.py (requires Playwright and a Chromium installation).
AE_DOM_ONLY=1 executes in-memory DOM tests when HTTP navigation is unavailable;
that mode does not test native module loading, HTTP, CSP, or the deployed Site.
"""
import functools
import http.server
import json
import os
import re
from pathlib import Path
import shutil
import threading
from playwright.sync_api import sync_playwright

DOM_ONLY = os.environ.get("AE_DOM_ONLY") == "1"
ROOT = Path(__file__).resolve().parent
OUT = Path(os.environ.get('AE_TEST_OUTPUT', '/tmp/ae-recursive-origin-tests'))
OUT.mkdir(parents=True, exist_ok=True)
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass
server = http.server.ThreadingHTTPServer(('127.0.0.1', 0), functools.partial(QuietHandler, directory=str(ROOT)))
threading.Thread(target=server.serve_forever, daemon=True).start()
port = server.server_address[1]
results = []
try:
    with sync_playwright() as p:
        executable = os.environ.get('CHROMIUM_PATH') or shutil.which('chromium')
        browser = p.chromium.launch(executable_path=executable, headless=True, args=['--no-sandbox'])
        for width, height in [(390,844), (1440,900), (320,568)]:
            context = browser.new_context(viewport={'width':width,'height':height}, reduced_motion='reduce', accept_downloads=True)
            page = context.new_page()
            errors, external = [], []
            page.on('pageerror', lambda error: errors.append(str(error)))
            def route_handler(route):
                url = route.request.url
                if url.startswith(f'http://127.0.0.1:{port}/'):
                    route.continue_()
                else:
                    external.append(url)
                    route.abort()
            page.route('**/*', route_handler)
            if DOM_ONLY:
                # No network navigation: exercise local source in Chromium's DOM.
                # Native module loading and HTTP/CSP integration are not tested.
                html = (ROOT/'index.html').read_text()
                demo = re.search(r'<script type="module">(.*?)</script>', html, re.S).group(1)
                html = re.sub(r'<script type="module">.*?</script>', '', html, flags=re.S)
                core = re.sub(r'^export ', '', (ROOT/'core.mjs').read_text(), flags=re.M)
                widget = re.sub(r'^import .*?;\n', '', (ROOT/'widget.mjs').read_text(), flags=re.M)
                widget = re.sub(r'^export ', '', widget, flags=re.M)
                demo = re.sub(r'^import .*?;\n', '', demo, flags=re.M)
                page.set_content(html)
                page.add_script_tag(content='(()=>{\n'+core+'\n'+widget+'\n'+demo+'\n})();')
            else:
                page.goto(f'http://127.0.0.1:{port}/index.html', wait_until='networkidle')
            page.wait_for_selector('ae-recursive-origin')
            w = page.locator('ae-recursive-origin')
            assert page.locator('ae-recursive-origin').count() == 1
            # Idempotent mounting must never duplicate the original or layer.
            page.evaluate('window.mountLayer(); window.mountLayer()')
            assert page.locator('ae-recursive-origin').count() == 1
            assert page.evaluate("window.fixtureOrigin === document.querySelector('#existing-origin')")
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
            box = w.locator('.frame').bounding_box()
            assert abs(box['width']/box['height'] - 9/16) < 0.015, box
            page.locator('#counter').click()
            assert page.locator('#count').inner_text() == '1'
            baseline_html = page.locator('#existing-origin').evaluate('(el)=>el.outerHTML')
            w.locator('#intent').fill('PRIVATE_TEST_INTENTION_DO_NOT_EXPORT')
            w.locator('#copy-context').check()
            w.locator('#child').click()
            w.locator('.child').first.click()
            assert w.locator('#intent').input_value() == 'PRIVATE_TEST_INTENTION_DO_NOT_EXPORT'
            assert 'depth 1' in w.locator('#trail').inner_text()
            w.locator('#executor').select_option('codex')
            w.locator('#name').fill('<img src=x onerror=alert(1)>')
            w.locator('#child').click()
            assert w.locator('.child').count() == 1
            w.locator('.child').first.click()
            assert 'depth 2' in w.locator('#trail').inner_text()
            assert w.locator('#intent').input_value() == ''
            w.locator('#parent').click()
            # Return from child to root, check untrusted names remain plain text.
            w.locator('#parent').click()
            assert w.locator('.child img').count() == 0
            assert '<img src=x' in w.locator('.child').inner_text()
            for alias in ['$mcp', '&mcp', '$\u00e6', '$\u2764\ufe0f']:
                w.locator('#entry').fill(alias)
                w.locator('#entry').press('Enter')
                assert w.locator('#origin-view').get_attribute('aria-pressed') == 'true'
            w.locator('#public-view').click()
            assert w.locator('#download').is_disabled()
            w.locator('#prepare').click()
            text = w.locator('#preview').inner_text()
            data = json.loads(text)
            assert len(data['environments']) == 3
            assert 'PRIVATE_TEST_INTENTION' not in text
            assert data['authority']['grant'] is None
            assert data['publication']['deployment_authorized'] is False
            w.locator('#approve').check()
            with page.expect_download() as download_info:
                w.locator('#download').click()
            download = download_info.value
            path = OUT/f'draft-{width}.json'
            download.save_as(str(path))
            assert json.loads(path.read_text()) == data
            # Editing after approval closes the export gate.
            w.locator('#origin-view').click()
            w.locator('#intent').fill('changed')
            w.locator('#public-view').click()
            assert w.locator('#download').is_disabled()
            assert not w.locator('#approve').is_checked()
            assert context.storage_state()['origins'] == []
            assert page.locator('#existing-origin').evaluate('(el)=>el.outerHTML') == baseline_html
            # Capture the actual rendered layer before removing it.
            w.locator('#origin-view').click()
            w.locator('#intent').fill('Return more time and creative freedom to the human.')
            w.locator('#name').fill('Open Sovereign / ^\u00e6')
            w.locator('.scroll').evaluate('(el)=>{el.scrollTop=0}')
            w.screenshot(path=str(OUT/f'widget-{width}.png'))
            w.locator('#remove').click()
            assert page.locator('ae-recursive-origin').count() == 0
            assert page.evaluate("window.fixtureOrigin === document.querySelector('#existing-origin')")
            assert page.locator('#existing-origin').evaluate('(el)=>el.outerHTML') == baseline_html
            page.locator('#counter').click()
            assert page.locator('#count').inner_text() == '2'
            page.locator('#mount').click()
            assert page.locator('ae-recursive-origin').count() == 1
            assert page.locator('ae-recursive-origin').locator('#intent').input_value() == ''
            assert not errors, errors
            assert not external, external
            results.append({'viewport':f'{width}x{height}','status':'pass','preservation':'same DOM node and retained listener','external_requests':0})
            context.close()
        browser.close()
finally:
    server.shutdown()
print(json.dumps({'browser':'Chromium','mode':'DOM-only, imports inlined' if DOM_ONLY else 'local HTTP with native modules','results':results,'deployment_tested':False}, indent=2))
