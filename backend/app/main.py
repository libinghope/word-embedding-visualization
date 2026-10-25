from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, Query
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from starlette.exceptions import HTTPException

from .services.dataset_service import ID_PATTERN, Registry
from .services.embedding_service import DomainError, analogy, neighbors, similarity
from .models.schemas import DatasetSummary, PointsResponse, MetadataResponse, Word, ComparisonResponse, RankingResponse

Token = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=128)]
DatasetID = Annotated[str, StringConstraints(pattern=r"^[a-z0-9][a-z0-9_-]{0,63}$")]


class Comparison(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: DatasetID
    words: list[Token] = Field(min_length=1, max_length=10)

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.words)) != len(self.words):
            raise ValueError("Comparison words must be unique")
        return self


class Analogy(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dataset_id: DatasetID
    positive: list[Token] = Field(min_length=1, max_length=10)
    negative: list[Token] = Field(default_factory=list, max_length=10)
    k: int = Field(default=10, ge=1, le=50, strict=True)
    exclude_input_words: bool = True

    @model_validator(mode="after")
    def limit(self):
        if len(self.positive) + len(self.negative) > 10:
            raise ValueError("At most 10 total terms")
        return self


def create_app(data_root: Path | None = None) -> FastAPI:
    root = data_root or Path(os.environ.get("DATA_DIR", Path(__file__).resolve().parents[1] / "data"))

    @asynccontextmanager
    async def lifespan(app):
        app.state.registry = Registry(root)
        for name, reason in app.state.registry.failures.items():
            logging.error("Dataset %s rejected: %s", name, reason)
        yield

    app = FastAPI(title="Semantic Atlas", version="0.1.0", lifespan=lifespan)
    app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
                       allow_methods=["GET", "POST"], allow_headers=["Content-Type"])

    def error(status, code, message, details=None):
        return JSONResponse(status_code=status, content={"error": {"code": code, "message": message, "details": details or {}}})

    @app.exception_handler(DomainError)
    async def domain_error(_, exc):
        return error(exc.status, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(_, exc):
        return error(422, "VALIDATION_ERROR", "请求参数不符合要求。", {"fields": [
            {"location": list(e["loc"]), "message": e["msg"]} for e in exc.errors()]})

    @app.exception_handler(HTTPException)
    async def http_error(_, exc):
        return error(exc.status_code, "HTTP_ERROR", str(exc.detail))

    @app.exception_handler(Exception)
    async def unexpected(_, exc):
        logging.exception("Unhandled API error", exc_info=exc)
        return error(500, "INTERNAL_ERROR", "服务暂时无法完成请求，请重试。")

    def get_dataset(dataset_id):
        if not ID_PATTERN.fullmatch(dataset_id):
            raise DomainError(422, "VALIDATION_ERROR", "无效的数据集标识。")
        registry = app.state.registry
        if dataset_id not in registry.datasets:
            raise DomainError(404, "DATASET_NOT_FOUND", "数据集不存在或未通过完整性检查。")
        return registry.datasets[dataset_id]

    @app.get("/api/v1/health")
    def health():
        n = len(app.state.registry.datasets)
        if not n:
            raise DomainError(503, "DATASET_UNAVAILABLE", "没有可用数据集，请先运行数据构建脚本。")
        return {"status": "ok", "datasets": n}

    @app.get("/api/v1/datasets", response_model=list[DatasetSummary])
    def datasets():
        return [{key: ds.metadata[key] for key in ("dataset_id", "model_name", "data_kind", "point_count", "embedding_dimensions")}
                for ds in app.state.registry.datasets.values()]

    @app.get("/api/v1/datasets/{dataset_id}/metadata", response_model=MetadataResponse)
    def metadata(dataset_id: str):
        return get_dataset(dataset_id).metadata

    @app.get("/api/v1/datasets/{dataset_id}/points", response_model=PointsResponse, response_model_exclude_none=True)
    def points(dataset_id: str):
        return {"dataset_id": dataset_id, "points": get_dataset(dataset_id).points}

    @app.get("/api/v1/words/search", response_model=list[Word])
    def search(dataset_id: str, q: Annotated[Token, Query()], limit: Annotated[int, Query(ge=1, le=50)] = 20):
        ds = get_dataset(dataset_id)
        prefix = [i for i, w in enumerate(ds.words) if w.startswith(q)]
        rest = [i for i, w in enumerate(ds.words) if q in w and not w.startswith(q)]
        return [{"id": i, "word": ds.words[i]} for i in (prefix + rest)[:limit]]

    @app.post("/api/v1/similarity", response_model=ComparisonResponse)
    def compare(body: Comparison):
        return similarity(get_dataset(body.dataset_id), body.words)

    @app.get("/api/v1/neighbors", response_model=RankingResponse)
    def nearest(dataset_id: str, word: Annotated[Token, Query()], k: Annotated[int, Query(ge=1, le=50)] = 10):
        return neighbors(get_dataset(dataset_id), word, k)

    @app.post("/api/v1/analogy", response_model=RankingResponse)
    def arithmetic(body: Analogy):
        return analogy(get_dataset(body.dataset_id), body.positive, body.negative, body.k, body.exclude_input_words)

    return app


app = create_app()
