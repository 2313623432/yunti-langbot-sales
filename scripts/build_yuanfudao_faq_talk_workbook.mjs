import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const outputDir = path.resolve(repoRoot, "outputs", "yuanfudao-faq-talk-cleaning");

const readJson = async (name) => JSON.parse(await fs.readFile(path.join(outputDir, name), "utf8"));
const clamp = (value, max = 2600) => {
  if (value === null || value === undefined) return "";
  const text = String(value);
  return text.length > max ? `${text.slice(0, max)}...` : text;
};

const writeTable = (sheet, headers, rows, tableName) => {
  const matrix = [headers, ...rows.map((row) => headers.map((header) => clamp(row[header])))];
  sheet.getRange("A1").write(matrix);
  const range = sheet.getRangeByIndexes(0, 0, matrix.length, headers.length);
  range.format = {
    font: { name: "Microsoft YaHei", size: 10 },
    alignment: { vertical: "top" },
    wrapText: true,
  };
  sheet.getRangeByIndexes(0, 0, 1, headers.length).format = {
    fill: "#1F4E79",
    font: { bold: true, color: "#FFFFFF", name: "Microsoft YaHei", size: 10 },
    alignment: { horizontal: "center", vertical: "middle" },
    wrapText: true,
  };
  range.format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
  sheet.freezePanes.freezeRows(1);
  try {
    const table = sheet.tables.add(range.address, true, tableName);
    table.style = "TableStyleMedium2";
    table.showFilterButton = true;
  } catch {
    // Keep data usable if the workbook already considers the area table-like.
  }
};

const setWidths = (sheet, widths) => {
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, 1, 1).format.columnWidthPx = width;
  });
};

const summary = await readJson("summary.json");
const faqs = await readJson("standard_faq.json");
const scripts = await readJson("talk_scripts.json");
const sopNodes = await readJson("sop_nodes.json");
const keywords = await readJson("intent_keywords.json");

const workbook = Workbook.create();

const overview = workbook.worksheets.add("总览");
overview.showGridLines = false;
overview.getRange("A1:F1").merge();
overview.getRange("A1").values = [["猿辅导 FAQ 与话术清洗审阅包"]];
overview.getRange("A1").format = {
  fill: "#17365D",
  font: { bold: true, color: "#FFFFFF", size: 16, name: "Microsoft YaHei" },
  alignment: { horizontal: "center", vertical: "middle" },
};
overview.getRange("A3:B10").values = [
  ["源目录", summary.source],
  ["标准 FAQ", summary.standard_faq],
  ["话术素材", summary.talk_scripts],
  ["SOP 节点", summary.sop_nodes],
  ["关键词意图", summary.intent_keywords],
  ["本版范围", "不包含产品事实表，只整理 FAQ、跟进话术、SOP 和意图关键词。"],
  ["入库建议", "先确认高风险 FAQ，再筛选 P0/P1 话术；P2 原文摘录暂不直接入主库。"],
  ["风险提示", "涉及价格、赠品、退款、名额、链接、排期的内容需人工确认。"],
];
overview.getRange("A3:A10").format = {
  fill: "#D9EAF7",
  font: { bold: true, name: "Microsoft YaHei" },
};
overview.getRange("B3:B10").format = { font: { name: "Microsoft YaHei" }, wrapText: true };
overview.getRange("A3:B10").format.borders = { preset: "all", style: "thin", color: "#B7C9D6" };
setWidths(overview, [130, 760]);

const faqSheet = workbook.worksheets.add("标准FAQ");
writeTable(
  faqSheet,
  [
    "category",
    "product",
    "question",
    "similar_questions",
    "answer",
    "answer_style",
    "risk_level",
    "status",
    "source_file",
    "source_sheet",
    "source_row",
  ],
  faqs,
  "StandardFAQ",
);
setWidths(faqSheet, [220, 110, 300, 220, 620, 100, 80, 110, 220, 130, 80]);

const sopSheet = workbook.worksheets.add("SOP节点");
writeTable(
  sopSheet,
  [
    "node",
    "trigger_condition",
    "customer_expression",
    "recommended_action",
    "recommended_script",
    "forbidden_script",
    "decision_standard",
    "keywords",
    "review_status",
    "source_file",
    "source_row",
  ],
  sopNodes,
  "SOPNodes",
);
setWidths(sopSheet, [150, 220, 220, 260, 420, 300, 280, 220, 100, 240, 80]);

const scriptsSheet = workbook.worksheets.add("话术素材");
writeTable(
  scriptsSheet,
  [
    "script_type",
    "stage",
    "customer_intent",
    "trigger_text",
    "recommended_reply",
    "next_action",
    "forbidden",
    "keywords",
    "priority",
    "status",
    "source_file",
    "source_sheet",
    "source_row",
  ],
  scripts,
  "TalkScripts",
);
setWidths(scriptsSheet, [140, 160, 260, 340, 680, 260, 320, 180, 80, 110, 240, 120, 80]);

const keywordSheet = workbook.worksheets.add("关键词意图");
writeTable(
  keywordSheet,
  [
    "keyword",
    "tag_type",
    "meaning",
    "sales_stage",
    "handling_advice",
    "example",
    "priority",
    "source_file",
    "source_row",
  ],
  keywords,
  "IntentKeywords",
);
setWidths(keywordSheet, [120, 220, 340, 180, 420, 220, 80, 240, 80]);

const advice = workbook.worksheets.add("入库建议");
advice.showGridLines = false;
advice.getRange("A1:E1").values = [["对象", "当前数量", "建议入库方式", "优先级", "上线前检查"]];
advice.getRange("A2:E5").values = [
  ["标准FAQ", faqs.length, "一问一答一条知识；补充相似问法", "P0", "确认高风险条目，尤其退款、赠品、包邮、名额"],
  ["SOP节点", sopNodes.length, "一个节点一条知识；用于流程判断和回复约束", "P0", "确认禁忌话术和转人工边界"],
  ["话术素材", scripts.length, "筛选 P0/P1；长段原文先压缩成短句客服口吻", "P1", "去重，删除强催/过度承诺/过时优惠"],
  ["关键词意图", keywords.length, "作为意图识别辅助，不直接当回复内容", "P1", "合并近义词，补充误触发规则"],
];
advice.getRange("A1:E1").format = {
  fill: "#1F4E79",
  font: { bold: true, color: "#FFFFFF", name: "Microsoft YaHei" },
  alignment: { horizontal: "center" },
};
advice.getRange("A1:E5").format = {
  font: { name: "Microsoft YaHei", size: 10 },
  wrapText: true,
};
advice.getRange("A1:E5").format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
setWidths(advice, [140, 90, 360, 90, 420]);

for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange();
  if (used) used.format.autofitRows();
}

await fs.mkdir(outputDir, { recursive: true });
for (const sheetName of ["总览", "标准FAQ", "SOP节点", "入库建议"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(path.join(outputDir, `${sheetName}.png`), new Uint8Array(await preview.arrayBuffer()));
}

const inspect = await workbook.inspect({
  kind: "sheet,table",
  maxChars: 5000,
  tableMaxRows: 3,
  tableMaxCols: 6,
});
console.log(inspect.ndjson);
const errors = await workbook.inspect({
  kind: "match",
  searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A",
  options: { useRegex: true, maxResults: 50 },
  summary: "formula error scan",
});
console.log(errors.ndjson);

const xlsx = await SpreadsheetFile.exportXlsx(workbook);
await xlsx.save(path.join(outputDir, "yuanfudao_faq_talk_review.xlsx"));
