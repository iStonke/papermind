"""OOM-Vorrang für entbehrliche Kindprozesse.

Worker und Kinder teilen sich ein Container-Speicherlimit. Wird es knapp, soll
der Kernel zuerst das Kind (OCR, Scan-Bereinigung, PDF-Task) beenden: Dessen
Abbruch fangen die Eltern sauber als Jobfehler ab. Trifft es dagegen den Worker
selbst, reißen alle Spuren gleichzeitig ab. Den eigenen Wert zu erhöhen ist ohne
Privilegien erlaubt.
"""
from pathlib import Path

DISPOSABLE_OOM_SCORE_ADJ = 1000
_OOM_SCORE_ADJ_PATH = Path("/proc/self/oom_score_adj")


def prefer_oom_kill(score: int = DISPOSABLE_OOM_SCORE_ADJ, *, path: Path = _OOM_SCORE_ADJ_PATH) -> bool:
    """Markiert den aktuellen Prozess (und alle künftigen Kinder) als erstes OOM-Opfer."""
    try:
        path.write_text(f"{int(score)}\n", encoding="ascii")
        return True
    except OSError:  # kein Linux / /proc nicht beschreibbar - nur eine Optimierung
        return False
