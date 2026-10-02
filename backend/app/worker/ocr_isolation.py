"""OCR in einem eigenen, hart abbrechbaren Prozess.

Ein Python-Thread lässt sich nicht beenden: Hängt die OCR (kaputtes PDF,
tesseract/ocrmypdf ohne Rückkehr), bliebe der Worker-Thread für immer
blockiert – und mit ihm die OCR-Spur. Deshalb läuft die Pipeline in einem
Kindprozess mit eigener Prozessgruppe. Bei Fristablauf oder Abbruch wird die
ganze Gruppe (inklusive tesseract/ocrmypdf/unpaper) per SIGKILL beendet.
"""
import logging
import multiprocessing
import os
import signal
import threading
import time
from typing import Any, Callable

logger = logging.getLogger("papermind.worker.ocr_isolation")

# spawn statt fork: Der Worker ist mehrfädig (Heartbeats, Executors); ein fork
# könnte im Kind auf Locks anderer Threads hängen bleiben.
_CTX = multiprocessing.get_context("spawn")
_POLL_SECONDS = 1.0
_JOIN_SECONDS = 5.0


class OCRIsolationError(RuntimeError):
    """Basisklasse für Abbrüche des isolierten OCR-Prozesses."""


class OCRDeadlineExceeded(OCRIsolationError):
    pass


class OCRAborted(OCRIsolationError):
    pass


class OCRChildFailed(OCRIsolationError):
    pass


def _child_main(conn, target: Callable[..., Any], args: tuple, kwargs: dict) -> None:
    # Eigene Prozessgruppe, damit der Elternprozess auch Enkel (tesseract …) trifft.
    os.setsid()
    try:
        try:
            message = ("ok", target(*args, **kwargs))
        except BaseException as exc:  # noqa: BLE001 - jeder Fehler geht an den Elternprozess
            message = ("error", type(exc).__name__, str(exc) or type(exc).__name__)
        try:
            conn.send(message)
        except Exception as exc:  # noqa: BLE001 - z. B. nicht serialisierbares Ergebnis
            conn.send(("error", type(exc).__name__, f"OCR-Ergebnis nicht übertragbar: {exc}"))
    finally:
        conn.close()


def _terminate(process) -> None:
    if process.is_alive():
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            # Kind hat setsid() noch nicht erreicht – dann nur den Prozess selbst.
            process.kill()
    process.join(_JOIN_SECONDS)


def run_isolated(
    target: Callable[..., Any],
    *args: Any,
    deadline_seconds: float,
    abort: threading.Event | None = None,
    **kwargs: Any,
) -> Any:
    """``target(*args, **kwargs)`` im Kindprozess ausführen und das Ergebnis liefern.

    Wirft ``OCRDeadlineExceeded`` nach ``deadline_seconds``, ``OCRAborted`` sobald
    ``abort`` gesetzt ist, und ``OCRChildFailed`` bei Fehlern oder Absturz des Kindes.
    In allen Abbruchfällen ist die Prozessgruppe danach beendet.
    """
    receiver, sender = _CTX.Pipe(duplex=False)
    process = _CTX.Process(target=_child_main, args=(sender, target, args, kwargs), name="ocr-isolated")
    process.start()
    sender.close()
    deadline = time.monotonic() + max(0.0, float(deadline_seconds))
    message = None
    try:
        while True:
            if receiver.poll(_POLL_SECONDS):
                try:
                    message = receiver.recv()
                except EOFError:
                    message = None
                break
            if abort is not None and abort.is_set():
                raise OCRAborted("OCR abgebrochen")
            if time.monotonic() >= deadline:
                raise OCRDeadlineExceeded(f"OCR nach {int(deadline_seconds)} s abgebrochen")
            if not process.is_alive() and not receiver.poll(0):
                break
    finally:
        _terminate(process)
        receiver.close()

    if message is None:
        raise OCRChildFailed(f"OCR-Prozess unerwartet beendet (Exit-Code {process.exitcode})")
    if message[0] == "error":
        raise OCRChildFailed(message[2])
    return message[1]
