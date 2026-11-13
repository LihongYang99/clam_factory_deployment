# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Clam seafood processing factory workers. The project is developed by a Virginia
Tech student intern.

## Product Purpose

Provide an overview of water quality measurements and images, with navigation to
individual measurement details. Support a future multimodal BOD prediction study.

## Capabilities and Constraints

Monitoring only in the first phase. Node 01 supplies DO, temperature, and oxygen
saturation; Node 02 supplies ORP and temperature; Node 05 supplies EC and estimated
salinity. Camera 06 supplies RGB previews through a separate RTSP path. Remaining
devices are planned. No readings, images, operating limits, forecasts, or verified
calibration may be invented. The prediction page is a placeholder for future
hourly, 12-hour-ahead DO, ORP, and source-temperature results.

The overview groups temperature, turbidity and electrical conductivity under physical properties;
DO, ORP, pH and UV254 under chemical properties; RGB under image information.
These are navigation categories approved by the owner, not a comprehensive
scientific classification. Each measurement has a sidebar destination.

## Operating Context

The gateway runs on a Jetson Orin Nano on the local network. MQTT telemetry is
stored in SQLite and served through a Python HTTP service to a plain HTML/CSS/JS
frontend. Workers use the overview; technical detail remains available for
commissioning and troubleshooting.

## Brand Commitments

English interface. Preserve the title “Clam processing water quality dashboard”
and the owner-provided Virginia Tech BSE and Bumble Bee Seafood Company logos.
Use Calibri with system fallbacks.

## Evidence on Hand

Nodes 01, 02, and 05 have delivered telemetry through MQTT to the dashboard.
Calibration and compensation remain unverified. Real camera frames were displayed
before the November 12 address change; stream recovery at the new address is
pending verification. See README.md for the current node map and deployment status.

Owner-approved visual direction: white background, deep blue text, simple sans-serif
type and a small clam outline. Temperature readings must stay identifiable by
source sensor. The temperature page compares configured probe modules and
automatically averages current, valid readings, with a visible contributor count.
The average is for display; source readings, history and quality remain separate.
