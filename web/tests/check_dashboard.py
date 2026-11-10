"""Local browser check. Requires Playwright and installed Google Chrome.
Run from the repository root: .venv/bin/python web/tests/check_dashboard.py
All telemetry is intercepted test data; no deployment database is opened.
"""
import sys
import tempfile
import threading
import time
from pathlib import Path
from http.server import ThreadingHTTPServer
from playwright.sync_api import sync_playwright, expect

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'gateway'))
sys.path.insert(0, str(ROOT / 'gateway/tests'))
from app import Store, handler_for
from test_app import SAMPLE

with tempfile.TemporaryDirectory() as folder:
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler_for(Store(Path(folder)/'test.db')))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(channel='chrome', headless=True)
            page = browser.new_page()
            errors = []
            page.on('pageerror', lambda e: errors.append(str(e)))
            now = time.time()
            payload = {'server_time': now, 'stale_after_seconds': 20,
                       'health': {'subscription_ready': True, 'mqtt_connected': True, 'storage_error': False},
                       'history': [{'received_at': now-5, 'sample': dict(SAMPLE, do_mg_l=6.18, temperature_c=25.32)}]}
            payload['latest'] = payload['history'][-1]
            orp_payload = dict(payload, latest={'received_at': now-5, 'sample':dict(SAMPLE, node_id='node_02', orp_mv=-120, temperature_c=23.4)}, history=[{'received_at':now-5,'sample':dict(SAMPLE,node_id='node_02',orp_mv=-120,temperature_c=23.4)}])
            page.route('**/api/node_02*', lambda r: r.fulfill(json=orp_payload))
            page.route('**/api/node_01*', lambda r: r.fulfill(json=payload))
            url = f'http://127.0.0.1:{server.server_port}'
            output = ROOT / 'build/dashboard'
            output.mkdir(parents=True, exist_ok=True)
            for width in [1440, 900, 390]:
                page.set_viewport_size({'width': width, 'height': 768 if width > 760 else 1000})
                page.goto(url)
                page.wait_for_function("document.querySelector('#value-do').textContent === '6.18 mg/L'")
                assert page.locator('#overview').is_visible()
                assert page.locator('.vt-logo').evaluate('(e)=>e.complete && e.naturalWidth > 0')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                if width > 760:
                    assert page.evaluate('document.documentElement.scrollHeight <= innerHeight'), 'Overview should fit desktop height'
                page.screenshot(path=str(output/f'overview-{width}.png'), full_page=True)
                page.locator('#sensor-nav a[href="#temperature"]').click()
                expect(page.locator('#live-detail')).to_be_visible()
                expect(page.locator('#chart-title')).to_have_text('Temperature history')
                expect(page.locator('#temperature-source')).to_be_visible()
                assert '25.32 °C' in page.locator('#chart title').first.text_content()
                page.locator('#sensor-nav a[href="#do"]').click()
                expect(page.locator('#chart title').first).to_contain_text('6.18 mg/L')
                page.wait_for_timeout(300)
                assert page.evaluate("""() => {
                    const marker = document.querySelector('#nav-indicator').getBoundingClientRect();
                    const active = document.querySelector('#sensor-nav [aria-current]').getBoundingClientRect();
                    return Math.abs(marker.left - active.left) < 1 &&
                      Math.abs(marker.top - (innerWidth <= 760 ? active.bottom - 4 : active.top)) < 1;
                }""")
                page.emulate_media(reduced_motion='reduce')
                page.locator('#sensor-nav a[href="#temperature"]').click()
                assert page.locator('#nav-indicator').evaluate('(e) => e.getAnimations().length === 0')
                page.locator('#sensor-nav a[href="#do"]').click()
                page.emulate_media(reduced_motion='no-preference')
                page.locator('#sensor-nav a[href="#orp"]').click()
                expect(page.locator('#do')).to_have_text('-120.00')
                expect(page.locator('#temp')).to_have_text('23.40')
                expect(page.locator('#chart title').first).to_contain_text('-120.00 mV')
                page.locator('#sensor-nav a[href="#do"]').click()
                expect(page.locator('#do')).to_have_text('6.18')
                page.locator('#pause').click()
                assert page.locator('#connection').inner_text() == 'Display paused'
                page.locator('#pause').click()
                page.screenshot(path=str(output/f'detail-{width}.png'), full_page=True)
                for name in ['turbidity', 'tss', 'ph', 'uv254', 'camera']:
                    page.locator(f'#sensor-nav a[href="#{name}"]').click()
                    expect(page.locator('#planned-view')).to_be_visible()
                    assert page.locator('#live-detail').is_hidden()
                page.go_back()
                expect(page.locator('#planned-title')).to_have_text('UV254 / optical COD proxy')
            payload['server_time'] = now+100
            page.goto(url)
            page.wait_for_function("document.querySelector('#state-do').textContent === 'Telemetry stale'")
            payload['history'] = []
            payload['latest'] = None
            page.reload()
            page.wait_for_function("document.querySelector('#value-do').textContent === '—'")
            page.unroute('**/api/node_01*')
            orp_payload = dict(payload, latest={'received_at': now-5, 'sample':dict(SAMPLE, node_id='node_02', orp_mv=-120, temperature_c=23.4)}, history=[{'received_at':now-5,'sample':dict(SAMPLE,node_id='node_02',orp_mv=-120,temperature_c=23.4)}])
            page.route('**/api/node_02*', lambda r: r.fulfill(json=orp_payload))
            page.route('**/api/node_01*', lambda r: r.fulfill(status=503, body='unavailable'))
            page.reload()
            page.wait_for_function("document.querySelector('#overview-status').textContent.includes('Gateway unavailable')")
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
print('PASS: responsive overview, sensor routing/history, chart units, planned devices, pause, stale, empty, API failure.')
