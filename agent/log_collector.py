"""Tail a project-local application log file and store parsed entries in MongoDB."""

import argparse
import os
import re
import socket
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from backend.app.services.log_service import LogStorageError, insert_log


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAFE_LOG_DIRECTORY = (PROJECT_ROOT / "demo_service").resolve()
DEFAULT_LOG_PATH = "demo_service/sample_app.log"
LOG_PATTERN = re.compile(r"^(\d{4}-\d{2}-\d{2}) (\d{2}:\d{2}:\d{2}) (INFO|WARNING|ERROR|CRITICAL) (.+)$")


def get_log_file_path(path=None):
    """Resolve the configured log path, allowing files only under demo_service."""
    configured_path = path or os.getenv("LOG_FILE_PATH", DEFAULT_LOG_PATH)
    candidate = Path(configured_path)
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT / candidate
    resolved_path = candidate.resolve()

    try:
        resolved_path.relative_to(SAFE_LOG_DIRECTORY)
    except ValueError as error:
        raise ValueError("LOG_FILE_PATH must point to a file under the project demo_service directory.") from error
    return resolved_path


def parse_log_line(line):
    """Parse `YYYY-MM-DD HH:MM:SS LEVEL source message`; return None if malformed."""
    match = LOG_PATTERN.match(line.strip())
    if not match:
        return None

    date_part, time_part, level, details = match.groups()
    source, separator, message = details.partition(" ")
    if not separator or not source or not message.strip():
        return None

    try:
        timestamp = datetime.strptime(
            f"{date_part} {time_part}",
            "%Y-%m-%d %H:%M:%S",
        ).replace(tzinfo=timezone.utc)
    except ValueError:
        return None

    return {
        "timestamp": timestamp.isoformat(),
        "level": level,
        "source": source,
        "message": message.strip(),
    }


def collect_new_lines(path, offset=0, log_writer=insert_log):
    """Read complete new lines from a safe file and store valid entries."""
    resolved_path = get_log_file_path(path)
    if not resolved_path.is_file():
        raise FileNotFoundError(f"Configured log file not found: {resolved_path}")

    file_size = resolved_path.stat().st_size
    if offset > file_size:
        offset = 0
    inserted_count = 0

    with resolved_path.open("r", encoding="utf-8", errors="replace") as log_file:
        log_file.seek(offset)
        while True:
            line_offset = log_file.tell()
            line = log_file.readline()
            if not line:
                break
            next_offset = log_file.tell()
            parsed_log = parse_log_line(line)
            if parsed_log is None:
                print(f"Skipping malformed log line at byte {line_offset}.", file=sys.stderr)
                offset = next_offset
                continue

            parsed_log.update(
                log_id=f"{resolved_path}:{line_offset}",
                hostname=socket.gethostname(),
            )
            try:
                log_writer(parsed_log)
                inserted_count += 1
            except LogStorageError as error:
                print(f"Log storage error: {error}", file=sys.stderr, flush=True)
                offset = line_offset
                break
            offset = next_offset

    return offset, inserted_count


def main():
    parser = argparse.ArgumentParser(description="Tail a safe project-local application log file.")
    parser.add_argument(
        "--from-start",
        action="store_true",
        help="read existing entries before following new lines",
    )
    parser.add_argument("--once", action="store_true", help="read currently available lines and exit")
    arguments = parser.parse_args()

    try:
        log_path = get_log_file_path()
    except ValueError as error:
        print(f"Log collector configuration error: {error}", file=sys.stderr)
        return 2
    if not log_path.is_file():
        print(f"Log file does not exist: {log_path}", file=sys.stderr)
        return 1

    offset = 0 if arguments.from_start else log_path.stat().st_size
    print(f"Tailing project log file: {log_path}. Press Ctrl+C to stop.", flush=True)
    try:
        while True:
            offset, inserted_count = collect_new_lines(log_path, offset)
            if inserted_count:
                print(f"Stored {inserted_count} log entr{'y' if inserted_count == 1 else 'ies'}.", flush=True)
            if arguments.once:
                return 0
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nLog collector stopped.", flush=True)
        return 0
    except FileNotFoundError as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())