import asyncio
import unittest
from unittest.mock import AsyncMock, patch
from enigma_timer.ble import GiikerWorker


class ReconnectionTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.worker = GiikerWorker()
        self.worker._loop = asyncio.get_running_loop()
        self.worker._address = "test-address"
        self.worker._want_connection = True

    async def test_old_client_callback_cannot_disconnect_new_client(self):
        old, current = object(), object()
        self.worker._client = current
        self.worker._connected = True
        self.worker._handle_link_lost(old)
        self.assertIs(self.worker._client, current)
        self.assertTrue(self.worker._connected)
        self.assertIsNone(self.worker._reconnect_task)

    async def test_deliberate_disconnect_does_not_start_reconnect(self):
        self.worker._want_connection = False
        client = object()
        self.worker._client = client
        self.worker._handle_link_lost(client)
        self.assertIsNone(self.worker._client)
        self.assertIsNone(self.worker._reconnect_task)

    async def test_real_loss_starts_only_one_recovery(self):
        client = object()
        self.worker._client = client
        self.worker._restore_connection = AsyncMock()
        self.worker._handle_link_lost(client)
        task = self.worker._reconnect_task
        self.worker._handle_link_lost(client)
        await task
        self.worker._restore_connection.assert_awaited_once_with("test-address")

    async def test_failed_client_is_released_before_its_callback_runs(self):
        worker = self.worker
        class Client:
            async def disconnect(self):
                worker._handle_link_lost(self)
        client = Client()
        worker._client = client
        await worker._discard(client)
        self.assertIsNone(worker._client)
        self.assertIsNone(worker._reconnect_task)

    async def test_recovery_stops_after_success(self):
        attempts = []
        self.worker.reconnecting.connect(attempts.append)
        calls = []
        async def connect(address, automatic=False):
            calls.append((address, automatic))
            self.worker._connected = len(calls) == 2
        self.worker._connect_async = connect
        with patch("enigma_timer.ble.asyncio.sleep", new=AsyncMock()):
            await self.worker._restore_connection("test-address")
        self.assertEqual(attempts, [1, 2])
        self.assertEqual(calls, [("test-address", True)]*2)

    async def test_recovery_is_bounded(self):
        attempts = []
        self.worker.reconnecting.connect(attempts.append)
        self.worker._connect_async = AsyncMock()
        with patch("enigma_timer.ble.asyncio.sleep", new=AsyncMock()):
            await self.worker._restore_connection("test-address")
        self.assertEqual(self.worker._connect_async.await_count, 3)
        self.assertEqual(attempts, [1, 2, 3, 0])

    async def test_manual_disconnect_cancels_pending_recovery(self):
        task = asyncio.create_task(asyncio.sleep(100))
        self.worker._reconnect_task = task
        self.worker.disconnect()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        self.assertFalse(self.worker._want_connection)
        self.assertTrue(task.cancelled())
