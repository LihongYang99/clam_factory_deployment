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

Monitoring only in the first phase. Node 01 supplies dissolved oxygen,
temperature and oxygen saturation. Other devices in the README node map are
planned; no readings, images, operating limits or verified calibration may be
invented. Temperature and DO share Node 01.

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
and the owner-provided Virginia Tech BSE logo.

## Evidence on Hand

Node 01 telemetry has been received through MQTT. Calibration and compensation
remain unverified. No camera feed is available. See README.md for the node map.

Owner-approved visual direction: white background, deep blue text, simple sans-serif
type and a small clam outline. Temperature readings must stay identifiable by
source sensor; only the Node 01 DO probe currently supplies temperature.
