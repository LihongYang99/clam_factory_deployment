# LAN address reservations

Use DHCP on each device and reserve its address in the MikroTik router.
One board is one node; Node 01 uses `.101`, Node 02 `.102`, and so on.

| Device | Address | Verification |
| --- | --- | --- |
| Router / WebFig | `192.168.88.1` | WebFig accessible |
| Node 01 | `192.168.88.101` | Address and Active Address match after board reset |
| Node 02 | `192.168.88.102` | Confirmed in serial diagnostics on 2026-11-10 |
| Node 03–07 | `192.168.88.103`–`192.168.88.107` | Planned; slot 06 reserved for camera |
| Jetson Orin Nano | `192.168.88.250` | Owner confirmed `hostname -I` includes this address |

## Reserve an address

1. Connect the device to the router. For an ESP32, read its station MAC from
   the serial `event=STATUS` line.
2. Open [WebFig](http://192.168.88.1) → **IP → DHCP Server → Leases**.
3. Open the lease whose **MAC Address** matches the device. Check the target
   address against existing leases and manually configured devices before using it;
   a failed ping alone does not prove an address is free.
4. Click **Make Static**. This reserves the existing address; it does not choose
   the project's sequential address automatically.
5. Set **Address** to the agreed IP, optionally add a comment such as
   `clam-node01-DO`, and save with **Apply / OK**.
6. On the ESP32, press **RESET / EN** once, without holding BOOT. For the Jetson,
   disconnect and reconnect its Ethernet connection to request a lease again.
7. Refresh **Leases**. Confirm the correct MAC and that **Address** and
   **Active Address** both show the intended IP.

Keep MAC addresses and device-specific observations in the local commissioning
record. Firmware stays on DHCP; changing this reservation requires no reflashing.

## Why reset?

**Address** is the router's configured reservation. **Active Address** is the
address currently leased to the device. Editing the reservation does not
immediately replace an existing lease, so the device may keep its old IP.

Restarting the ESP32 reconnects Wi-Fi and requests an address through DHCP,
allowing the new reservation to take effect. Reset is a convenient way to trigger
this; renewing the lease can also work. This means restarting the board, **not
factory-resetting the router**.

## Confirm the result

- Node 01: the supplied screenshot shows both fields as `192.168.88.101` for
  the matching MAC. The new lease is active. Its earlier `.253` address is historical.
- Jetson: the owner subsequently confirmed `hostname -I` includes
  `192.168.88.250`. The earlier blank Active Address is historical.
- A matching lease confirms network addressing only. Sensor readings, MQTT,
  and the dashboard require their own checks.

## SSH from the Mac: pitfalls from commissioning

SSH login was confirmed by the owner on 2026-11-04.

```bash
ssh lihong@192.168.88.250
```

The Jetson prompt is `lihong@lihongyang2026-clam`: **lihong is the username**;
**lihongyang2026-clam is the hostname**. Using the hostname as the SSH username
caused `Permission denied (publickey,password)`. Use `whoami` on the Jetson if
unsure, and enter that account's Jetson login password, not the Mac or Wi-Fi password.
Password typing is invisible. On first connection, verify the host fingerprint
against the Jetson before accepting it.

### Timeout before the password prompt

During setup, the Mac Ethernet interface `en8` had `192.168.1.100` with mask
`255.255.0.0`, and both ping and TCP port 22 timed out. Jetson already had the
correct `.250` address and SSH listening on `0.0.0.0:22`.

On the Mac, open **System Settings → Network → USB Ethernet adapter → Details
→ TCP/IP**, keep **Using DHCP**, and click **Renew DHCP Lease**, then **OK**.
This obtained `192.168.88.100`, mask `255.255.255.0`, from DHCP server/router
`192.168.88.1`. SSH then reached authentication. The Mac's `.100` is an observed
dynamic lease, not a reserved project address.

Useful Mac checks (the adapter name may differ on another computer):

```bash
route -n get 192.168.88.250
ipconfig getifaddr en8
ipconfig getpacket en8
ping -c 4 192.168.88.250
nc -vz -G 5 192.168.88.250 22
```

Do not infer subnet membership from IP addresses alone: check masks and routes.
An ARP entry alone does not prove bidirectional IP connectivity. The original
DHCP source was not captured, so its cause remains unknown.

Jetson checks if connection still times out:

```bash
hostname -I
sudo systemctl status ssh --no-pager
sudo ss -ltnp 'sport = :22'
```

`ufw: command not found` means UFW is not installed; it does not prove that all
firewall rules are absent. No UFW installation was needed to resolve this incident.

After login, commands in that terminal execute on the **Jetson**, even though
its window is on the Mac. Run `hostname` to check; `exit` returns to the Mac.
Continue with [MQTT setup](../gateway/README.md).
