# 数据来源与使用边界

人工维护词表：`backend/data/seed_words.txt`，1,000 个唯一英文 token，覆盖常见食物、动物、交通、人物、自然、情感与生活物品。词表顺序决定单一版本内的 ID，不对语义簇作人为分类标注。

首次真实模型扫描报告 OOV 为 `grey` 和 `uranus`。人工修订为独立词 `charcoal` 与保留大小写的 `Uranus` 后重新构建，未使用查询时自动猜词或静默替换。最初生成的 synthetic-demo 保留其自身原始词表与哈希；不同数据集版本的词表不强制相同。

真实模型目标为 `word2vec-google-news-300`：约 300 万词/短语、300 维。Gensim [官方目录](https://raw.githubusercontent.com/piskvorky/gensim-data/master/list.json)记录压缩文件 1,743,563,840 字节，MD5 `a5e5354d40acb95f9ec66d5977d140ef`，来源为 [word2vec 项目归档](https://code.google.com/archive/p/word2vec/)。下载脚本通过 Gensim 检查下载校验和，构建另记录源文件 SHA-256。

2026-10-25 核查时 Gensim 模型目录的 license 字段为 `not found`。不能把 word2vec 代码或 Gensim 的软件许可证当成预训练权重的许可证。本项目不随源码分发 Google News 权重或真实向量子集；本机生成物被 `.gitignore` 排除。构建时 license-note 如实记录核查结果与本地评估范围，公开分发前需另行解决授权问题。

`synthetic-demo` 为项目脚本用 NumPy 固定种子 42 生成的随机 300D 向量。它与词表对应，但随机数不表示词语的语义；PCA/UMAP 和数学结果仍由这些向量实际计算。它仅用于离线交互、性能与工程测试，页面持续显示提醒，不能据此得出语义结论。

CI 小样本使用手工向量与明确的预期值，验证原始向量算术、排除规则、分数、错误处理与完整性检查；测试夹具中的坐标和诊断为格式测试数据，不作为演示数据发布。
