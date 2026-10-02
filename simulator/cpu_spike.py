"""Manual CPU load tool for testing monitoring and incident detection."""

import argparse
import multiprocessing
import os
import signal
import time


def _use_cpu(stop_event):
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    value = 1.0001
    while not stop_event.is_set():
        value = (value * 1.0001) % 1000


def main():
    parser = argparse.ArgumentParser(description="Manual CPU-only monitoring test tool.")
    parser.add_argument(
        "--workers",
        type=int,
        default=os.cpu_count() or 1,
        help="CPU worker processes (defaults to the machine's logical processor count).",
    )
    arguments = parser.parse_args()
    if arguments.workers < 1:
        parser.error("--workers must be at least 1")

    stop_event = multiprocessing.Event()
    workers = [
        multiprocessing.Process(target=_use_cpu, args=(stop_event,))
        for _ in range(arguments.workers)
    ]

    print(
        f"TEST TOOL: starting {len(workers)} CPU workers. "
        "No memory is allocated; press Ctrl+C to stop."
    )
    for worker in workers:
        worker.start()

    try:
        while any(worker.is_alive() for worker in workers):
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\nStopping CPU test workers.")
    finally:
        stop_event.set()
        for worker in workers:
            worker.join(timeout=2)
            if worker.is_alive():
                worker.terminate()
                worker.join()
        print("CPU test workers stopped.")


if __name__ == "__main__":
    multiprocessing.freeze_support()
    main()