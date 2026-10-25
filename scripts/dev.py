"""Run both local development services. Ctrl+C stops both children."""
import argparse
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--demo', action='store_true', help='Explicitly build synthetic-demo if missing')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    node = shutil.which('node')
    vite = root / 'frontend/node_modules/vite/bin/vite.js'
    if not node or not vite.is_file():
        raise SystemExit('Install Node and frontend dependencies first; see README.')
    if args.demo and not (root / 'backend/data/synthetic-demo').exists():
        subprocess.run([sys.executable, str(root / 'backend/scripts/build_dataset.py'), '--synthetic',
                        '--output', str(root / 'backend/data/synthetic-demo')], cwd=root, check=True)
    children = []
    flags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
    try:
        children.append(subprocess.Popen([sys.executable, '-m', 'uvicorn', 'app.main:app', '--app-dir', str(root / 'backend'),
                                          '--host', '127.0.0.1', '--port', '8000'], cwd=root, creationflags=flags))
        children.append(subprocess.Popen([node, str(vite), '--host', '127.0.0.1'], cwd=root / 'frontend', creationflags=flags))
        print('Semantic Atlas: http://127.0.0.1:5173 | API: http://127.0.0.1:8000/docs', flush=True)
        while all(child.poll() is None for child in children):
            time.sleep(.5)
        failed = next((child.returncode for child in children if child.poll() is not None), 1)
        return failed or 0
    except KeyboardInterrupt:
        return 0
    finally:
        for child in children:
            if child.poll() is None:
                try:
                    child.send_signal(signal.CTRL_BREAK_EVENT if os.name == 'nt' else signal.SIGTERM)
                    child.wait(timeout=5)
                except (OSError, subprocess.TimeoutExpired):
                    child.kill()
                    child.wait()


if __name__ == '__main__':
    raise SystemExit(main())
