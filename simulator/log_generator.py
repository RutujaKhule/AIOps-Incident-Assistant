"""Append a finite number of safe demo application log lines."""

import argparse
from datetime import datetime, timedelta, timezone

from agent.log_collector import get_log_file_path


def main():
    parser = argparse.ArgumentParser(description="Append a small set of demo application logs.")
    parser.add_argument("--info", type=int, default=1, help="number of INFO lines (default: 1)")
    parser.add_argument("--warnings", type=int, default=0, help="number of WARNING lines")
    parser.add_argument("--errors", type=int, default=0, help="number of repeated ERROR lines")
    parser.add_argument("--critical", type=int, default=0, help="number of repeated CRITICAL lines")
    arguments = parser.parse_args()

    counts = (arguments.info, arguments.warnings, arguments.errors, arguments.critical)
    if any(count < 0 for count in counts):
        parser.error("log counts must be zero or greater")
    if sum(counts) > 100:
        parser.error("at most 100 lines may be generated per run")

    try:
        log_path = get_log_file_path()
    except ValueError as error:
        parser.error(str(error))

    messages = []
    messages.extend(("INFO", "application", "Demo application running") for _ in range(arguments.info))
    messages.extend(("WARNING", "application", "Slow response detected") for _ in range(arguments.warnings))
    messages.extend(("ERROR", "application", "Database connection failed") for _ in range(arguments.errors))
    messages.extend(("CRITICAL", "application", "Database connection failed") for _ in range(arguments.critical))

    start_time = datetime.now(timezone.utc).replace(tzinfo=None, microsecond=0)
    with log_path.open("a", encoding="utf-8") as log_file:
        for index, (level, source, message) in enumerate(messages):
            timestamp = start_time + timedelta(seconds=index)
            log_file.write(f"{timestamp:%Y-%m-%d %H:%M:%S} {level} {source} {message}\n")

    print(f"Appended {len(messages)} demo log entr{'y' if len(messages) == 1 else 'ies'} to {log_path}.")


if __name__ == "__main__":
    main()