import queue
import threading


class InterruptHandler:
    def __init__(self):
        self._queue: queue.Queue[str] = queue.Queue()
        self._active = False
        self._thread: threading.Thread | None = None

    def start(self):
        """Start listening for user input in background thread"""
        self._active = True
        self._thread = threading.Thread(target=self._listen, daemon=True)
        self._thread.start()

    def stop(self):
        self._active = False

    def _listen(self):
        while self._active:
            try:
                msg = input()
                if msg.strip():
                    self._queue.put(msg.strip())
            except (EOFError, OSError):
                break

    def get_message(self) -> str | None:
        """Returns user message if any, otherwise None"""
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def has_message(self) -> bool:
        return not self._queue.empty()
