# Semantic Atlas · 词向量三维探索

基于 FastAPI、Vue 3、Pinia、TypeScript 和 Three.js 的本地交互工具。PCA/UMAP 负责三维布局；相似度、最近邻与向量加减全部在原始高维向量上计算。

功能：1,000 词点云、旋转/缩放/平移、悬停、点击多选、搜索聚焦、投影切换、最多 10 词比较矩阵、Top-K 最近邻、向量表达式、投影质量与数据来源说明、移动端分栏切换、错误恢复。

## 本地启动

需要 Python 3.12–3.13、Node.js 22.12+ 和 pnpm。当前锁定的 NumPy/SciPy 要求 Python 3.12+；实际验证版本与结果见 [验证记录](docs/verification.md)。所有命令除注明外在仓库根目录运行。

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.lock
cd frontend
pnpm install --frozen-lockfile
cd ..

# 首次体验：显式生成随机测试向量，再启动两项服务
.\.venv\Scripts\python.exe scripts\dev.py --demo
```

打开 http://127.0.0.1:5173 。API 文档为 http://127.0.0.1:8000/docs 。Ctrl+C 停止两项服务。`--demo` 仅在 synthetic-demo 不存在时构建，不覆盖已有版本；未加此参数时不会创建或下载任何数据。

Linux/macOS 将 `.venv\Scripts\python.exe` 换为 `.venv/bin/python`，路径分隔符改为 `/`。如果 Windows 的 ensurepip 失败，可用已有系统 pip：`python -m pip --python .venv\Scripts\python.exe install -r backend\requirements.lock`。

**synthetic-demo 使用固定随机种子生成，不能用于真实语义解释。** 页面有持续提示；真实数据存在时默认优先选择真实数据。不隐式下载模型、不在请求期间运行降维，也不自动用假数据替换损坏的数据集。

## 当前中英真实数据

默认优先加载 `fasttext-en-zh-v1`：从已下载的 fastText RCSLS 对齐模型提取 768 个英文词、232 个中文词，共 1,000 × 300 维。词表固定在 `backend/data/fasttext_seed.json`，中文和英文共同拟合 PCA/UMAP，不混入 Google News 向量。搜索与最近邻候选范围为此子集，不是完整模型词表。

```powershell
# 已下载模型和对应 .vec.json 校验清单后构建；已有输出不会覆盖
.\.venv\Scripts\python.exe backend\scripts\build_fasttext_dataset.py
# 已构建时直接启动
.\.venv\Scripts\python.exe scripts\dev.py
```

构建器流式读取两份模型并核验 SHA-256、行数、维度、有限值和词表覆盖；来源与许可保存在生成数据的 metadata.json 中。数据依据 CC-BY-SA-3.0 使用。示例：搜索 `apple`、`苹果`，加入比较以查看原始向量的跨语言余弦相似度。

2026-10-25 验证：37 项后端测试、9 项前端单元测试、4 项浏览器测试通过，类型检查与生产构建通过。浏览器测试覆盖中文搜索、跨语言比较及 PCA/UMAP 切换。此子集 PCA 三维解释方差为 17.17%，UMAP 局部可信度为 0.9709。

## 真实 Word2Vec 数据

下载约 1.74 GB（约 1.62 GiB），需额外磁盘空间用于下载缓存。流式提取不将整个 300 万词模型装入内存，但仍须扫描压缩源文件。来源与许可状态见 [数据说明](docs/data-sources.md)。

```powershell
# 下载是独立、显式操作；将模型缓存放在项目内
$env:GENSIM_DATA_DIR = Join-Path (Get-Location) 'backend\models'
.\.venv\Scripts\python.exe backend\scripts\download_model.py

# 本地构建；license-note 必须如实填写来源核查结果和使用范围
.\.venv\Scripts\python.exe backend\scripts\build_dataset.py --model-path backend\models\word2vec-google-news-300\word2vec-google-news-300.gz --extract-mode stream --seed-file backend\data\seed_words.txt --output backend\data\demo-v1 --license-note "Gensim catalog reports license not found; local evaluation only; redistribution not cleared."
```

`--model-path` 支持 word2vec binary 及其 gzip 压缩格式；也可指定 `--extract-mode gensim`，但会加载全模型。省略 model-path 时只查 Gensim 本地缓存，缺失会报错，不触发下载。其他本地 300D Word2Vec 模型需同时填写准确的 `--model`、`--source-url`、`--license-note`。

词表固定为 `backend/data/seed_words.txt`。遇到 OOV 构建失败并输出完整列表，需人工修改词表保持 1,000 个唯一词。构建成功生成 `metadata.json`、`points.json`、`vectors.npy` 和 `build-report.json`。已有输出目录不可覆盖；变更输入或参数请使用新的 dataset_id。构建后重启后端，使其重新校验并注册数据集。

## 开发与测试

```powershell
# 后端
cd backend
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000

# 另一个终端，进入 frontend
pnpm dev
pnpm test
pnpm build

# 浏览器端到端测试：先启动前后端并构建至少一个 1,000 词数据集
pnpm exec playwright install chromium
pnpm test:e2e
```

Windows 若下载的 Chromium 无法启动，可使用已经安装的 Edge：`$env:PLAYWRIGHT_CHANNEL='msedge'; pnpm test:e2e`。这是本次通过浏览器验收的配置。

数学与 API 测试采用手工小向量，不下载模型，也不依赖真实类比恰好命中特定词。浏览器测试验证完整交互链及移动端布局。锁文件固定依赖；升级后应重跑测试并创建新数据版本，避免跨版本声称完全复现。

默认 Vite 代理 `/api` 到 `127.0.0.1:8000`；分离部署时设置 `VITE_API_BASE_URL`。后端可通过 `DATA_DIR` 指向数据集父目录，默认为模块位置下的 `backend/data`。CORS 只允许本地 5173 端口。生产静态资源由 `pnpm build` 生成在 `frontend/dist`；部署时需反向代理 `/api/v1` 到 FastAPI，开发服务器不是生产托管服务。

## 操作约定

- 点击点切换选择，搜索结果加入选择并聚焦；邻居结果仅聚焦。列表中的词可设为最近邻查询焦点。
- 拖动不触发选择；重置只恢复相机，清空按钮才删除选择。切换投影保留选择与数学结果。
- 搜索区分大小写，保留下划线。表达式使用空格分隔，例如 `king - man + woman`；重复词逐次计权，最多 10 项。
- 所有排名仅在当前 1,000 词中查找。原始向量先加减再归一化目标；不保证结果为 queen。
- 类别未人工标注，因此点使用统一颜色；金色线框标记选中，紫色表示计算结果，不暗示模型自动发现的分类。

详细说明：[架构](docs/architecture.md) · [API](docs/api.md) · [数据来源](docs/data-sources.md) · [已知限制](docs/known-limitations.md) · [实现方案](docs/Word_Embedding_3D_Visualization_Implementation_Plan.md)。
