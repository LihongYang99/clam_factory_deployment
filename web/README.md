# Monitoring dashboard

Standalone HTML/CSS/JavaScript, served by `gateway/app.py`. No npm install or
frontend build step. Follow [dashboard setup](../docs/dashboard_setup.md) to
configure the Jetson receiver and open `http://192.168.88.250:8000`.

The page polls `/api/node_01` every five seconds and shows DO, temperature,
saturation, sample quality, receive age, 15-minute/one-hour DO history, and an
accessible table of recent samples. Pause display pauses browser polling only;
the recorder continues collecting. No simulated values are included.

Charts use gateway receive time; node UTC is not invented when unsynchronized.
Old readings remain visible with stale/disconnected labels. Sensor errors are
separate from reception freshness. The browser never receives MQTT credentials.

Design: white workspace, deep blue text, restrained blue curve, amber quality
notice, local system fonts, visible keyboard focus and responsive layout. No
control actions or BOD predictions are included in this first version.

Chrome rendering was checked at 1440, 900, and 390 pixels wide with isolated test
responses. Checks covered the logo, horizontal overflow, responsive chart labels,
pause/resume, time window, sample table, stale/empty data, and API failure.
These checks do not verify live Jetson recording; see the setup guide's limits.

For HTML/CSS/JavaScript-only updates, run this from the Mac repository root:

```bash
rsync -av web lihong@192.168.88.250:~/clam_factory_deployment/
```

Refresh the dashboard afterward. A gateway restart is unnecessary for these
static-file changes.

The header uses the owner-provided horizontal BSE logo at
`gateway/images/vt-bse-logo.png`, unchanged and at its original aspect ratio.
It is served locally through `/vt-bse-logo.png` and displayed on a light panel
for legibility. Sync `web/`, `gateway/images/`, and `gateway/app.py`, then restart
the gateway when adding or changing the image route.

## Worker overview and measurement navigation

The overview and left navigation list Chemical properties first, followed by
Physical properties and Image information. The left navigation opens each measurement;
on small screens it becomes a horizontally scrollable navigation strip.
Temperature and DO use the same Node 01 telemetry, with separate trend units.
Other entries describe planned devices and never display invented readings or
camera images. Hash links support browser back/forward and direct detail links.
Technical acquisition information is collapsed in the detail view.

Run the isolated browser regression check from the repository root:

```bash
# Development-only dependency; not required on the Jetson.
.venv/bin/pip install playwright
.venv/bin/python web/tests/check_dashboard.py
```

The check uses installed Google Chrome, a temporary database and intercepted
fixture responses. Screenshots in `build/dashboard/` contain test data only.

Temperature is source-specific: the current reading is labeled DO probe / Node 01.
Future temperature-capable nodes must retain their own source, timestamps and
quality flags; this view does not average them or imply one shared temperature.

## Manufacturer specification shading

Trend shading is a nominal manufacturer-specification band, not a confidence
interval or verified field uncertainty. Calibration and compensation status
remain independent. Bands break at invalid readings, sequence gaps, boot changes
and gaps over 20 seconds, like the measurement line.

- SEN0681 DO: ±3% FS on 0–20 mg/L = ±0.6 mg/L. Temperature: ±0.5°C at 25°C.
  Source: https://wiki.dfrobot.com/sen0681/
- SEN0709 ORP: ±5 mV specified at 25°C in 222 mV standard; temperature ±0.5°C.
  Source: https://wiki.dfrobot.com/sen0709/

The displayed ORP band is a reference to that specified condition, not a guarantee
across the entire range or current field conditions. Planned instruments have
no invented accuracy bands. “Not integrated” is red and retains its text label.
