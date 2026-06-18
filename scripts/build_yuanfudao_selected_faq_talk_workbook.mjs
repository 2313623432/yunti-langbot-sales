import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const outputDir = path.resolve(repoRoot, "outputs", "yuanfudao-selected-faq-talk-cleaning");

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
  if (rows.length > 0) {
    try {
      const table = sheet.tables.add(range.address, true, tableName);
      table.style = "TableStyleMedium2";
      table.showFilterButton = true;
    } catch {
      // The rendered workbook remains usable even if table creation is skipped.
    }
  }
};

const setWidths = (sheet, widths) => {
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, 1, 1).format.columnWidthPx = width;
  });
};

const summary = await readJson("summary.json");
const sources = await readJson("source_inventory.json");
const sections = await readJson("markdown_sections.json");
const faqs = await readJson("standard_faq.json");
const scripts = await readJson("talk_scripts.json");

const workbook = Workbook.create();

const overview = workbook.worksheets.add("总览");
overview.showGridLines = false;
overview.getRange("A1:F1").merge();
overview.getRange("A1").values = [["猿辅导单独话术 FAQ 文件整合审阅包"]];
overview.getRange("A1").format = {
  fill: "#17365D",
  font: { bold: true, color: "#FFFFFF", size: 16, name: "Microsoft YaHei" },
  alignment: { horizontal: "center", vertical: "middle" },
};
overview.getRange("A3:B12").values = [
  ["源文件数量", summary.source_files],
  ["Markdown 章节", summary.markdown_sections],
  ["标准 FAQ / FAQ 候选", summary.standard_faq],
  ["话术素材", summary.talk_scripts],
  ["结构化 SOP 节点", summary.sop_nodes],
  ["关键词意图", summary.intent_keywords],
  ["本版范围", "仅整合用户本次单独拉出的 10 个话术/FAQ 文件；产品事实表暂不纳入。"],
  ["可用判断", "可以作为 FAQ 与话术清洗底稿；其中 Markdown 抽取的 FAQ 已标记为候选，需人工复核。"],
  ["入库建议", "优先处理标准FAQ表中的课程问答；再筛选 P0/P1 话术；长段培训原文先压缩为客服短句。"],
  ["风险提示", "价格、赠品、退款、包邮、名额、链接、排期等内容上线前必须人工确认。"],
];
overview.getRange("A3:A12").format = {
  fill: "#D9EAF7",
  font: { bold: true, name: "Microsoft YaHei" },
};
overview.getRange("B3:B12").format = { font: { name: "Microsoft YaHei" }, wrapText: true };
overview.getRange("A3:B12").format.borders = { preset: "all", style: "thin", color: "#B7C9D6" };
setWidths(overview, [160, 820]);

const inventorySheet = workbook.worksheets.add("文件盘点");
writeTable(
  inventorySheet,
  ["file_name", "extension", "source_type", "size_bytes", "extraction_note", "full_path"],
  sources,
  "SourceInventory",
);
setWidths(inventorySheet, [260, 80, 120, 110, 260, 760]);

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
  "SelectedStandardFAQ",
);
setWidths(faqSheet, [210, 110, 320, 220, 640, 100, 80, 110, 240, 130, 80]);

const sectionSheet = workbook.worksheets.add("Markdown章节");
writeTable(
  sectionSheet,
  [
    "source_file",
    "section_title",
    "product",
    "section_type",
    "content",
    "suggested_use",
    "priority",
    "status",
    "source_line",
  ],
  sections,
  "MarkdownSections",
);
setWidths(sectionSheet, [240, 260, 110, 130, 700, 220, 80, 110, 80]);

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
  "SelectedTalkScripts",
);
setWidths(scriptsSheet, [140, 220, 180, 280, 720, 260, 330, 180, 80, 110, 240, 120, 80]);

const advice = workbook.worksheets.add("入库建议");
advice.showGridLines = false;
advice.getRange("A1:E1").values = [["对象", "当前数量", "建议入库方式", "优先级", "上线前检查"]];
advice.getRange("A2:E6").values = [
  ["标准FAQ", faqs.length, "一问一答一条知识；保留相似问法；高风险答案先锁定口径", "P0", "确认退款、价格、赠品、名额、包邮、链接、排期"],
  ["Markdown FAQ候选", faqs.filter((item) => String(item.category).includes("Markdown候选")).length, "只作为候选；人工改写成明确问题和短答案后再入库", "P0/P1", "删除营销标题式问题，补足真实用户问法"],
  ["话术素材", scripts.length, "筛选 P0/P1；长段话术压缩成客服可直接发送的 2-4 句", "P1", "去重，删除强催促、过度承诺、过时优惠"],
  ["Markdown章节", sections.length, "作为原文追溯和整理素材，不建议整段直接入主库", "P2", "拆成 FAQ、异议处理、跟进动作后再入库"],
  ["结构化SOP/关键词", 0, "本批文件未抽到结构化 SOP 节点或关键词表", "暂缓", "如需要流程库，建议另补 SOP 表或人工从话术中归纳"],
];
advice.getRange("A1:E1").format = {
  fill: "#1F4E79",
  font: { bold: true, color: "#FFFFFF", name: "Microsoft YaHei" },
  alignment: { horizontal: "center" },
};
advice.getRange("A1:E6").format = {
  font: { name: "Microsoft YaHei", size: 10 },
  wrapText: true,
};
advice.getRange("A1:E6").format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
setWidths(advice, [150, 90, 420, 90, 460]);

for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange();
  if (used) used.format.autofitRows();
}

await fs.mkdir(outputDir, { recursive: true });
const previewRanges = {
  "总览": "A1:B12",
  "文件盘点": "A1:F12",
  "标准FAQ": "A1:K40",
  "Markdown章节": "A1:I40",
  "话术素材": "A1:M40",
  "入库建议": "A1:E6",
};
for (const [sheetName, range] of Object.entries(previewRanges)) {
  const preview = await workbook.render({ sheetName, range, autoCrop: "all", scale: 1, format: "png" });
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
await xlsx.save(path.join(outputDir, "yuanfudao_selected_faq_talk_review.xlsx"));
