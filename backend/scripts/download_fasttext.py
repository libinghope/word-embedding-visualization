"""Download official Chinese/English aligned fastText vectors, with resumable ranges.

This does not change the active application dataset or import these vectors.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import shutil
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
from pathlib import Path

BASE = 'https://dl.fbaipublicfiles.com/fasttext/vectors-aligned/'
CHUNK_SIZE = 64 * 1024 * 1024


def remote_info(language):
    name = f'wiki.{language}.align.vec'
    url = BASE + name
    with urllib.request.urlopen(urllib.request.Request(url, method='HEAD'), timeout=60) as response:
        return {'language': language, 'filename': name, 'url': url,
                'bytes': int(response.headers['Content-Length']), 'etag': response.headers.get('ETag'),
                'last_modified': response.headers.get('Last-Modified')}


def transfer(info, part: Path, start: int, end: int):
    expected = end - start + 1
    for attempt in range(6):
        have = part.stat().st_size if part.exists() else 0
        if have == expected:
            return
        if have > expected:
            raise ValueError(f'Oversized partial file: {part.name}')
        try:
            headers = {'Range': f'bytes={start + have}-{end}', 'Accept-Encoding': 'identity'}
            if info['etag']:
                headers['If-Range'] = info['etag']
            with urllib.request.urlopen(urllib.request.Request(info['url'], headers=headers), timeout=90) as response:
                if response.status != 206 or response.headers.get('Content-Range') != f"bytes {start + have}-{end}/{info['bytes']}":
                    raise ValueError('Server did not honor the requested byte range; partial data preserved')
                with part.open('ab') as output:
                    while data := response.read(1024 * 1024):
                        output.write(data)
            if part.stat().st_size != expected:
                raise OSError('Incomplete range; retrying remaining bytes')
            return
        except (OSError, TimeoutError) as exc:
            if attempt == 5:
                raise RuntimeError(f'{part.name}: download interrupted; rerun to resume') from exc
            time.sleep(min(2 ** attempt, 16))


def finalize(info, parts: list[Path], destination: Path):
    target = destination / info['filename']
    temporary = destination / (info['filename'] + '.assembling')
    digest = hashlib.sha256()
    lines, last_byte = 0, b''
    with temporary.open('wb') as output:
        for part in parts:
            with part.open('rb') as source:
                while data := source.read(8 * 1024 * 1024):
                    digest.update(data)
                    lines += data.count(b'\n')
                    last_byte = data[-1:]
                    output.write(data)
    if temporary.stat().st_size != info['bytes']:
        raise ValueError('Final file size mismatch')
    with temporary.open('rb') as handle:
        header = handle.readline().decode('ascii').strip()
        count, dimensions = map(int, header.split())
        first = handle.readline().split()
    actual_rows = lines - 1 + (1 if last_byte != b'\n' else 0)
    if dimensions != 300 or actual_rows != count or len(first) != dimensions + 1:
        raise ValueError(f'Invalid vector header/row count: {header}; actual rows={actual_rows}')
    # Never overwrite an existing completed source file.
    temporary.rename(target)
    manifest = {**info, 'word_count': count, 'dimensions': dimensions, 'sha256': digest.hexdigest(),
                'downloaded_at': datetime.now(timezone.utc).isoformat(),
                'source_page': 'https://fasttext.cc/docs/en/aligned-vectors',
                'license': 'CC-BY-SA-3.0', 'license_url': 'https://creativecommons.org/licenses/by-sa/3.0/',
                'verification': 'HTTP size, Content-Range/ETag, vector header, data row count, local SHA-256'}
    (destination / (info['filename'] + '.json')).write_text(json.dumps(manifest, indent=2), 'utf-8')
    for part in parts:
        part.unlink()  # Only individual chunks created by this downloader.
    print(json.dumps({'completed': info['filename'], **manifest}, ensure_ascii=False), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=Path(__file__).resolve().parents[1] / 'models/fasttext-aligned')
    parser.add_argument('--workers', type=int, default=8)
    args = parser.parse_args()
    if not 1 <= args.workers <= 16:
        parser.error('workers must be between 1 and 16')
    destination = args.output.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    partial = destination / '.partial'
    partial.mkdir(exist_ok=True)
    infos = [remote_info(language) for language in ('zh', 'en')]
    jobs, groups, missing = [], {}, []
    for info in infos:
        target = destination / info['filename']
        if target.exists():
            manifest_path = destination / (info['filename'] + '.json')
            if not manifest_path.exists():
                raise ValueError(f'Existing file has no verification manifest: {target}')
            manifest = json.loads(manifest_path.read_text('utf-8'))
            with target.open('rb') as handle:
                digest = hashlib.file_digest(handle, 'sha256').hexdigest()
            if target.stat().st_size != info['bytes'] or digest != manifest['sha256'] or manifest['etag'] != info['etag']:
                raise ValueError(f'Existing file differs from source or recorded hash: {target}')
            print(f"Already verified: {target.name}", flush=True)
            continue
        descriptor = partial / (info['filename'] + '.source.json')
        if descriptor.exists() and json.loads(descriptor.read_text('utf-8')) != info:
            raise ValueError('Source metadata changed; do not reuse previous partial chunks')
        descriptor.write_text(json.dumps(info, indent=2), 'utf-8')
        parts = []
        for index in range(math.ceil(info['bytes'] / CHUNK_SIZE)):
            start, end = index * CHUNK_SIZE, min((index + 1) * CHUNK_SIZE, info['bytes']) - 1
            part = partial / f"{info['filename']}.{index:04d}.part"
            parts.append(part)
            jobs.append((info, part, start, end))
        groups[info['filename']] = parts
        missing.append(info)
    if shutil.disk_usage(destination).free < sum(i['bytes'] for i in missing) * 2:
        raise ValueError('Insufficient free disk space for resumable chunks and assembly')
    started, last_report = time.monotonic(), 0.0
    total = sum(i['bytes'] for i in missing)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(transfer, *job) for job in jobs}
        while futures:
            done, futures = wait(futures, timeout=5, return_when=FIRST_COMPLETED)
            for future in done:
                future.result()
            now = time.monotonic()
            if now - last_report >= 15 or not futures:
                sizes = {name: sum(p.stat().st_size for p in parts if p.exists()) for name, parts in groups.items()}
                downloaded = sum(sizes.values())
                print(json.dumps({'downloaded_bytes': downloaded, 'total_bytes': total,
                                  'percent': round(100 * downloaded / total, 1) if total else 100,
                                  'elapsed_seconds': round(now - started), 'files': sizes}), flush=True)
                last_report = now
    for info in missing:
        print(f"Verifying and assembling {info['filename']}...", flush=True)
        finalize(info, groups[info['filename']], destination)
    print('Both aligned vector files are ready. The application dataset has not been changed.', flush=True)


if __name__ == '__main__':
    main()
