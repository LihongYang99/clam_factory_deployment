# Monitoring dashboard

Standalone HTML/CSS/JavaScript, served by `gateway/app.py`. No npm install or
frontend build step. Follow [dashboard setup](../docs/dashboard_setup.md) to
configure the Jetson receiver and open `http://192.168.88.250:8000`.

The page polls `/api/node_01`, `/api/node_02`, `/api/node_05`, and `/api/predictions`
every five seconds and shows DO, ORP, electrical conductivity, estimated salinity,
source-specific temperatures, oxygen saturation,
sample quality, receive age, 15-minute/one-hour history, and an
accessible table of recent samples. Pause display freezes sensor and prediction
updates in the browser; the recorder continues collecting. The camera refreshes
independently every two seconds. No simulated values are included.

Charts use gateway receive time; node UTC is not invented when unsynchronized.
Old readings remain visible with stale/disconnected labels. Sensor errors are
separate from reception freshness. The browser never receives MQTT credentials.

Design: white workspace, deep blue text, restrained blue curve, amber quality
notice, Calibri with system fallbacks, visible keyboard focus and responsive layout. No
control actions or BOD predictions are included in this version.

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
for legibility. Beside it, the owner-provided company logo is stored unchanged
at `web/logo-company-VT/Bumble Bee Seafood Company Logo.png` and served through
`/bumble-bee-logo.png`. Both images keep their original aspect ratios; the
header wraps on narrow screens.

Adding this company logo also adds a gateway image route. Sync the frontend and
server, then restart the gateway so the image loads:

```bash
rsync -av web lihong@192.168.88.250:~/clam_factory_deployment/
rsync -av gateway/app.py lihong@192.168.88.250:~/clam_factory_deployment/gateway/
ssh -t lihong@192.168.88.250 'sudo systemctl restart clam-gateway && systemctl is-active clam-gateway'
```

If changing the VT image, also sync `gateway/images/`.

## Worker overview and measurement navigation

The overview and left navigation list Chemical properties first, followed by
Physical properties and Image information. The left navigation opens each measurement;
on small screens it becomes a horizontally scrollable navigation strip.
The Temperature navigation entry compares the temperature modules in connected
probes. Source-specific readings and history remain available from the overview
and each probe link.
RGB camera opens the live preview, also shown as a small Overview thumbnail.
Live JPEG delivery at camera address `192.168.88.106` was verified on November 14,
2026; see [camera setup](../docs/camera_setup.md) for the checks and remaining
validation. This dated check does not override the live availability indicator.
Unintegrated devices show their
planned state without invented readings. Hash links support browser back/forward and direct detail links.
Technical acquisition information is collapsed in the detail view.

Select **IP & MAC** in the sidebar (`#network`) for the router, Jetson and node
address registry. Overview and the header keep addresses out of the readings.
The registry distinguishes configured from planned IPs and labels unknown MACs
as **Not recorded** or **Not assigned**. Jetson's listed MAC is its Ethernet
interface; Node 01 and Node 02 use their Wi-Fi MACs. Temperature modules share
their probe node's address, so each board appears once.

These are recorded LAN assignments, not live discovery or connection status.
Maintain the `addresses` map and `setupNetwork()` device records in `web/app.js`
when hardware or router reservations change. Probe details, temperature
comparison and prediction sources retain their source IPs for troubleshooting.

## Electrical conductivity

**Electrical conductivity** opens Node 05's Atlas EZO-EC reading and history in
µS/cm, from `conductivity_us_cm`. Zero is a valid conductivity reading. Missing
or invalid readings remain blank; stale or disconnected readings retain their
status. No accuracy band is shown because a verified probe specification has
not been supplied.

The same detail page displays EZO-derived estimated salinity from `salinity_psu`:
a dashed orange line on the right axis (0–42 PSU), alongside the solid teal EC
line on the left. Both come from the same probe. Older samples without salinity
remain missing; neither calibration nor compensation is verified.

The EZO-EC does not measure water temperature. Its optional `probe_k` and
`compensation_temperature_c` fields are configuration settings, not additional
measurements. Node 05 has no temperature/saturation cards or temperature history
column, and it does not contribute to the temperature average or prediction rows.
Its IP assignment remains **Planned** in the address registry until the physical
DHCP reservation is confirmed; the identified board MAC is `44:1B:F6:FE:71:50`.

Deploy both the frontend and gateway when enabling Node 05, then restart
`clam-gateway` so `/api/node_05` is available. No production readings are seeded.

## Prediction dashboard

Select **Prediction dashboard** beside Overview to compare the latest measured
DO, ORP, and each probe's temperature with a 12-hour LSTM forecast. Differences
are shown only when both the measurement and prediction are current. Missing
predictions stay blank; no demo forecasts are published. Results older than
90 minutes are labeled overdue. API failures and paused displays retain visible
timestamps and clearly label any cached result as old or paused.

The target cadence is one model run per hour. No trained model or hourly job is
included yet; browser refresh only reads results. The page shows a waiting state
until a producer writes a valid batch. See [prediction results](../docs/predictions.md)
for the result file, units, timestamps, and model integration contract.

This feature adds a gateway API. Deploy **both `web/` and `gateway/`**, then restart
`clam-gateway` as described in [dashboard setup](../docs/dashboard_setup.md).
Copying only `web/` to an older gateway will show a prediction API error.

Run the isolated browser regression check from the repository root:

```bash
# Development-only dependency; not required on the Jetson.
.venv/bin/pip install playwright
.venv/bin/python web/tests/check_dashboard.py
```

The check uses installed Google Chrome, a temporary database and intercepted
fixture responses. Screenshots in `build/dashboard/` contain test data only.

## Temperature comparison and average

Open **Temperature** to see each probe's latest temperature and an arithmetic
mean. DO / Node 01 and ORP / Node 02 are currently configured. All configured
temperature modules participate automatically; no location or manual grouping
is required. The page shows how many probes contribute and why others do not.

The mean includes only finite temperature values from successful API responses,
with a connected MQTT receiver, ready subscription, healthy storage,
`sensor_status=OK`, and a gateway receive age within that node's freshness limit
(currently 20 seconds). Null, invalid, stale and disconnected sources are
excluded. Zero degrees is a valid value. One contributor is explicitly labeled
as a single-probe reading; no contributors shows a dash rather than zero.

This is a display average of the latest eligible readings, not simultaneous
sampling or a calibration correction. It does not overwrite individual readings,
SQLite history, or source-specific temperature predictions, and it does not
improve or certify probe accuracy. Each row keeps its source and receive time.
Pause display freezes the displayed readings and mean until resumed.

`#temperature` opens the comparison; `#temperature_do` and `#temperature_orp`
open the existing individual histories. When integrating another temperature
module, add a live measurement with `key: 'temperature_c'`, a unique ID, the
`Node NN` source and `probe` label in `web/app.js`. Add its reserved IP to the
address map and implement its gateway API as part of node integration. It then
joins the comparison and average automatically; unintegrated nodes are not included.

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
