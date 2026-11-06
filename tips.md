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
