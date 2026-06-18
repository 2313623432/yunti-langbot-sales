# 猿辅导清洗知识库 - 平台无关上传包

这个压缩包只包含可放入火山引擎或其他知识库的清洗数据，不包含项目模板、manifest、向量库、本地数据库或项目配置。

## 推荐上传顺序

1. `01_markdown_upload/00_猿辅导FAQ_话术_SOP总知识库.md`
   - FAQ、销售话术、群发 SOP 总文档。
2. `01_markdown_upload/04_猿辅导课程货盘知识库.md`
   - 课程货盘/产品事实清洗版。
4. 或者分别上传：
   - `01_markdown_upload/01_猿辅导FAQ问答知识库.md`
   - `01_markdown_upload/02_猿辅导销售话术知识库.md`
   - `01_markdown_upload/03_猿辅导1天2次群发SOP知识库.md`
   - `01_markdown_upload/04_猿辅导课程货盘知识库.md`
   - `01_markdown_upload/05_猿辅导QA对知识库.md`
5. 如果平台对 Markdown 解析不好，可以上传 `02_txt_upload/` 里的 TXT 文件。
6. `03_by_product_markdown/` 是按产品拆分的 FAQ/话术/SOP Markdown。
7. `04_structured_data/` 是 FAQ/话术/SOP 的 CSV/JSONL 结构化版本。
8. `05_course_catalog/` 是课程货盘的 Markdown、TXT、CSV、JSONL 版本。
9. `06_qa_pairs/` 是 QA 对的 Markdown、TXT、CSV、JSONL 版本。

## 当前覆盖范围

- FAQ 与销售话术：311 条清洗记录
- 1天2次群发 SOP：98 条清洗记录
- 课程货盘/产品事实：21 条课程或商品记录
- QA 对：由 FAQ、话术、SOP、课程货盘抽取生成
- 内容范围：自然拼读、剑桥英语、学科、英语、数学/思维、通用问题、群发 SOP、课程货盘

## 当前不包含

- 图片/视频素材本身
- 本地向量索引或数据库
- 未在源文件中明确出现的字段

涉及实时价格、权益、售后、排期时，建议以最新活动页、班主任通知或后台为准。
