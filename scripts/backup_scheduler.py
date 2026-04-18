#!/usr/bin/env python3
from __future__ import annotations

import os
import subprocess
import sys
import time
from pathlib import Path


def main() -> int:
    interval = max(300, int(os.getenv('NV0_BACKUP_INTERVAL_SECONDS', '21600') or '21600'))
    script = Path(__file__).with_name('backup_state.py')
    while True:
        try:
            subprocess.run([sys.executable, str(script)], check=True)
            print('backup completed', flush=True)
        except subprocess.CalledProcessError as exc:
            print(f'backup failed: {exc}', flush=True)
        time.sleep(interval)


if __name__ == '__main__':
    raise SystemExit(main())
