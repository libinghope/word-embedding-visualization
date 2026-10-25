from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DatasetSummary(BaseModel):
    dataset_id: str
    model_name: str
    data_kind: Literal['synthetic', 'pretrained']
    point_count: int
    embedding_dimensions: int


class Positions(BaseModel):
    pca: tuple[float, float, float]
    umap: tuple[float, float, float]


class Word(BaseModel):
    id: int
    word: str


class Point(Word):
    positions: Positions
    category: str | None = None


class PointsResponse(BaseModel):
    dataset_id: str
    points: list[Point]


class ComparisonResponse(BaseModel):
    model_config = ConfigDict(allow_inf_nan=False)
    dataset_id: str
    metric: Literal['cosine']
    space: str
    words: list[str]
    matrix: list[list[float]]


class RankedWord(Word):
    score: float = Field(ge=-1, le=1)


class RankingResponse(BaseModel):
    dataset_id: str
    metric: Literal['cosine']
    space: str
    candidate_scope: Literal['current_dataset']
    candidate_count: int
    requested_k: int
    returned_count: int
    results: list[RankedWord]


class Diagnostic(BaseModel):
    value: float = Field(ge=0, le=1)
    n_neighbors: int
    input_metric: Literal['cosine']
    output_metric: Literal['euclidean']
    sample_count: int


class Diagnostics(BaseModel):
    pca_explained_variance_ratio: list[float]
    pca_explained_variance_total: float
    trustworthiness: dict[Literal['pca', 'umap'], Diagnostic]


class MetadataResponse(DatasetSummary):
    model_config = ConfigDict(extra='allow', allow_inf_nan=False)
    schema_version: int
    source_url: str
    license_note: str
    diagnostics: Diagnostics
    projection_params: dict
    display_transforms: dict
    numeric_policy: dict
    build: dict
    checksums: dict[str, str]

