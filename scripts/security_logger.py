# security_logger.py
from datetime import datetime

def log_security_event(event_type, details):
    with open("security_audit.log", "a", encoding="utf-8") as file:
        file.write(
            f"{datetime.now()} | {event_type} | {details}\n"
        )