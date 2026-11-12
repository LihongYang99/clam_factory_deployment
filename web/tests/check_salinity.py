"""Local browser check. Requires Playwright and installed Google Chrome.
Run from the repository root: .venv/bin/python web/tests/check_dashboard.py
All telemetry is intercepted test data; no deployment database is opened.
"""
import sys
import re
import tempfile
import threading
import time
from datetime import datetime, timezone
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
            ec_sample = {key:value for key,value in SAMPLE.items() if key not in ('do_mg_l', 'temperature_c', 'saturation_pct')}
            ec_sample.update(node_id='node_05', sensor_model='EZO-EC', conductivity_us_cm=1413.5,
                             probe_k=10.0, compensation_temperature_c=25.0, salinity_psu=0.7)
            ec_payload = dict(payload, history=[{'received_at':now-10, 'sample':dict(ec_sample, sequence=32, conductivity_us_cm=1410)},
                                               {'received_at':now-5, 'sample':dict(ec_sample, sequence=33)}])
            ec_payload['latest'] = ec_payload['history'][-1]
            page.route('**/api/node_05*', lambda r: r.fulfill(json=ec_payload))
            prediction_payload = {'status':'waiting', 'server_time':now, 'horizon_hours':12, 'interval_hours':1, 'latest':None}
            page.route('**/api/predictions', lambda r: r.fulfill(json=prediction_payload))
            stamp = lambda value: datetime.fromtimestamp(value, timezone.utc).isoformat()
            prediction_result = {'generated_at':stamp(now-60), 'forecast_for':stamp(now-60+12*3600), 'model_version':'lstm-test-v1',
                                 'values':{'do':5.91, 'orp':-95, 'temperature':25.8, 'temperature_orp':None}}
            url = f'http://127.0.0.1:{server.server_port}'
            output = ROOT / 'build/dashboard'
            output.mkdir(parents=True, exist_ok=True)
            for width in [1440, 900, 390]:
                page.set_viewport_size({'width':width, 'height':900})
                page.goto(url+'#conductivity')
                expect(page.locator('#salinity')).to_have_text('0.70')
                expect(page.locator('#do')).to_have_text('1413.50')
                expect(page.locator('.salinity-line')).to_have_attribute('stroke-dasharray','6 4')
                assert page.locator('.salinity-line').get_attribute('d').count('L') == 1
                expect(page.locator('#live-detail thead th').nth(2)).to_have_text('Estimated salinity (PSU)')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.screenshot(path=str(output/f'salinity-{width}.png'),full_page=True)
            # Do not connect across an acquisition gap or a missing salt field.
            ec_payload['history'][0]['received_at'] = now-50
            page.evaluate('refresh()')
            assert 'L' not in page.locator('.salinity-line').get_attribute('d')
            ec_payload['latest']['sample'].pop('salinity_psu')
            page.evaluate('refresh()')
            expect(page.locator('#salinity')).to_have_text('—')
            ec_payload['history'] = [ec_payload['latest']]
            page.evaluate('refresh()')
            expect(page.locator('#chart-caption')).to_contain_text('No salinity samples')
            ec_payload['latest']['sample'].update(salinity_psu=0,conductivity_us_cm=0)
            page.evaluate('refresh()')
            expect(page.locator('#salinity')).to_have_text('0.00')
            ec_payload['latest']['sample'].update(salinity_psu=None,conductivity_us_cm=None,sensor_status='TIMEOUT')
            page.evaluate('refresh()')
            expect(page.locator('#salinity')).to_have_text('—')
            expect(page.locator('.salinity-line')).to_have_attribute('d','')
            page.locator('#sensor-nav a[href="#do"]').click()
            expect(page.locator('#salinity-reading')).to_be_hidden()
            assert not errors, errors
            browser.close()
            print('Salinity browser checks passed: 1440, 900, 390 px; legacy, zero, error, navigation.')
    finally:
        server.shutdown()
        server.server_close()
