# Giiker discovery

The picker displays smart cubes only. Other BLE peripherals are filtered in
the worker and again in the dialog. A cube is recognised by its advertised
name, the Giiker AADB service (including service data), or an address already
recognised in this run or saved by the application. A saved address is never
inserted as a discovery result without a live advertisement.

Discovery uses active scanning without a Bluetooth service filter. Some cubes
send their name in a later scan response and omit the service in earlier
packets. Filtering at the OS level can therefore miss them. The name from
the current scan response takes precedence over the Windows device name.
Recognition survives later packets with no name and manual scanner restarts.

Scanner start and stop are serialised, including backend teardown. Queued
restarts cannot reopen discovery after the picker has closed. Connection
attempts stop discovery before opening GATT. Reconnection uses
`find_device_by_address`, which returns when the target is found, rather than
waiting for a fixed-duration scan of every peripheral.

Reference: [Bleak scanner API](https://bleak.readthedocs.io/en/latest/api/scanner.html)
and [Windows scanner implementation](https://bleak.readthedocs.io/en/latest/_modules/bleak/backends/winrt/scanner.html).

Regression tests cover unrelated-device filtering, late names, nameless service
packets, saved addresses, scanner stop/start races, closed-picker commands,
early-return reconnection, and preservation of connection/error messages.
They do not establish radio reliability on physical hardware.

Connection initialization requests only the Giiker service. Windows first uses
its service cache; a failed connect/notification subscription releases that
client and retries with an uncached service lookup. Client construction has an
explicit eight-second timeout (newer Bleak versions otherwise default to thirty
seconds). Subscription is bounded to five seconds. The connection-ready signal
follows a successful subscription; the optional initial read is bounded to 1.5
seconds and no longer delays readiness. Failed-client teardown is also bounded.
The picker displays discovery, connection, subscription and retry stages.
