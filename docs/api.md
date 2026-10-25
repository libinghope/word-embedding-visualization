# API 合约

前缀 `/api/v1`。运行后的 `/docs` 提供自动生成的请求 Schema。

| Method | 路径 | 参数 / 返回 |
| --- | --- | --- |
| GET | `/health` | 有可用数据集返回 200，否则 503 |
| GET | `/datasets` | 已验证的数据集摘要数组 |
| GET | `/datasets/{id}/metadata` | 完整公开元数据，含来源、参数、显示变换、诊断 |
| GET | `/datasets/{id}/points` | `{dataset_id, points: [{id, word, positions: {pca, umap}}]}` |
| GET | `/words/search` | `dataset_id,q,limit=20`；返回 `{id,word}[]` |
| POST | `/similarity` | `{dataset_id,words}`；返回 `{dataset_id,metric,space,words,matrix}` |
| GET | `/neighbors` | `dataset_id,word,k=10`；返回排名对象 |
| POST | `/analogy` | `{dataset_id,positive,negative:[],k:10,exclude_input_words:true}`；返回排名对象 |

排名对象包含 `dataset_id, metric='cosine', space='original_embedding_{D}d', candidate_scope='current_dataset', candidate_count, requested_k, returned_count, results`，每项结果为 `{id,word,score}`。候选数在排除输入后计算，实际返回 `min(k,candidate_count)`，可以为空。

token 首尾去空白、长度 1–128、保留大小写/下划线。搜索先前缀再包含，每组按 ID 排序；limit 和 k 为 1–50。比较为 1–10 个唯一词。类比 positive 至少 1 项，negative 可为空，总项数最多 10；重复逐次计权，跨组抵消。未知词导致整次请求失败。

统一错误：`{error:{code,message,details}}`。422 为结构/范围/非法 dataset_id，404 为未知词或未知数据集，400 为近零向量，503 为没有可用数据。code 包括 `VALIDATION_ERROR`、`WORD_NOT_FOUND`、`DATASET_NOT_FOUND`、`ZERO_TARGET_VECTOR`、`DATASET_UNAVAILABLE`。错误不返回本地路径和堆栈。

请求示例：`POST /api/v1/analogy`，JSON 为 `{"dataset_id":"demo-v1","positive":["king","woman"],"negative":["man"],"k":10}`。所有分数由数据实际计算，不预设 queen 排名。
