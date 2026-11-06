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

Design: dark blue-gray instrument panel, cyan water-quality curve, amber quality
notice, local system fonts, visible keyboard focus and responsive layout. No
control actions or BOD predictions are included in this first version.

Desktop and narrow-window Chrome rendering were inspected locally. Jetson live
recording and browser verification are pending; see the setup guide's limits.

The header uses the owner-provided horizontal BSE logo at
`gateway/images/vt-bse-logo.png`, unchanged and at its original aspect ratio.
It is served locally through `/vt-bse-logo.png` and displayed on a light panel
for legibility. Sync `web/`, `gateway/images/`, and `gateway/app.py`, then restart
the gateway when adding or changing the image route.
