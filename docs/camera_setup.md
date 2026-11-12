# Camera 06 preview

Barlus IPC5MPIR-PBX10 connects to a router LAN port (currently port 4).
Current camera address: `192.168.88.106/24`; MAC: `00:12:35:02:DF:76`.
Configured on the camera through ONVIF SetNetworkInterfaces (eth0, DHCP off).
The camera no longer requires the Jetson's temporary `192.168.1.200` address.
Reserve/exclude `.106` in the router DHCP configuration to prevent future conflicts.

ONVIF GetStreamUri (media service port 8899, profile 001) supplied the RTSP URL.
It is stored only in the Jetson's private `gateway/.env` as `CAMERA_RTSP_URI`.
Never commit or display this URL: it may include camera credentials.

`gateway/camera.py` uses system Python and GStreamer to decode H.264 over TCP.
The gateway retains only the latest JPEG in memory; it does not record video or
audio. `/api/camera` exposes freshness and gateway frame-receive time;
`/camera.jpg` returns a fresh JPEG, or HTTP 503 when unavailable.
Receive time is not a verified camera exposure timestamp.

The RGB camera page refreshes every two seconds. Frames expire after ten
seconds; connection failures trigger automatic retries. The overview shows
camera availability. MQTT sensor collection remains independent.

After syncing gateway changes:

```bash
sudo systemctl restart clam-gateway
systemctl is-active clam-gateway
```

Open the normal dashboard and select **RGB camera**. For home access use the
existing SSH tunnel at `http://localhost:8001/#camera`.
