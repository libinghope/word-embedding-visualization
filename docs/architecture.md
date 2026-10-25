# 架构与数据契约

离线构建：预训练文件或显式随机数据 → 固定有序词表 → 原始 float32 向量 → PCA/UMAP → 统一显示尺度 → 质量指标 → 临时目录验证 → 不可覆盖的数据集目录。

在线服务：启动时 Registry 扫描数据目录并验证哈希、ID/行序契约、shape/dtype、有限值、非零向量及诊断；失败数据集不注册。Dataset 保存原始向量的 float64 计算副本和单位向量缓存。请求期间只进行精确点积与排序，不降维、不加载全模型、不下载数据。完整高维向量不传到浏览器。

`points[i].id == i` 对应 `vectors[i]`；原始词表与规范化 token 顺序均有 SHA-256。模型、词表顺序、算法参数或依赖发生变化时使用新 dataset_id。不同版本的 ID 不能混用。文件哈希检测意外损坏，不是防恶意篡改的签名。

原始向量不被单位向量缓存覆盖。相似度为单位向量点积；类比先以 float64 累加原始向量，再归一化目标。近零阈值为 `1e-12 * max(1, 所有输入项范数之和)`。按未四舍五入分数降序、ID 升序排序，输出裁剪到 [-1,1]；默认排除查询词或类比输入词。

PCA 使用 full SVD、不 whiten、不预归一化。UMAP 使用原始向量、cosine 距离、固定种子 42、单线程，记录实际参数。每个投影单独平移至均值中心，再以最大点半径的倒数统一缩放三轴。trustworthiness 以高维 cosine 与三维 Euclidean 衡量，MVP k=10。显示坐标不参与任何语义数值计算。

前端 Pinia 保存数据集、投影、选择、当前词与计算结果。Three.js 组件维护绘制对象、相机与拾取，使用一个 Points 对象及少量选择线框。组件卸载时释放几何体、材质、controls、监听和 WebGL 上下文。搜索取消过期请求；数学与类比通过序号防止旧响应覆盖新状态。切换投影不重新计算语义结果。

模块入口：`backend/scripts/build_dataset.py`、`backend/app/services/dataset_service.py`、`backend/app/services/embedding_service.py`、`backend/app/main.py`、`frontend/src/stores/explorer.ts`、`frontend/src/components/EmbeddingScene.vue`。
