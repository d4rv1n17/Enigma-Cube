"""Discovery must retain cubes without listing unrelated BLE devices."""
import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from enigma_timer.ble import GiikerWorker, SERVICE_UUID, is_cube_advertisement


def advertisement(name=None, uuids=()):
    return SimpleNamespace(local_name=name, service_uuids=uuids, service_data={})


def device(name=None, address="AA:BB:CC:DD:EE:FF"):
    return SimpleNamespace(name=name, address=address)


class DiscoveryTests(unittest.TestCase):
    def test_other_devices_never_leave_worker(self):
        worker = GiikerWorker()
        results = []
        worker.device_found_detailed.connect(lambda *args: results.append(args))
        for name in (None, "Mi Band 8", "Microsoft Mouse", "Gimbal", "QY Headset"):
            worker._on_detect(device(name), advertisement(name))
        self.assertEqual(results, [])
        self.assertEqual(worker._candidates, {})

    def test_scan_response_overrides_stale_windows_name(self):
        worker = GiikerWorker()
        results = []
        worker.device_found_detailed.connect(lambda *args: results.append(args))
        worker._on_detect(device("Unknown"), advertisement("Gi157084"))
        self.assertEqual(results, [("Gi157084", "AA:BB:CC:DD:EE:FF", True)])

    def test_nameless_cube_service_and_later_name(self):
        worker = GiikerWorker()
        results = []
        worker.device_found_detailed.connect(lambda *args: results.append(args))
        worker._on_detect(device(), advertisement(uuids=[SERVICE_UUID]))
        worker._on_detect(device(), advertisement("Gi157084"))
        worker._on_detect(device(), advertisement())
        self.assertEqual([item[0] for item in results], ["Giiker", "Gi157084"])
        # A new scan clears current results, not the known-cube identity.
        worker._reported_names.clear()
        latest = device()
        worker._on_detect(latest, advertisement())
        self.assertEqual(results[-1], ("Gi157084", latest.address, True))
        self.assertIs(worker._candidates[latest.address], latest)

    def test_saved_cube_requires_live_advertisement_but_not_name(self):
        worker = GiikerWorker(known_addresses=["aa:bb:cc:dd:ee:ff"])
        results = []
        worker.device_found_detailed.connect(lambda *args: results.append(args))
        self.assertEqual(results, [])
        worker._on_detect(device(), advertisement())
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0][2])

    def test_service_data_and_case_insensitive_names(self):
        self.assertTrue(is_cube_advertisement("gi157084"))
        self.assertTrue(is_cube_advertisement("Giiker"))
        self.assertTrue(is_cube_advertisement("Mi Smart Magic Cube"))
        self.assertTrue(is_cube_advertisement(None, SimpleNamespace(
            service_uuids=[], service_data={SERVICE_UUID: b""})))
        self.assertFalse(is_cube_advertisement("Mi Band"))


class ScannerLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_connected_is_reported_before_optional_initial_read_completes(self):
        worker=GiikerWorker()
        worker._loop=asyncio.get_running_loop()
        worker._want_connection=True
        target=device("Gi157084")
        worker._candidates[target.address]=target
        read_gate=asyncio.Event()
        connected=asyncio.Event()
        worker.connected.connect(lambda *_: connected.set())
        async def read(*_):
            await read_gate.wait()
            return b""
        client=SimpleNamespace(is_connected=True,connect=AsyncMock(),
                               start_notify=AsyncMock(),read_gatt_char=read,
                               disconnect=AsyncMock())
        with patch("bleak.BleakClient",return_value=client) as factory:
            task=asyncio.create_task(worker._connect_async(target.address))
            await asyncio.wait_for(connected.wait(),timeout=1)
            self.assertTrue(worker._connected)
            self.assertFalse(task.done())
            read_gate.set()
            await task
        self.assertEqual(factory.call_args.kwargs["services"],[SERVICE_UUID])
        self.assertEqual(factory.call_args.kwargs["timeout"],8.0)

    async def test_stale_cached_services_retry_uncached_and_release_old_client(self):
        worker=GiikerWorker()
        worker._loop=asyncio.get_running_loop()
        worker._want_connection=True
        target=device("Gi157084")
        worker._candidates[target.address]=target
        def client():
            return SimpleNamespace(is_connected=True,connect=AsyncMock(),start_notify=AsyncMock(),
                                   read_gatt_char=AsyncMock(return_value=b""),disconnect=AsyncMock())
        old,new=client(),client()
        old.start_notify.side_effect=RuntimeError("stale service cache")
        with patch("bleak.BleakClient",side_effect=[old,new]) as factory:
            with patch("bleak.BleakScanner.find_device_by_address",new=AsyncMock(return_value=target)):
                await worker._connect_async(target.address)
        self.assertEqual([c.kwargs["winrt"]["use_cached_services"] for c in factory.call_args_list],[True,False])
        old.disconnect.assert_awaited_once()
        self.assertIs(worker._client,new)
        self.assertTrue(worker._connected)

    async def test_stop_and_start_cannot_overlap_backend_teardown(self):
        active = 0
        high_water = 0
        stop_entered = asyncio.Event()
        allow_stop = asyncio.Event()

        class Scanner:
            def __init__(self, **kwargs):
                self.kwargs = kwargs

            async def start(self):
                nonlocal active, high_water
                active += 1
                high_water = max(high_water, active)

            async def stop(self):
                nonlocal active
                stop_entered.set()
                await allow_stop.wait()
                active -= 1

        worker = GiikerWorker()
        worker._scan_requested = True
        with patch("bleak.BleakScanner", Scanner):
            await worker._scan_start_async()
            self.assertEqual(worker._scanner.kwargs["scanning_mode"], "active")
            stop = asyncio.create_task(worker._scan_stop_async())
            await stop_entered.wait()
            start = asyncio.create_task(worker._scan_start_async())
            await asyncio.sleep(0)
            self.assertFalse(start.done())
            allow_stop.set()
            await asyncio.gather(stop, start)
            self.assertEqual(high_water, 1)
            await worker._scan_stop_async()
            self.assertEqual(active, 0)

    async def test_queued_restart_cannot_start_scan_after_picker_closed(self):
        worker = GiikerWorker()
        worker._scan_requested = False
        with patch("bleak.BleakScanner") as scanner:
            await worker._scan_restart_async()
            await worker._scan_start_async()
        scanner.assert_not_called()

    async def test_reconnect_uses_early_return_address_lookup(self):
        worker = GiikerWorker()
        worker._loop = asyncio.get_running_loop()
        worker._want_connection = True
        with patch("bleak.BleakScanner.find_device_by_address", new=AsyncMock(return_value=None)) as find:
            with patch("bleak.BleakScanner.discover", new=AsyncMock()) as discover:
                await worker._connect_async("AA:BB:CC:DD:EE:FF", automatic=True)
        find.assert_awaited_once_with("AA:BB:CC:DD:EE:FF", timeout=5.0,
                                      scanning_mode="active")
        discover.assert_not_called()
