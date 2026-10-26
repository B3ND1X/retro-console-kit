# -*- coding: utf-8 -*-
"""What the add-on's three HTTP servers share: the manifest server, the web
interface and the DIAL endpoint. No xbmc import.
"""

import threading
from http.server import ThreadingHTTPServer


class BoundedHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, *args, **kwargs):
        self.slots = threading.BoundedSemaphore(8)
        super().__init__(*args, **kwargs)
    def process_request(self, request, client_address):
        if not self.slots.acquire(False):
            request.close()
            return
        def run():
            try:
                self.process_request_thread(request, client_address)
            finally:
                self.slots.release()
        threading.Thread(target=run, daemon=True).start()


class ServerThread:
    """A ThreadingHTTPServer serving from a daemon thread.

    attributes are set on the server object, where a handler finds them as
    self.server.<name>: the manifest directory, the web backend, the PIN.
    """

    def __init__(self, handler, host, port, thread_name, **attributes):
        self.handler = handler
        self.host = host
        self.port = port
        self.thread_name = thread_name
        self.attributes = attributes
        self._httpd = None
        self._thread = None

    def start(self):
        """Bind and serve; return the port, the system's pick for 0. Raises OSError if binding fails."""
        httpd = BoundedHTTPServer((self.host, self.port), self.handler)
        httpd.daemon_threads = True
        for name, value in self.attributes.items():
            setattr(httpd, name, value)
        self._httpd = httpd
        self.port = httpd.server_address[1]
        self._thread = threading.Thread(target=httpd.serve_forever, name=self.thread_name, daemon=True)
        self._thread.start()
        return self.port

    def set(self, **attributes):
        """Change what the handlers see, while serving too."""
        self.attributes.update(attributes)
        if self._httpd is not None:
            for name, value in attributes.items():
                setattr(self._httpd, name, value)

    def stop(self, timeout=5):
        """Stop serving and release the port; False when it was not running."""
        if self._httpd is None:
            return False
        self._httpd.shutdown()
        self._httpd.server_close()
        self._thread.join(timeout=timeout)
        self._httpd = self._thread = None
        return True


def content_length(headers):
    """The request's Content-Length: 0 when absent, None when it is not a plain number.

    int() of the raw header would raise on garbage, and a negative length makes
    rfile.read() wait for the client to close a kept-alive connection.
    """
    value = (headers.get("Content-Length") or "0").strip()
    return int(value) if value.isascii() and value.isdigit() else None
