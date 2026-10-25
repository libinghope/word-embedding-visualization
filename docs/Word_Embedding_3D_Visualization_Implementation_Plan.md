# Word Embedding 三维语义空间可视化平台：实现方案

> 版本：v1.1（MVP 开发基线；2026-10-25 补齐数据与计算约定）  
> 目标读者：开发者、Codex、Claude 等代码助手  
> 核心原则：**三维投影负责直觉观察；原始高维向量负责相似度、最近邻和向量运算。**

## 1. 目标与范围

开发一个可在浏览器中运行的交互式词向量可视化平台。用户可以通过搜索词语、观察三维词云、比较多个词、查询最近邻及进行向量算术，探索静态词嵌入空间中的语义关系，并比较不同降维算法所展示的结构。

### 1.1 MVP 必须实现

1. 加载固定的 **1,000 个词**组成的演示词表，提供可重复的数据生成与导入流程。
2. 使用 **300 维 Word2Vec** 词向量（推荐预训练 `word2vec-google-news-300`；模型首次下载较大，见数据策略）。
3. 分别使用 **PCA(3)** 和 **UMAP(3)** 生成两组三维坐标，页面中可切换；**不把二者的坐标互相比较**。
4. Three.js 展示三维坐标系、点云、少量按需显示的词标签，支持轨道旋转、缩放、平移、悬停提示和点击选中。
5. 搜索词语并聚焦点位；支持多选，显示选中点的连线及对比面板。
6. 在**原始 300 维向量**上执行余弦相似度计算、Top-K 最近邻查询及 `A - B + C` 向量算术。
7. 展示 PCA/UMAP 映射的质量诊断，避免把投影空间的几何关系当作高维事实。
8. 具备最小自动化测试、运行脚本、错误提示和开发文档。

### 1.2 暂不实现

- 任意模型上传、几十万词同时渲染、用户账号、数据库、复杂模型训练、GPU 端实时降维、LLM 的逐 token 上下文嵌入、自动断言词对属于特定关系。
- 不预设“水果一定扎堆”“国王/女王一定形成平行四边形”等结果；展示实际模型结果。

### 1.3 验收场景

- 输入 `apple`，定位并高亮；显示原始向量最近邻及其相似度。
- 多选 `apple`, `orange`, `car`，在空间中高亮并连线；面板显示三组**高维余弦相似度**。
- 切换 PCA ↔ UMAP 时，选择状态保留，坐标重新绘制；相似度和最近邻结果不变。
- 输入 `king - man + woman`，展示最接近的 10 个词以及分数；词汇不存在时明确提示。
- 点云显示三维 XYZ 坐标和算法名称，并提供“投影失真”说明。

## 2. 技术架构

| 层 | 选择 | 职责 |
| --- | --- | --- |
| 数据处理 | Python 3.11+、NumPy、Gensim、scikit-learn、umap-learn | 词表加载、归一化、PCA/UMAP、质量指标、预计算 |
| API | FastAPI、Pydantic v2、Uvicorn | 返回数据集、搜索、相似度、最近邻、向量运算 |
| 前端 | Vue 3、TypeScript、Vite、Pinia | 状态管理、搜索、多选、结果面板 |
| 3D 渲染 | Three.js | 点云、相机、坐标轴、拾取、连线、按需标签 |
| 测试 | pytest、Vitest、Playwright（可逐步添加） | 算法正确性、API 合约、前端交互 |
| 部署 | Docker Compose（可选） | 本地或局域网运行；MVP 可直接双进程开发 |

**数据流**：预训练向量 → 离线构建脚本（挑选词表、生成 embeddings、PCA/UMAP、指标） → 版本化数据集文件 → FastAPI 加载 → Vue 获取点位、搜索、对比 → Three.js 交互显示。

**设计约束**：投影过程离线进行，页面加载不触发全量高维数据下载；后端保存原始向量以供精确计算。原始 300 维空间余弦相似度是默认相似性指标，若使用预归一化向量则通过点积计算。

## 3. 数据选择与生产

### 3.1 数据源

- 首选：Gensim downloader 中的 `word2vec-google-news-300`。首次下载体积约 1.5 GB，生成数据后服务端不必再加载整个原始模型。
- 备选：小规模开放预训练向量，需在数据集元数据中记录**实际模型、维度、来源、许可信息**，不能将 50/100 维模型假装成 300 维。
- 词表：`backend/data/seed_words.txt`（本文文件路径均相对仓库根目录，运行命令另注明工作目录），MVP 固定 1,000 个英文词，覆盖动物、水果、车辆、人物、地理、颜色、情感、抽象概念等。文件采用 UTF-8，每行一个 token，去除行首尾空白、忽略空行，按首次出现顺序去重；去重后必须恰为 1,000 词且全部存在于模型中，否则输出报告并以非零退出码结束，不静默补词或发布部分数据。人工修订词表后重新构建。词语选择应覆盖对照案例，而非仅选模型最相近的词。
- 模型词表中的大小写、下划线及多词短语要严格处理。MVP 使用词表文件内与模型键完全匹配的 token，并提供显式、确定性的查询规范化策略，避免不可解释的自动匹配。

### 3.2 离线生成数据

脚本：`backend/scripts/build_dataset.py`

1. 读取词表、去重；验证模型中是否存在词。
2. 获取原始向量，检查有限值、维度、零向量；生成 L2 归一化向量，供余弦运算。
3. 将高维原始向量用于 PCA(3) 和 UMAP(3)，不先对每行做 L2 归一化。PCA 使用 `n_components=3, svd_solver='full', whiten=False`，由算法中心化输入，不对各特征做标准化。UMAP 使用 `n_components=3, n_neighbors=15, min_dist=0.1, metric='cosine', output_metric='euclidean', init='spectral', random_state=42, n_jobs=1`；固定依赖版本并记录全部实际生效参数。
4. 将每种投影分别按第 3.5 节进行平移和统一尺度缩放；前端切换投影时不把展示坐标用于数学语义计算。
5. 计算 PCA explained variance ratio，并按第 3.5 节使用高维余弦距离计算两种投影的 trustworthiness；可选统计高维 vs 3D 邻域重叠率。
6. 写出 `backend/data/demo-v1/metadata.json`、`points.json`（或压缩格式）、`vectors.npy`；使用稳定 `word_id` 关联点与向量。
7. 输出 OOV 列表和构建日志。成果应可重复生成，构建过程不应依赖前端。

文件格式核心字段示例（完整必填约定见第 3.4–3.6 节）：

```json
// metadata.json（示例结构，数值按真实构建结果填写）
{
  "dataset_id": "demo-v1",
  "model_name": "word2vec-google-news-300",
  "embedding_dimensions": 300,
  "point_count": 1000,
  "algorithms": ["pca", "umap"],
  "random_seed": 42,
  "projection_params": {
    "pca": {"n_components": 3, "svd_solver": "full", "whiten": false, "input_normalization": "none"},
    "umap": {"n_components": 3, "n_neighbors": 15, "min_dist": 0.1, "metric": "cosine", "output_metric": "euclidean", "init": "spectral", "random_state": 42, "n_jobs": 1, "input_normalization": "none"}
  },
  "diagnostics": {"pca_explained_variance_ratio": [], "trustworthiness": {}},
  "license_note": "Check and document source-model terms before distribution"
}
```

```json
// points.json（示例结构）
{
  "dataset_id": "demo-v1",
  "points": [
    {
      "id": 0,
      "word": "apple",
      "category": "fruit",
      "positions": {"pca": [0.1, 0.2, -0.5], "umap": [0.4, -0.3, 0.9]}
    }
  ]
}
```

`category` 是人工维护的可选演示标签，不是模型自动识别的“事实”；可以用于着色，但界面须注明标签来源。**上述数值均为格式示例，不代表真实计算结果。**

### 3.3 词汇范围策略

MVP 的 Top-K 默认只在已加载的 1,000 词集合中检索，并在 UI 标明“当前数据集内最近邻”。向量算术亦只在该集合中检索答案。第二阶段可在后端加载更大词库或建立 ANN 索引，但必须区分“候选库范围”和“可见点范围”。

### 3.4 向量存储、标识与数值计算

- `vectors.npy` 保存源模型提取的**未归一化**向量，格式为 little-endian float32、形状 `(N, D)`，禁止 object 数组，读取时使用 `allow_pickle=False`。转换为 float32 后重新验证有限值及非零范数；计算时提升至 float64。真实 MVP 为 `N=1000, D=300`，合成测试数据必须使用独立 dataset_id 和 `data_kind='synthetic'`。
- `points[i].id == i`，且 `points[i].word` 对应 `vectors[i]`；ID 按清洗后的词表顺序分配，在同一不可变数据集版本内稳定。跨版本不承诺相同 ID，前端使用 `(dataset_id, id)` 标识词。词表、模型、顺序或投影参数改变时必须创建新版本，不覆盖已发布版本。
- 服务启动时由原始向量生成 float64 单位向量缓存 `u_i = v_i / ||v_i||₂`；不得用缓存覆盖原始向量。余弦相似度为 `u_i · u_j`，排序使用未四舍五入的分数；仅在输出前将浮点误差裁剪到 `[-1, 1]`。单元测试默认采用 `atol=1e-6, rtol=1e-6`。
- 类比目标 `t = Σ v_positive − Σ v_negative` 使用原始向量和 float64 累加，再计算 `u_i · (t / ||t||₂)`。令 `S` 为所有输入项原始向量范数之和，当 `||t||₂ <= 1e-12 * max(1, S)` 时返回 `ZERO_TARGET_VECTOR`，不得产生 NaN 或任意排名。
- 最近邻始终排除查询词；类比默认排除正负列表中所有输入词。按分数降序排列，分数完全相同时按 ID 升序；排除后不足 K 项时返回实际数量（可以为 0），不补齐、不重复。无需 ANN 或向量数据库。
- API 的 `space` 按实际维度生成为 `original_embedding_{D}d`，不可在备用数据集上硬编码 300D。

### 3.5 投影显示与质量诊断

- 对算法原始三维输出 `Y`，计算 `center = mean(Y, axis=0)`、`radius = max_i ||Y_i-center||₂`；当 radius 非有限或 `<=1e-12` 时构建失败。保存 `scale = 1/radius`，显示坐标为 `(Y-center)*scale`。三个轴共用一个正比例系数，禁止逐轴 min-max 或标准差缩放。
- `metadata.display_transforms` 分别保存 PCA/UMAP 的 `center`（三元素数组）、`scale`（正数）和 `method='center_max_radius'`。`points.json` 的 positions 已完成该变换，前端不得重复应用；坐标轴名称为 PC1/PC2/PC3 或 UMAP1/UMAP2/UMAP3，不赋予其固定语义名称。
- 对两种投影统一计算 `trustworthiness(X, Y, n_neighbors=k, metric='cosine')`；`X` 为原始高维向量，输出空间按欧氏距离评价，`Y` 使用缩放前坐标。真实 MVP 的 `k=10`；小型测试数据使用 `k=min(10, floor((N-1)/2))`，当 N<3 时构建失败。元数据分别记录 `value`、`n_neighbors`、`input_metric='cosine'`、`output_metric='euclidean'`、`sample_count=N`。
- PCA 记录三个分量的 explained variance ratio 及其累计值，明确其衡量原始向量方差，不等同于余弦邻域保真度。可选邻域重叠率使用相同 k、高维余弦/三维欧氏距离，排除自身，按 ID 处理并列，取各词邻居集合交集大小除以 k 后的均值。
- 不设置虚构的投影质量合格阈值，也不要求 UMAP 指标必然优于 PCA；指标必须真实、有限且位于定义范围内，低分应如实展示。

### 3.6 构建资源、可复现性与完整性

- 下载体积不等于内存预算。Google News 约 300 万 × 300 维的 float32 数值本身约 3.6 GB，另有词表、解析和临时对象开销；实际峰值应测量记录。最终 1,000 × 300 的 float32 原始矩阵约 1.2 MB。
- 下载和构建分离：构建默认只读取已缓存模型，缺失时给出显式下载命令并退出。支持 `--model-path` 复用本地文件；针对 Google News word2vec binary（含 gzip）提供 `--extract-mode stream` 顺序扫描、只保留目标词的模式，以降低峰值内存。扫描仍需读取源文件，不能承诺缩短下载或扫描时间。格式、压缩方式、模型名称和来源必须显式记录。
- `metadata.json` 必填：`schema_version`、`dataset_id`、`data_kind`、模型名称/来源 URL/许可说明、维度/点数、`vector_dtype`、`vector_normalization='none'`、`id_policy='seed_order_row_index'`、投影参数、显示变换、诊断、数值阈值、构建 UTC 时间、Python/依赖版本、操作系统、线程配置及构建脚本版本（Git commit；无 Git 时使用脚本 SHA-256）。
- `metadata.checksums` 保存源模型文件、原始词表文件、清洗后 token 序列、`points.json` 和 `vectors.npy` 的 SHA-256；token 序列规范为每个 token 后接 LF 的 UTF-8 字节串。元数据本身不做自引用哈希；需要校验整个交付包时使用包外清单。发布向量子集前同样核实源模型条款，不能用示例 license_note 代替已核实记录。
- 锁定依赖及输入顺序，记录完整参数和构建环境；相同固定环境的投影复建以 `atol=1e-5, rtol=1e-5` 比较算法输出，并检查诊断差异。若超差应调查并记录，不扩大容差掩盖变化；不承诺跨平台或跨版本逐位一致。日常演示使用已生成、版本化的产物。
- 先写临时目录，校验通过后发布。服务启动时验证文件哈希、dataset_id 一致、矩阵 shape/dtype、唯一词和连续 ID、行序对应关系、向量与坐标有限值、非零范数、诊断字段及显示变换。行序由清洗后 token 序列哈希和构建契约共同保证；无法仅从数值反推词语。校验失败时不注册该数据集，记录原因；不得静默切换为合成数据。
- 构建报告至少包含输入/去重/有效词数、重复词、OOV、源文件哈希、耗时及可获取的峰值内存。真实数据固定词表必须包含验收所用的 `apple`, `orange`, `car`, `king`, `man`, `woman`, `queen`。

## 4. API 设计（统一前缀 `/api/v1`）

| Method | Path | 功能 |
| --- | --- | --- |
| GET | `/datasets` | 列出可用数据集及元数据摘要 |
| GET | `/datasets/{dataset_id}/metadata` | 返回完整公开元数据，包括投影参数、显示变换、诊断、来源及构建版本；不暴露本地绝对路径 |
| GET | `/datasets/{dataset_id}/points` | 返回全部显示点及两种投影坐标 |
| GET | `/words/search?q=app&limit=20&dataset_id=demo-v1` | 前缀/包含搜索，返回 id、word |
| POST | `/similarity` | 计算多个词的两两原始高维余弦相似度 |
| GET | `/neighbors?word=apple&k=10&dataset_id=demo-v1` | 当前候选集合内的最近邻 |
| POST | `/analogy` | `positive`、`negative` 向量加减，查询最接近结果 |
| GET | `/health` | 服务健康状态 |

### 4.1 请求响应示例

```json
// POST /api/v1/similarity
{
  "dataset_id": "demo-v1",
  "words": ["apple", "orange", "car"]
}
```

```json
// 响应（仅示意字段，数值需真实计算）
{
  "dataset_id": "demo-v1",
  "metric": "cosine",
  "space": "original_embedding_300d",
  "words": ["apple", "orange", "car"],
  "matrix": [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
}
```

> 以上 `matrix` 的非对角线 0.0 只是结构占位符，**严禁硬编码当成真实结果**。

```json
// POST /api/v1/analogy
{
  "dataset_id": "demo-v1",
  "positive": ["king", "woman"],
  "negative": ["man"],
  "k": 10,
  "exclude_input_words": true
}
```

- 向量算术在**原始向量上求和/求差**，对所得目标向量计算与候选词的余弦相似度；若目标近零则返回业务错误；响应须包含 `candidate_scope` 和 `space`。
- 后端校验空查询、`k` 上限（1–50）、最多同时比较 10 个词、未知词、非法 dataset_id；用统一错误结构返回 400/404/422。
- 保证数字可 JSON 序列化，避免 NaN / Infinity。
- 数据集在服务启动时一次读取缓存；读请求不重新计算 UMAP。
- 开发期 CORS 仅允许本地 Vite 地址，不配置通配生产域名。

### 4.2 输入、输出及错误边界

- 所有查询 token 仅去除首尾空白，保留大小写和下划线，不自动词干化、不替换空格、不转换大小写；上限 128 个字符。搜索也按该规则匹配，先返回前缀匹配，再返回其余包含匹配，每组按 ID 升序；`limit` 为整数 1–50，默认 20。空查询返回 422，未匹配返回空列表。UI 选词后提交返回的标准 token。
- `similarity.words` 为 1–10 个词，去除首尾空白后不允许重复（422），矩阵行列保持请求顺序。任何词不在当前数据集中则整次请求失败，不返回部分矩阵。
- `analogy.positive` 为 1–10 项，`negative` 为 0–10 项，两者总数最多 10。重复项允许且逐次计权，跨列表相同词按代数规则抵消；先校验所有 token 存在，再计算目标。`exclude_input_words` 默认为 true，排除集合包含所有输入项，即使其相互抵消。
- `k` 为整数 1–50、默认 10。neighbors/analogy 响应统一包含 `dataset_id`、`metric='cosine'`、`space`、`candidate_scope='current_dataset'`、`candidate_count`（排除输入后的候选数）、`requested_k`、`returned_count` 和 `results`；每项结果为 `{id, word, score}`，结果数量等于 `min(k, candidate_count)`。
- dataset_id 仅通过已验证的数据集注册表解析，格式为 `[a-z0-9][a-z0-9_-]{0,63}`，不得直接拼接为任意文件路径。非法格式及输入结构/范围错误返回 422；格式合法但未知的数据集或词返回 404；近零目标返回 400。无可用数据集时 `/health` 返回 503，正常就绪返回 200。
- 所有 API 错误（包括框架校验错误）统一为 `{error: {code, message, details}}`。code 使用稳定机器可读值，例如 `VALIDATION_ERROR`、`DATASET_NOT_FOUND`、`WORD_NOT_FOUND`、`ZERO_TARGET_VECTOR`、`DATASET_UNAVAILABLE`；未知词的 details 列出缺失 token，不暴露堆栈或本地路径。

## 5. 前端交互与视觉设计

### 5.1 页面布局

- **顶部栏**：应用标题、数据集选择（MVP 唯一）、PCA/UMAP 切换、重置相机、说明入口。
- **左侧栏**：搜索框、搜索结果、已选词列表、添加/移除词、Top-K 选择。
- **中央三维画布**：点云、XYZ 轴、可选网格、鼠标悬停词提示、点击选择、线段连接已选词。
- **右侧详情**：选中词信息、相似度矩阵、最近邻及分数、向量算术输入输出。
- **底部提示**：当前投影、点数量、诊断指标、“三维距离不可替代高维语义相似度”。

### 5.2 操作定义

| 操作 | 行为 |
| --- | --- |
| 拖动鼠标左键 | 绕目标点旋转 |
| 滚轮 | 缩放 |
| 右键拖动 | 平移 |
| 悬停点 | 显示词标签/高亮 |
| 点击点 | 未选则加入，已选则移除；最多 10 词，达到上限时提示且保留已有选择 |
| 搜索选词 | 相机平滑聚焦，保留其余选择 |
| 多选 | 以固定颜色强调选中词，并连线；矩阵反映原始向量相似度 |
| PCA/UMAP 切换 | 重新定位点云，保留选择和相似度数据 |
| 点击邻居结果 | 在三维场景中聚焦对应词 |
| 重置 | 仅重置相机，不删除已选词；另设清空选择 |

**可视化注意事项**：

- 主渲染采用 Three.js `BufferGeometry` + `Points`，不要为每个词创建单独 Mesh。
- 3D 标注只显示选中、悬停、最近邻/关键词，避免 1,000 个 DOM 标签覆盖视图。
- 使用 Raycaster 点拾取（合理的 threshold），支持高 DPI；悬停事件节流。
- 选中点可用独立 Sprite/Mesh 标记并保持坐标同步；连线只表示“选择/比较”，**不能暗示语义因果或真实路径**。
- 色盲友好：颜色之外，用形状、边框或列表状态表达选中状态。
- 屏幕缩小时侧栏折叠，尽量保持画布可操作。
- 标签和结果必须来自真实词表/计算，不能仅写演示假数据。
- 搜索输入防抖 200 ms；使用 AbortController 和请求序号，仅接受当前数据集、当前查询的最新响应。相似度、最近邻和类比请求也以输入快照/序号丢弃过期响应，避免旧结果覆盖新选择。
- 左键 pointerdown 到 pointerup 的最大位移超过 5 CSS px，或发生 pointercancel/多指操作时，不触发点选择；阈值按 CSS 像素计算，不乘设备像素比。
- 切换投影时取消旧相机动画、清除悬停，更新点/选中标记/连线坐标并重新适配整个点云的包围球；保留选词、数学结果和高亮词 ID。不对两种算法坐标做对应插值，也不因投影切换重新请求相似度。

### 5.3 投影质量说明

- PCA 最大化保留投影方差，但无法保证保留所有语义邻域。
- UMAP 优先保留局部邻域，投影后的全局间距和方向未必有可解释含义。
- 将 `trustworthiness` 作为一种局部邻域忠实度参考，不宣称投影完全无损。
- 所有“最相似”“相似度数值”“类比结果”必须基于原始 300 维向量，而非绘制后的 3D 点距离。

## 6. 目录结构（建议）

```text
word-embedding-explorer/
├── README.md
├── docs/
│   ├── architecture.md
│   ├── data-sources.md
│   └── api.md
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py
│   │   ├── api/routes.py
│   │   ├── models/schemas.py
│   │   ├── services/dataset_service.py
│   │   ├── services/embedding_service.py
│   │   └── core/config.py
│   ├── scripts/build_dataset.py
│   ├── data/
│   │   ├── seed_words.txt
│   │   └── demo-v1/                 # 生成物，可不提交大型向量文件
│   └── tests/
│       ├── test_embedding_service.py
│       └── test_api.py
├── frontend/
│   ├── package.json
│   ├── src/
│   │   ├── main.ts
│   │   ├── App.vue
│   │   ├── api/client.ts
│   │   ├── stores/explorer.ts
│   │   ├── components/EmbeddingScene.vue
│   │   ├── components/WordSearch.vue
│   │   ├── components/ComparisonPanel.vue
│   │   ├── components/AnalogyPanel.vue
│   │   └── types/api.ts
│   └── tests/
└── docker-compose.yml               # 可选
```

代码职责划分：`dataset_service` 负责读取点位和元数据，`embedding_service` 负责余弦与向量运算；前端 Scene 仅负责绘制与拾取，业务状态统一放在 Pinia，不在 Three.js 对象中重复维护核心状态。

## 7. 开发阶段与任务拆分

### 数据预验证（进入三维功能开发前完成）

先用真实模型完成提取 1,000 词、PCA/UMAP、诊断、最近邻及类比的最小数据闭环，记录下载可用性、OOV、实际构建耗时及资源情况。可以与 Phase 0 的工程骨架工作交错进行，但应在 Phase 2 前验证真实数据链路。受网络或资源限制时继续合成数据的联调和测试，并明确真实数据验收仍未通过；不得将合成结果作为替代验收。

### Phase 0：工程骨架与可运行性

**交付**：FastAPI `/health` 可访问、Vue 页面可打开、API 客户端可请求、README 包含一键启动命令。

验收：本地运行前后端，浏览器无关键报错，CORS 配置正确。

### Phase 1：数据生成与数学服务

**交付**：`seed_words.txt`、可重复的构建脚本、生成结果、词向量服务、单元测试。

验收：同种输入和固定环境得到第 3.6 节容差内的结果；保存的原始向量未被归一化覆盖，运行时单位向量缓存范数接近 1；余弦对称、对角线接近 1；同词最近邻排除自身；OOV 返回清楚错误；`king - man + woman` 有合法结果但不要求输出一定为 `queen`。

**离线演示保障**：将少量合规许可、独立生成的示例数据用于 CI；真实 Word2Vec 模型下载仅在显式命令中执行，避免 CI 强制下载 1.5 GB 文件。

### Phase 2：三维可视化 MVP

**交付**：点云、坐标轴、相机控制、悬停、点击、搜索、高亮、PCA/UMAP 切换。

验收：显示 1,000 个点；点击点与 UI 列表互相同步；搜索后相机聚焦；切换投影不清除选择；页面无明显内存泄漏（销毁组件后释放 geometry/material/controls/listeners）。

### Phase 3：语义关系探索

**交付**：多选相似度矩阵、最近邻、向量算术与结果高亮。

验收：所有数值与后端结果一致；没有任何基于三维欧氏距离的“语义相似度”计算；API 出错时显示可读提示；最多 10 词的比较矩阵可用。

### Phase 4：验证、优化、文档

**交付**：数据来源、投影诊断、单元/接口/UI 核心测试、性能检查、开发/部署指南。

验收：刷新可正确加载；PCA 与 UMAP 切换顺畅；正常开发桌面环境下 1,000 点交互流畅（建议目标 30 FPS 以上，以实际测试设备记录）；网络请求失败可恢复；README 从全新仓库克隆后可照步骤启动。

## 8. 测试清单

### 8.1 数学正确性

- 已归一化的非零向量 `cos(v,v)` ≈ 1。
- `cos(a,b)` ≈ `cos(b,a)`，所有有限值位于 [-1, 1]（考虑浮点误差）。
- 词不存在、零向量、空词表、无效维度时处理正确。
- Top-K 降序、无重复、排除查询词，`k` 边界正确。
- 类比的目标向量按正负列表计算，候选词范围明确，可选择排除输入项。
- 投影切换不改变原始相似度结果。
- 使用范数不同的手工向量验证类比确实先对原始向量相加，再归一化目标；覆盖重复计权、跨列表抵消、近零阈值两侧、同分按 ID 排序及候选不足 K。
- 验证显示变换共用一个尺度，三维点间距离按同一比例变化；诊断采用高维 cosine、输出 Euclidean，覆盖小数据集 k 的边界。
- 篡改文件哈希、重复 ID、错序 token、非法 dtype/shape、非有限值和损坏元数据时，数据集不得注册；验证重新构建不会覆盖已发布版本。

### 8.2 API

- Schema 与类型验证、错误码、非法词/数据集、`k > 50`、比较词数上限。
- 查询一致性、数据集 `metadata` 与点数/维度一致。
- CORS 和异常处理。
- 完整 metadata 接口包含实际参数、显示变换及诊断；space 随实际维度变化；候选数与返回数准确；框架校验错误也符合统一结构。
- 搜索大小写/下划线规则、重复比较词、类比项数上限、未知词整次失败，以及所有数据集不可用时 health 返回 503。

### 8.3 UI 与可用性

- 相机操控、鼠标拾取、标签遮挡、搜索及多选同步。
- 网络延迟/错误状态、loading/empty 状态。
- 不同视口大小、缩放比例及常见桌面浏览器。
- 搜索与数学请求乱序不覆盖最新状态；旋转拖动不误选；投影切换取消旧相机动画并适配点云，保持数学结果不变；第 11 个选词有明确提示。

## 9. 风险与应对

| 风险 | 应对 |
| --- | --- |
| 模型下载大、首建慢 | 下载与构建分离；支持复用本地模型；离线小型合成数据用于测试 |
| 部分词 OOV | 构建报告 OOV、完善词表；UI 显示未收录，不隐式猜词 |
| UMAP 图像随机/参数敏感 | 固定种子、参数、版本，记录构建环境 |
| 3D 映射误导 | 双空间计算、明确投影注释、诊断指标 |
| 性能随点数增长 | BufferGeometry、限制标签、节流拾取；大数据再做 LOD/分块 |
| 版权/分发 | 记录词向量模型许可证；未经核实不随仓库发布预训练模型文件 |
| 相似度方向易误解 | 连线作为 UI 比较工具；分数注明“原始 300D 余弦” |

## 10. 本地运行与交付要求

建议 README 提供如下命令（具体以生成后的 `pyproject.toml` / npm scripts 为准）：

```bash
# 后端（在 backend/ 下）
python -m venv .venv
# 按平台激活虚拟环境
pip install -e '.[dev]'
python scripts/build_dataset.py --model word2vec-google-news-300 --seed-file data/seed_words.txt --output data/demo-v1
uvicorn app.main:app --reload --port 8000

# 前端（在 frontend/ 下）
npm install
npm run dev
```

建议前端通过 `VITE_API_BASE_URL=http://localhost:8000/api/v1` 配置接口地址；服务端不要假设项目根目录即为运行目录，使用配置文件或基于模块位置的路径解析。

上述构建命令假定模型已缓存；README 必须另提供显式下载步骤、本地 `--model-path` 和 `--extract-mode stream` 示例。相对 CLI 输入/输出路径按调用时工作目录解析并在日志中显示解析结果，服务默认数据目录按后端模块位置解析。开发依赖使用锁文件固定，不以 `Python 3.11+` 代替实际验证过的版本记录。

**最终交付物**：可运行源码、数据构建脚本、示例词表、API 文档、关键测试、README、数据来源/许可说明、已知限制文档及截图（截图仅用于展示，不代替可运行交互）。

## 11. 发给 Codex / Claude 的执行提示词

> 你是一位资深 Python/FastAPI、Vue3/TypeScript、Three.js 工程师。请根据本 Markdown 文档实现一个可运行的 Word Embedding 三维语义空间探索工具。
>
> 按 Phase 0 → 1 → 2 → 3 → 4 的顺序开发，每阶段提供修改文件清单、启动命令、实际运行/测试结果和遗留问题。优先形成可运行闭环；不要提前实现账户、数据库或复杂部署。
>
> 强制要求：数学计算（余弦、最近邻、类比）全部在原始高维向量中执行；PCA/UMAP 仅负责三维布局。不要硬编码假的相似度或类比结果。不要用随机点云冒充真实预训练数据；若模型缺失，可启用明确标记为 synthetic-demo 的小型测试数据，并提示用户切换到真实构建数据。
>
> 统一 TypeScript/Pydantic API 数据结构；保持代码职责清晰；新增功能时同步补充测试和 README。词向量数据集使用稳定 id，记录来源、维度、投影参数及许可信息。
>
> 如实际模型下载/硬件/网络受限，说明阻塞点，并完成可用的测试替代闭环，不要编造构建与测试成功。每阶段完成后自行运行已有测试，修复后再继续。

## 12. 后续研究方向（非 MVP）

1. **多语义上下文**：引入 BERT / LLM 的上下文 token 表示，对同一词在不同句子中的 embedding 进行对比。
2. **语义方向研究**：比较多组词对的高维差分方向及余弦一致性，探索哪些语义类比具有统计稳定性。
3. **投影误差可视化**：针对选中词，显示“高维最近邻”与“三维最近邻”的差异及排序变化。
4. **局部重投影**：围绕选中词构建局部 PCA/UMAP 空间，同时明确投影坐标系已改变。
5. **模型间比较**：相同词表、相同指标，比较 Word2Vec / GloVe / fastText / 上下文模型。

---

**验收底线**：这是一个帮助人类建立语义空间直觉的探索工具，而不是通过降维画面证明语义关系的统计结论。所有可量化的语义判断均应能回溯到原始高维向量与数据来源。

技术参考（v1.1 约定依据）：[Gensim 模型清单](https://raw.githubusercontent.com/piskvorky/gensim-data/master/list.json)、[PCA 参数与输入处理](https://scikit-learn.org/stable/modules/generated/sklearn.decomposition.PCA.html)、[trustworthiness 距离定义](https://scikit-learn.org/stable/modules/generated/sklearn.manifold.trustworthiness.html)、[UMAP 可复现性](https://umap-learn.readthedocs.io/en/latest/reproducibility.html)。本文数值阈值、显示尺度、错误结构和排序规则是本项目的实施约定。
