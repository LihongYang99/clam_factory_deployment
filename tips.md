# Project Tips

## Connect to Jetson from the VS Code terminal

On the Mac, open **Terminal → New Terminal** in VS Code and run:

```bash
ssh lihong@192.168.88.250
```

Enter the **Jetson login password**, not the Wi-Fi or MQTT password. Password
input is invisible. The Mac must have access to the router's local network.

A prompt like this confirms the terminal is on the Jetson:

```text
lihong@lihongyang2026-clam:~$
```

Commands in this terminal now run on the Jetson. Run `exit` to return to the Mac.
Terminal SSH does **not** switch the VS Code Explorer or editor to Jetson files.

## Open the dashboard from home through VT VPN

The Jetson must remain powered on and connected to both the VT campus network
and the project's router. The campus IP confirmed for this setup is
`10.141.48.234`; its project LAN IP is `192.168.88.250`.

1. Connect the Mac to **VT VPN**.
2. Open a **local Mac terminal** (including the VS Code terminal) and run:

   ```bash
   ssh -N -o ExitOnForwardFailure=yes -o ServerAliveInterval=30 -L 127.0.0.1:8001:192.168.88.250:8000 lihong@10.141.48.234
   ```

3. Enter the **Jetson login password**. With `-N`, no remote shell prompt
   appears; a quiet terminal is normal. Keep this terminal open.
4. Open **http://localhost:8001** in the Mac browser.
5. Press **Ctrl+C** in that terminal to close the tunnel when finished.

Use port **8001** consistently on the Mac; the Jetson dashboard remains on port **8000**.
The browser connects to port 8001 on the Mac. SSH carries that connection
through the Jetson's campus address to its dashboard at `192.168.88.250:8000`.
VT VPN alone does not provide access to the project's private LAN address.

If SSH times out, check the VPN connection, the Jetson's current campus IP,
and whether campus network policy permits VPN-to-Jetson SSH access. On the
Jetson, `hostname -I` lists its current addresses. If the tunnel connects but the
page fails, check that the `clam-gateway` service is running on the Jetson.

If port 8001 is already in use, first try **http://localhost:8001**: an existing
SSH tunnel may already be working. Do not start a second tunnel. To identify
its listener, run on the Mac:

```bash
lsof -nP -iTCP:8001 -sTCP:LISTEN
```

If it is an old SSH tunnel, close its terminal session with **Ctrl+C** before
reconnecting. If that terminal is unavailable, use `kill <PID>` only after
confirming the listed process is the old tunnel; replace `<PID>` with the
current process ID. Keep using port 8001.

## Edit Jetson files with Remote - SSH

Install the Microsoft **Remote - SSH** extension in VS Code if needed.
In the Mac's `~/.ssh/config`, add the following if the entry does not already exist:

```sshconfig
Host clam-jetson
    HostName 192.168.88.250
    User lihong
```

Press **Cmd+Shift+P → Remote-SSH: Connect to Host → clam-jetson**.
Enter the Jetson login password when prompted. In the remote window, use
**File → Open Folder** to select a folder on the Jetson.

The Mac repository at `/Users/lihongyang/Documents/clam_factory_deployment`
is not automatically copied to the Jetson. Open the local Mac workspace for
ESP32 USB flashing; use the remote window for gateway work on the Jetson.

For DHCP and SSH troubleshooting, see [network setup](docs/network_setup.md).
