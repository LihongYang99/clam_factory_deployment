# Monitoring Web Interface

This folder owns the dashboard frontend, separate from sensor firmware and the
planned `gateway/` backend. No running web page or server is implemented yet.

First view: Node 01 DO (mg/L), temperature (°C), saturation (%), recent trends,
last update time, and explicit online/stale/sensor-error states. Use an English,
responsive, dark industrial layout. Controls and VT branding come later.

The gateway will receive `clam/node_01/telemetry`, record the original payload
and receive timestamp, and expose readings to this page. The browser must not
contain Wi-Fi or MQTT credentials or connect directly to the broker.

The first firmware can be commissioned with USB and Wi-Fi before the gateway
exists. Its default local configuration has MQTT disabled; this does not yet
send data to a web page. Next, configure the Jetson broker, implement ingestion
and storage in `gateway/`, and build the frontend here against its API.

Start with the [Jetson MQTT setup](../gateway/README.md) to verify incoming telemetry.
