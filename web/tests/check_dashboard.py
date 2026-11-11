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
                             probe_k=1.0, compensation_temperature_c=25.0)
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
                page.set_viewport_size({'width': width, 'height': 768 if width > 760 else 1000})
                page.goto(url)
                page.wait_for_function("document.querySelector('#value-do').textContent === '6.18 mg/L'")
                expect(page.locator('#value-conductivity')).to_have_text('1413.50 µS/cm')
                assert page.locator('#overview').is_visible()
                expect(page.locator('#sensor-nav a[href="#do"]')).to_have_css('font-size', '14.5px')
                expect(page.locator('#sensor-nav a[href="#overview"]')).to_have_css('font-size', '16px')
                expect(page.locator('#value-ph')).to_have_css('color', 'rgb(180, 35, 24)')
                expect(page.locator('header')).not_to_contain_text('192.168.88.')
                expect(page.locator('#overview')).not_to_contain_text('192.168.88.')
                assert page.locator('.vt-logo').evaluate('(e)=>e.complete && e.naturalWidth > 0')
                assert page.locator('.company-logo').evaluate('(e)=>e.complete && e.naturalWidth === 1478')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                if width > 760:
                    height = page.evaluate('document.documentElement.scrollHeight')
                    viewport_height = page.evaluate('innerHeight')
                    if height > viewport_height:
                        page.screenshot(path=str(output/f'overview-overflow-{width}.png'), full_page=True)
                    assert height <= viewport_height, f'Overview height {height}px exceeds {viewport_height}px at width {width}px'
                page.screenshot(path=str(output/f'overview-{width}.png'), full_page=True)
                network_link = page.locator('#sensor-nav a[href="#network"]')
                expect(network_link).to_have_text('IP & MAC')
                network_link.click()
                expect(network_link).to_have_attribute('aria-current', 'page')
                expect(page.locator('#network-view')).to_be_visible()
                expect(page.locator('#network-view thead th')).to_have_text(['Device', 'IP address', 'MAC address', 'Assignment'])
                expect(page.locator('#network-rows tr')).to_have_count(9)
                for name, suffix, mac, assignment in [
                    ('Router', 1, 'Not recorded', 'Configured'),
                    ('Jetson Orin Nano', 250, 'AC:3A:E2:AB:F6:AC', 'Configured'),
                    ('Node 01', 101, '64:E8:33:75:BB:4C', 'Configured'),
                    ('Node 02', 102, '30:30:F9:3B:81:B4', 'Configured'),
                    ('Node 03', 103, 'Not assigned', 'Planned'),
                    ('Node 04', 104, 'Not assigned', 'Planned'),
                    ('Node 05', 105, '44:1B:F6:FE:71:50', 'Planned'),
                    ('Camera 06', 106, 'Not assigned', 'Planned'),
                    ('Node 07', 107, 'Not assigned', 'Planned'),
                ]:
                    row = page.locator('#network-rows tr').filter(has_text=name)
                    expect(row).to_have_count(1)
                    for value in (f'192.168.88.{suffix}', mac, assignment):
                        expect(row).to_contain_text(value)
                expect(page.locator('#network-rows').get_by_text('Planned', exact=True)).to_have_count(5)
                for selector in ('#overview', '#live-detail', '#planned-view', '#temperature-view', '#prediction-view', '.timestamp'):
                    expect(page.locator(selector)).to_be_hidden()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.evaluate('window.scrollTo(0, 0)')
                page.mouse.move(min(width-10, 600), 10)
                page.wait_for_timeout(300)
                page.screenshot(path=str(output/f'network-{width}.png'), full_page=True)
                page.go_back()
                expect(page.locator('#overview')).to_be_visible()
                expect(page.locator('#network-view')).to_be_hidden()
                expect(page.locator('.timestamp')).to_be_visible()
                page.locator('#sensor-nav a[href="#temperature"]').click()
                expect(page.locator('#temperature-view')).to_be_visible()
                expect(page.locator('#temperature-average')).to_have_text('24.36')
                expect(page.locator('#temperature-count')).to_have_text('2 of 2 probes')
                expect(page.locator('#reading-temperature')).to_contain_text('25.32')
                expect(page.locator('#reading-temperature_orp')).to_contain_text('23.40')
                expect(page.locator('#temperature-row-temperature .device-ip')).to_have_text('IP: 192.168.88.101')
                expect(page.locator('#temperature-row-temperature_orp .device-ip')).to_have_text('IP: 192.168.88.102')
                expect(page.locator('#sensor-nav a[href="#temperature_orp"]')).to_have_count(0)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.evaluate('window.scrollTo(0, 0)')
                page.mouse.move(min(width-10, 600), 10)
                page.wait_for_timeout(300)
                page.screenshot(path=str(output/f'temperatures-{width}.png'), full_page=True)
                page.locator('#temperature-view a[href="#temperature_do"]').click()
                expect(page.locator('#live-detail')).to_be_visible()
                expect(page.locator('#chart-title')).to_have_text('Temperature history')
                expect(page.locator('#temperature-source')).to_be_visible()
                expect(page.locator('#temperature-source')).to_have_text('Source: Node 01 / DO probe')
                expect(page.locator('#view-subtitle')).to_contain_text('192.168.88.101')
                expect(page.locator('#sensor-nav a[href="#temperature"]')).to_have_attribute('aria-current', 'page')
                assert '25.32 °C' in page.locator('#chart title').first.text_content()
                page.locator('#sensor-nav a[href="#temperature"]').click()
                page.locator('#temperature-view a[href="#temperature_orp"]').click()
                expect(page.locator('#temperature-source')).to_have_text('Source: Node 02 / ORP probe')
                expect(page.locator('#view-subtitle')).to_contain_text('192.168.88.102')
                expect(page.locator('#chart title').first).to_contain_text('23.40 °C')
                expect(page.locator('#sensor-nav a[href="#temperature"]')).to_have_attribute('aria-current', 'page')
                page.locator('#sensor-nav a[href="#conductivity"]').click()
                expect(page.locator('#detail-title')).to_have_text('Electrical conductivity')
                expect(page.locator('.primary-reading > span').first).to_have_text('Electrical conductivity')
                expect(page.locator('#do')).to_have_text('1413.50')
                expect(page.locator('.primary-reading .unit')).to_have_text('µS/cm')
                expect(page.locator('.secondary-readings')).to_be_hidden()
                expect(page.locator('#temperature-source')).to_be_hidden()
                expect(page.locator('#view-subtitle')).to_have_text('Node 05 / Planned IP: 192.168.88.105')
                expect(page.locator('.details p').first).to_have_text('EC probe → Node 05 → MQTT → SQLite')
                expect(page.locator('#chart title').last).to_contain_text('1413.50 µS/cm')
                expect(page.locator('.accuracy-bands polygon')).to_have_count(0)
                expect(page.locator('#chart-caption')).to_have_text('Gateway receive time (µS/cm)')
                expect(page.locator('#live-detail thead th:not([hidden])')).to_have_text(['Received', 'EC (µS/cm)', 'Sensor'])
                expect(page.locator('#rows tr')).to_have_count(2)
                expect(page.locator('#rows tr').first.locator('td')).to_have_count(3)
                expect(page.locator('#rows tr').first).not_to_contain_text('25.00')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.evaluate('window.scrollTo(0, 0)')
                page.mouse.move(min(width-10, 600), 10)
                page.wait_for_timeout(300)
                page.screenshot(path=str(output/f'conductivity-{width}.png'), full_page=True)
                page.locator('#sensor-nav a[href="#do"]').click()
                expect(page.locator('.secondary-readings')).to_be_visible()
                expect(page.locator('#live-detail thead th:not([hidden])')).to_have_text(['Received', 'DO (mg/L)', 'Temperature (°C)', 'Sensor'])
                expect(page.locator('#chart title').first).to_contain_text('6.18 mg/L')
                expect(page.locator('.accuracy-bands polygon')).to_have_count(1)
                expect(page.locator('#chart-caption')).to_contain_text('±0.6 mg/L')
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
                expect(page.locator('#live-detail thead th').nth(1)).to_have_text('ORP (mV)')
                page.locator('#sensor-nav a[href="#do"]').click()
                expect(page.locator('#do')).to_have_text('6.18')
                page.locator('#pause').click()
                assert page.locator('#connection').inner_text() == 'Display paused'
                page.locator('#pause').click()
                page.evaluate('window.scrollTo(0, 0)')
                page.wait_for_timeout(300)
                assert page.evaluate("""() => {
                    const marker = document.querySelector('#nav-indicator').getBoundingClientRect();
                    const active = document.querySelector('#sensor-nav [aria-current]').getBoundingClientRect();
                    return Math.abs(marker.left - active.left) < 1 &&
                      Math.abs(marker.top - (innerWidth <= 760 ? active.bottom - 4 : active.top)) < 1;
                }""")
                page.screenshot(path=str(output/f'detail-{width}.png'), full_page=True)
                prediction_payload.update(status='waiting', latest=None)
                page.locator('#sensor-nav a[href="#predictions"]').click()
                page.evaluate('refresh()')
                expect(page.locator('#prediction-view')).to_be_visible()
                expect(page.locator('#prediction-status')).to_have_text('Waiting for LSTM results')
                expect(page.locator('#prediction-forecast-do')).to_have_text('—')
                assert page.locator('#overview').is_hidden() and page.locator('#live-detail').is_hidden()
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.evaluate('window.scrollTo(0, 0)')
                page.wait_for_timeout(300)
                page.screenshot(path=str(output/f'predictions-waiting-{width}.png'), full_page=True)
                prediction_payload.update(status='ready', latest=prediction_result)
                page.evaluate('refresh()')
                expect(page.locator('#prediction-forecast-do')).to_have_text('5.91 mg/L')
                expect(page.locator('#prediction-current-orp')).to_have_text('-120.00 mV')
                expect(page.locator('#prediction-difference-do')).to_have_text('-0.27 mg/L')
                expect(page.locator('#prediction-difference-orp')).to_have_text('+25.00 mV')
                expect(page.locator('#prediction-forecast-temperature_orp')).to_have_text('—')
                for measurement, suffix in [('do', 101), ('orp', 102), ('temperature_do', 101), ('temperature_orp', 102)]:
                    source = page.locator('#prediction-rows tr').filter(has=page.locator(f'a[href="#{measurement}"]')).locator('.prediction-source:not([id])')
                    expect(source).to_contain_text(f'192.168.88.{suffix}')
                expect(page.locator('.prediction-table thead th').nth(1)).to_have_text('Latest reading')
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
                page.evaluate('window.scrollTo(0, 0)')
                page.wait_for_timeout(300)
                page.screenshot(path=str(output/f'predictions-ready-{width}.png'), full_page=True)
                page.locator('#prediction-rows a[href="#temperature_do"]').click()
                expect(page.locator('#temperature-source')).to_have_text('Source: Node 01 / DO probe')
                page.go_back()
                page.locator('#prediction-rows a[href="#temperature_orp"]').click()
                expect(page.locator('#temperature-source')).to_have_text('Source: Node 02 / ORP probe')
                page.go_back()
                expect(page.locator('#prediction-view')).to_be_visible()
                page.locator('#prediction-pause').click()
                expect(page.locator('#prediction-status')).to_contain_text('Display paused')
                expect(page.locator('#prediction-difference-do')).to_have_text('—')
                page.locator('#prediction-pause').click()
                expect(page.locator('#prediction-status')).to_have_text('Latest LSTM predictions')
                for name, suffix in [('turbidity', 104), ('ph', 103), ('uv254', 107), ('camera', 106)]:
                    page.locator(f'#sensor-nav a[href="#{name}"]').click()
                    expect(page.locator('#planned-view')).to_be_visible()
                    expect(page.locator('#planned-facts')).to_contain_text('Planned IP')
                    expect(page.locator('#planned-facts')).to_contain_text(f'192.168.88.{suffix}')
                    assert page.locator('#live-detail').is_hidden()
                page.go_back()
                expect(page.locator('#planned-title')).to_have_text('UV254 / optical COD proxy')

            # EC is a separate measurement; compensation temperature is a setting only.
            page.goto(url+'#conductivity')
            ec_payload['server_time'] = time.time()
            ec_payload['latest'] = {'received_at':ec_payload['server_time']-5, 'sample':dict(ec_sample, conductivity_us_cm=0)}
            ec_payload['history'] = [ec_payload['latest']]
            page.evaluate('refresh()')
            expect(page.locator('#do')).to_have_text('0.00')
            expect(page.locator('#chart title')).to_contain_text('0.00 µS/cm')
            ec_payload['latest']['sample'].update(sensor_status='TIMEOUT', conductivity_us_cm=None)
            page.evaluate('refresh()')
            expect(page.locator('#do')).to_have_text('—')
            expect(page.locator('#notice')).to_contain_text('Sensor reports TIMEOUT')
            expect(page.locator('#empty')).to_be_visible()
            expect(page.locator('#rows tr td').nth(1)).to_have_text('—')
            ec_payload['latest'] = None
            ec_payload['history'] = []
            page.evaluate('refresh()')
            expect(page.locator('#received')).to_have_text('No samples yet')
            expect(page.locator('#do')).to_have_text('—')
            ec_payload['latest'] = {'received_at':ec_payload['server_time']-30, 'sample':dict(ec_sample)}
            ec_payload['history'] = [ec_payload['latest']]
            page.evaluate('refresh()')
            expect(page.locator('#connection')).to_have_text('Telemetry stale')
            expect(page.locator('#do')).to_have_text('1413.50')
            page.unroute('**/api/node_05*')
            page.route('**/api/node_05*', lambda r: r.fulfill(status=503, body='unavailable'))
            page.evaluate('refresh()')
            expect(page.locator('#connection')).to_contain_text('Gateway unavailable')
            expect(page.locator('#state-conductivity')).to_have_text('Gateway unavailable')
            page.unroute('**/api/node_05*')
            page.route('**/api/node_05*', lambda r: r.fulfill(json=ec_payload))

            # Temperature averages include only fresh, valid sources, never zero-fill failures.
            def reset_temperature_inputs():
                current = time.time()
                for node, data, temperature in [('node_01', payload, 25.32), ('node_02', orp_payload, 23.4)]:
                    data['server_time'] = current
                    data['health'] = {'subscription_ready': True, 'mqtt_connected': True, 'storage_error': False}
                    data['latest'] = {'received_at': current-5, 'sample':dict(SAMPLE, node_id=node, temperature_c=temperature, orp_mv=-120)}
                    data['history'] = [data['latest']]

            reset_temperature_inputs()
            page.goto(url+'#temperature')
            expect(page.locator('#temperature-average')).to_have_text('24.36')
            payload['latest']['sample']['temperature_c'] = 0
            page.evaluate('refresh()')
            expect(page.locator('#temperature-average')).to_have_text('11.70')
            expect(page.locator('#temperature-count')).to_have_text('2 of 2 probes')

            for invalidity in ['null', 'sensor', 'stale', 'future', 'subscription', 'mqtt', 'storage']:
                reset_temperature_inputs()
                if invalidity == 'null': payload['latest']['sample']['temperature_c'] = None
                if invalidity == 'sensor': payload['latest']['sample']['sensor_status'] = 'TIMEOUT'
                if invalidity == 'stale': payload['latest']['received_at'] = payload['server_time']-21
                if invalidity == 'future': payload['latest']['received_at'] = payload['server_time']+30
                if invalidity == 'subscription': payload['health']['subscription_ready'] = False
                if invalidity == 'mqtt': payload['health']['mqtt_connected'] = False
                if invalidity == 'storage': payload['health']['storage_error'] = True
                page.evaluate('refresh()')
                expect(page.locator('#temperature-average')).to_have_text('23.40')
                expect(page.locator('#temperature-count')).to_have_text('1 of 2 probes')
                expect(page.locator('#temperature-average-state')).to_contain_text(re.compile('one valid probe only', re.I))
                assert page.locator('#reading-state-temperature').inner_text().strip(), invalidity

            reset_temperature_inputs()
            orp_payload['latest']['sample']['temperature_c'] = None
            page.evaluate('refresh()')
            expect(page.locator('#temperature-average')).to_have_text('25.32')
            expect(page.locator('#temperature-count')).to_have_text('1 of 2 probes')
            payload['latest']['sample']['temperature_c'] = None
            page.evaluate('refresh()')
            expect(page.locator('#temperature-average')).to_have_text('—')
            expect(page.locator('#temperature-count')).to_have_text('0 of 2 probes')

            reset_temperature_inputs()
            page.evaluate('refresh()')
            expect(page.locator('#temperature-average')).to_have_text('24.36')
            page.locator('#temperature-pause').click()
            expect(page.locator('#temperature-average-state')).to_contain_text('Display paused')
            payload['latest']['sample']['temperature_c'] = 10
            orp_payload['latest']['sample']['temperature_c'] = 20
            page.evaluate('refresh()')
            expect(page.locator('#temperature-average')).to_have_text('24.36')
            expect(page.locator('#reading-temperature')).to_contain_text('25.32')
            page.locator('#temperature-pause').click()
            expect(page.locator('#temperature-average')).to_have_text('15.00')

            reset_temperature_inputs()
            page.unroute('**/api/node_01*')
            page.route('**/api/node_01*', lambda r: r.fulfill(status=503, body='unavailable'))
            page.evaluate('refresh()')
            expect(page.locator('#temperature-average')).to_have_text('23.40')
            expect(page.locator('#temperature-count')).to_have_text('1 of 2 probes')
            expect(page.locator('#reading-state-temperature')).to_contain_text('Gateway unavailable')
            page.unroute('**/api/node_01*')
            page.route('**/api/node_01*', lambda r: r.fulfill(json=payload))
            reset_temperature_inputs()

            payload['server_time'] = now+100
            page.goto(url)
            page.wait_for_function("document.querySelector('#state-do').textContent === 'Telemetry stale'")
            page.goto(url+'#predictions')
            expect(page.locator('#prediction-source-state-do')).to_have_text('Stale reading')
            expect(page.locator('#prediction-difference-do')).to_have_text('—')
            prediction_payload['server_time'] = now+2*3600
            page.evaluate('refresh()')
            expect(page.locator('#prediction-status')).to_contain_text('Update overdue')
            expect(page.locator('#prediction-forecast-do')).to_have_text('5.91 mg/L')
            prediction_payload.update(status='error', latest=None)
            page.evaluate('refresh()')
            expect(page.locator('#prediction-status')).to_contain_text('Prediction data unavailable')
            expect(page.locator('#prediction-forecast-do')).to_have_text('—')
            prediction_payload.update(status='ready', server_time=now, latest=prediction_result)
            page.evaluate('refresh()')
            expect(page.locator('#prediction-status')).to_have_text('Latest LSTM predictions')
            page.unroute('**/api/predictions')
            page.route('**/api/predictions', lambda r: r.fulfill(status=503, body='unavailable'))
            page.evaluate('refresh()')
            expect(page.locator('#prediction-status')).to_contain_text('Displayed forecasts may be old')
            expect(page.locator('#prediction-difference-orp')).to_have_text('—')
            payload['history'] = []
            payload['latest'] = None
            page.reload()
            page.wait_for_function("document.querySelector('#value-do').textContent === '—'")
            page.unroute('**/api/node_01*')
            orp_payload = dict(payload, latest={'received_at': now-5, 'sample':dict(SAMPLE, node_id='node_02', orp_mv=-120, temperature_c=23.4)}, history=[{'received_at':now-5,'sample':dict(SAMPLE,node_id='node_02',orp_mv=-120,temperature_c=23.4)}])
            page.route('**/api/node_02*', lambda r: r.fulfill(json=orp_payload))
            page.route('**/api/node_01*', lambda r: r.fulfill(status=503, body='unavailable'))
            page.reload()
            expect(page.locator("#state-do")).to_have_text("Gateway unavailable")
            assert not errors, errors
            browser.close()
    finally:
        server.shutdown()
        server.server_close()
print('PASS: responsive overview, EC values/units/history/error/stale/API states, IP & MAC registry/routing, temperature mean/eligibility/history/pause, sensor routing/history, prediction routing/units/states, planned devices.')
