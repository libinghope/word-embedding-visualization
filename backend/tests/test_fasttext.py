import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from build_fasttext_dataset import extract


@pytest.fixture
def source(tmp_path):
    path = tmp_path / 'aligned.vec'
    path.write_text('2 300\napple ' + ' '.join(['0.25'] * 300) + '\n苹果 ' + ' '.join(['0.5'] * 300) + '\n', 'utf-8')
    path.with_suffix('.vec.json').write_text(json.dumps({'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}))
    return path


def test_unicode_extraction_preserves_seed_order_and_values(source):
    vectors, _ = extract(source, ['苹果', 'apple'])
    np.testing.assert_array_equal(vectors, np.array([[0.5] * 300, [0.25] * 300], dtype='<f4'))


def test_missing_word_fails_explicitly(source):
    with pytest.raises(ValueError, match='OOV: missing'):
        extract(source, ['missing'])


def test_source_integrity_checked(source):
    source.with_suffix('.vec.json').write_text(json.dumps({'sha256': '0' * 64}))
    with pytest.raises(ValueError, match='checksum'):
        extract(source, ['apple'])
