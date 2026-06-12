# 猿辅导销售知识库

这个目录由 `scripts/build_yuanfudao_knowledge.py` 从飞书导出的资料包生成。

## 自动导入到知识库文档

- `documents/` 目录包含 70 个可导入文件（Markdown / Excel / PDF / PPT，不含视频）。
- 后端启动时会自动把这些文件导入「猿辅导销售知识库」。

## 聚合检索语料

- `rag/yuanfudao_knowledge_index.md`
- `rag/yuanfudao_markdown_corpus.md`
- `rag/yuanfudao_spreadsheet_catalog.md`

原始视频和超过 500MB 的文件不会进入知识库文档；如需要逐个查看，回到下载目录的原始资料。

## 时效规则

价格、排期、权益、赠品、活动有效期以最新活动页、班主任通知、系统后台为准；历史资料用于话术学习和异议处理。
