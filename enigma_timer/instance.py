"""One workspace per data file; later launches activate it without an intro."""
import hashlib
import os
from PyQt5.QtCore import QObject,pyqtSignal,QLockFile
from PyQt5.QtNetwork import QLocalServer,QLocalSocket


class AppInstance(QObject):
    activated=pyqtSignal()

    def __init__(self,data_path,parent=None):
        super().__init__(parent)
        path=os.path.normcase(os.path.abspath(data_path))
        self.name="EnigmaCube-"+hashlib.sha256(path.encode("utf-8")).hexdigest()[:24]
        self._lock=QLockFile(path+".lock")
        self._lock.setStaleLockTime(0)
        self._server=QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.UserAccessOption)
        self._server.newConnection.connect(self._accept)
        self._clients=set()
        self.primary=False

    def _notify(self,timeout=150):
        socket=QLocalSocket()
        socket.connectToServer(self.name)
        if not socket.waitForConnected(timeout):
            return False
        # A connection itself is the activation request. Windows can discard
        # a tiny buffered payload if this short-lived secondary exits before
        # the GUI process accepts its pipe; no payload is needed for this IPC.
        socket.disconnectFromServer()
        return True

    def acquire(self):
        if self.primary:
            return True
        if self._notify():
            return False
        if not self._lock.tryLock(0):
            # Another cold start may hold its lock before its pipe is ready.
            if self._notify(1000):
                return False
            raise RuntimeError("The application is already starting or its data file is locked")
        if not self._server.listen(self.name):
            # Only the lock owner may clean up a stale endpoint.
            QLocalServer.removeServer(self.name)
            if not self._server.listen(self.name):
                self._lock.unlock()
                raise RuntimeError("Cannot create the application activation channel")
        self.primary=True
        return True

    def _accept(self):
        while self._server.hasPendingConnections():
            client=self._server.nextPendingConnection()
            self._clients.add(client)
            client.disconnected.connect(lambda c=client:self._release(c))
            self.activated.emit()

    def _release(self,client):
        self._clients.discard(client)
        client.deleteLater()

    def close(self):
        self._server.close()
        for client in list(self._clients):
            client.abort()
        self._clients.clear()
        if self.primary:
            self._lock.unlock()
            self.primary=False
