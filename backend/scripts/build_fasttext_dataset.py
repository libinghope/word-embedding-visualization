"""Build a reproducible bilingual subset from the downloaded aligned text vectors."""
import hashlib
import json
from pathlib import Path
import numpy as np
from build_dataset import write_dataset, sha256

ROOT = Path(__file__).resolve().parents[1]


def extract(path, words):
    wanted = {word.encode('utf-8'): word for word in words}
    found = {}
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        header = stream.readline()
        digest.update(header)
        count, dimensions = map(int, header.split())
        if dimensions != 300 or count < 1:
            raise ValueError('Expected 300-dimensional aligned vectors')
        rows = 0
        for line in stream:
            digest.update(line)
            rows += 1
            token, _, values = line.partition(b' ')
            if token in wanted:
                vector = np.asarray(values.split(), dtype='<f4')
                if vector.shape != (300,) or not np.isfinite(vector).all():
                    raise ValueError(f'Invalid vector: {token!r}')
                found[wanted[token]] = vector
        if rows != count:
            raise ValueError('Source row count mismatch')
    missing = [w for w in words if w not in found]
    if missing:
        raise ValueError('OOV: ' + ', '.join(missing))
    manifest = json.loads(path.with_suffix(path.suffix + '.json').read_text('utf-8'))
    if digest.hexdigest() != manifest['sha256']:
        raise ValueError('Source checksum mismatch')
    return [found[w] for w in words], manifest


def main():
    seed = ROOT / 'data/fasttext_seed.json'
    groups = json.loads(seed.read_text('utf-8'))
    words, vectors, sources = [], [], []
    for language, tokens in groups.items():
        print(f'Extracting {language}: {len(tokens)} words', flush=True)
        rows, manifest = extract(ROOT / f'models/fasttext-aligned/wiki.{language}.align.vec', tokens)
        words.extend(tokens)
        vectors.extend(rows)
        sources.append(manifest)
    source_hash = hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest()
    meta = write_dataset(ROOT / 'data/fasttext-en-zh-v1', words, np.asarray(vectors), synthetic=False,
        model='fastText aligned English + Chinese (RCSLS)',
        source_url='https://fasttext.cc/docs/en/aligned-vectors',
        license_note='fastText aligned vectors by Facebook Research; CC-BY-SA-3.0: https://creativecommons.org/licenses/by-sa/3.0/ . Subset and 3D projections derived from aligned English and Chinese vectors.',
        source_hash=source_hash, seed_hash=sha256(seed), report={'language_counts': {k: len(v) for k,v in groups.items()}},
        source_format='fasttext-aligned-text', extract_mode='stream',
        provenance={'sources': sources, 'language_counts': {k: len(v) for k,v in groups.items()},
                    'builder_sha256': sha256(Path(__file__)), 'source_checksum_policy': 'SHA256 of sorted-key JSON source manifests'})
    print(json.dumps(meta['diagnostics'], indent=2))


if __name__ == '__main__':
    main()
