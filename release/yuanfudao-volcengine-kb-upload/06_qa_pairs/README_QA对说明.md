# 猿辅导 QA 对清洗版

共生成 466 条 QA 对，来源包括 FAQ、销售话术、1天2次群发 SOP、课程货盘。

## 文件说明

- `yuanfudao_qa_pairs_ready.md`：推荐上传知识库的 Markdown 版本。
- `yuanfudao_qa_pairs_for_kb.txt`：纯文本导入版。
- `yuanfudao_qa_pairs.csv`：CSV 结构化版本。
- `yuanfudao_qa_pairs.jsonl`：JSONL 结构化版本。

## 生成原则

- FAQ 直接使用原 question/answer。
- 销售话术按产品和场景生成问题，答案保留话术正文。
- SOP 按产品、天数、群发序号生成问题，答案包含发送时间、触发条件、群发内容和报名动作。
- 课程货盘按 SKU 生成产品事实问答，并额外生成价格、适用人群问答。
- 不编造源文件没有明确写出的事实。
