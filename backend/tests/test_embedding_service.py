import numpy as np
import pytest

from app.services.dataset_service import Dataset
from app.services.embedding_service import DomainError, analogy, neighbors, similarity


def test_cosine_matrix(dataset_folder):
    ds = Dataset(dataset_folder)
    result = similarity(ds, ["king", "woman", "queen"])
    matrix = np.array(result["matrix"])
    np.testing.assert_allclose(matrix, matrix.T, atol=1e-6)
    np.testing.assert_allclose(matrix.diagonal(), 1, atol=1e-6)
    assert matrix[0, 1] == 0
    assert matrix[0, 2] == pytest.approx(3 / np.sqrt(13))
    assert result["space"] == "original_embedding_3d"
    assert ds.vectors[0, 0] == 4  # raw values are retained


def test_raw_arithmetic_not_normalized_inputs(dataset_folder):
    ds = Dataset(dataset_folder)
    result = analogy(ds, ["king", "woman"], ["man"], 10, True)
    assert result["results"][0]["word"] == "queen"
    assert result["results"][0]["score"] == pytest.approx(1)
    assert result["candidate_count"] == result["returned_count"] == 4
    assert not {"king", "woman", "man"} & {r["word"] for r in result["results"]}


def test_duplicates_cancellation_and_zero(dataset_folder):
    ds = Dataset(dataset_folder)
    result = analogy(ds, ["king", "king", "woman"], ["king", "man"], 10, True)
    assert result["results"][0]["word"] == "queen"
    with pytest.raises(DomainError) as exc:
        analogy(ds, ["king"], ["king"], 10, False)
    assert exc.value.code == "ZERO_TARGET_VECTOR"
    with pytest.raises(DomainError) as exc:
        analogy(ds, ["unknown"], ["unknown"], 10, True)
    assert exc.value.code == "WORD_NOT_FOUND"


def test_ties_self_exclusion_and_empty_candidates(dataset_folder):
    ds = Dataset(dataset_folder)
    result = neighbors(ds, "car", 50)
    assert [r["id"] for r in result["results"]] == list(range(6))
    assert result["requested_k"] == 50 and result["returned_count"] == 6
    result = analogy(ds, ds.words, [], 10, True)
    assert result["results"] == [] and result["candidate_count"] == 0


@pytest.mark.parametrize('delta,rejected', [(1e-13, True), (1e-10, False)])
def test_relative_zero_threshold(dataset_folder, delta, rejected):
    ds = Dataset(dataset_folder)
    ds.vectors = ds.vectors.copy()
    ds.vectors[0] = [1, delta, 0]
    ds.vectors[1] = [1, 0, 0]
    if rejected:
        with pytest.raises(DomainError) as error:
            analogy(ds, ['king'], ['man'], 3, True)
        assert error.value.code == 'ZERO_TARGET_VECTOR'
    else:
        assert analogy(ds, ['king'], ['man'], 3, True)['returned_count'] == 3

