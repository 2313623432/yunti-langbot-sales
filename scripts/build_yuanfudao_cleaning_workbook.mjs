import fs from "node:fs/promises";
import path from "node:path";
import { fileURLToPath } from "node:url";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, "..");
const outputDir = path.resolve(repoRoot, "outputs", "yuanfudao-kb-cleaning");

const readJson = async (name) => {
  const raw = await fs.readFile(path.join(outputDir, name), "utf8");
  return JSON.parse(raw);
};

const clamp = (value, max = 2500) => {
  if (value === null || value === undefined) return "";
  const text = String(value);
  return text.length > max ? `${text.slice(0, max)}...` : text;
};

const writeTable = (sheet, startCell, headers, rows, tableName) => {
  const matrix = [headers, ...rows.map((row) => headers.map((header) => clamp(row[header])))];
  const start = sheet.getRange(startCell);
  start.write(matrix);
  const rowCount = matrix.length;
  const colCount = headers.length;
  const range = sheet.getRangeByIndexes(0, 0, rowCount, colCount);
  range.format = {
    font: { name: "Microsoft YaHei", size: 10 },
    alignment: { vertical: "top" },
    wrapText: true,
  };
  sheet.getRangeByIndexes(0, 0, 1, colCount).format = {
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
    // Table creation is a convenience for review; keep the sheet usable if styling fails.
  }
};

const setWidths = (sheet, widths) => {
  widths.forEach((width, index) => {
    sheet.getRangeByIndexes(0, index, 1, 1).format.columnWidthPx = width;
  });
};

const documents = await readJson("document_inventory.json");
const products = await readJson("product_facts.json");
const faqs = await readJson("faq_entries.json");
const scripts = await readJson("talk_scripts.json");
const summary = await readJson("summary.json");

const workbook = Workbook.create();

const overview = workbook.worksheets.add("清洗总览");
overview.showGridLines = false;
overview.getRange("A1:F1").merge();
overview.getRange("A1").values = [["猿辅导知识库清洗审阅包"]];
overview.getRange("A1").format = {
  fill: "#17365D",
  font: { bold: true, color: "#FFFFFF", size: 16, name: "Microsoft YaHei" },
  alignment: { horizontal: "center", vertical: "middle" },
};
overview.getRange("A3:B10").values = [
  ["源目录", summary.source],
  ["文件总数", summary.documents],
  ["产品事实", summary.product_facts],
  ["FAQ/问答摘录", summary.faq_entries],
  ["话术/SOP摘录", summary.talk_scripts],
  ["第一轮结论", "产品货盘可作为主事实库底座；FAQ中混有跟进话术；SOP摘录需二次按用户意图归并。"],
  ["上线风险", "价格、赠品、排期、链接统一标记为待人工确认。"],
  ["建议下一步", "先人工确认产品事实，再把FAQ整理为一问一答一条，最后处理话术/SOP。"],
];
overview.getRange("A3:A10").format = {
  fill: "#D9EAF7",
  font: { bold: true, name: "Microsoft YaHei" },
};
overview.getRange("B3:B10").format = {
  font: { name: "Microsoft YaHei" },
  wrapText: true,
};
overview.getRange("A3:B10").format.borders = { preset: "all", style: "thin", color: "#B7C9D6" };
setWidths(overview, [140, 760]);
overview.getRange("A1").format.rowHeightPx = 36;
overview.getRange("A3:A10").format.rowHeightPx = 34;

const fileSheet = workbook.worksheets.add("文件盘点");
writeTable(
  fileSheet,
  "A1",
  ["file_name", "extension", "size_bytes", "category", "recommended_use", "cleaning_priority", "notes"],
  documents,
  "DocumentInventory",
);
setWidths(fileSheet, [330, 70, 90, 110, 160, 100, 360]);

const productSheet = workbook.worksheets.add("产品事实");
writeTable(
  productSheet,
  "A1",
  [
    "product_name",
    "business",
    "price",
    "subject",
    "suitable_grades",
    "schedule",
    "benefits",
    "upsell_price",
    "selling_points",
    "product_intro",
    "link",
    "freshness_status",
    "risk_note",
    "source_file",
    "source_sheet",
    "source_row",
  ],
  products,
  "ProductFacts",
);
setWidths(productSheet, [120, 110, 70, 110, 180, 260, 260, 140, 460, 420, 360, 110, 260, 180, 90, 80]);

const faqSheet = workbook.worksheets.add("FAQ问答摘录");
writeTable(
  faqSheet,
  "A1",
  [
    "category",
    "standard_question",
    "similar_questions",
    "standard_answer",
    "product_name",
    "suitable_grades",
    "risk_level",
    "freshness_status",
    "source_file",
    "source_sheet",
    "source_row",
  ],
  faqs,
  "FAQEntries",
);
setWidths(faqSheet, [120, 260, 180, 560, 120, 130, 80, 110, 210, 100, 80]);

const scriptSheet = workbook.worksheets.add("话术SOP摘录");
writeTable(
  scriptSheet,
  "A1",
  [
    "scenario",
    "user_intent",
    "trigger_text",
    "recommended_reply",
    "follow_up",
    "forbidden",
    "product_name",
    "source_file",
    "source_sheet",
    "source_row",
  ],
  scripts,
  "TalkScripts",
);
setWidths(scriptSheet, [140, 220, 360, 640, 180, 180, 120, 220, 110, 80]);

const ragSheet = workbook.worksheets.add("RAG导入建议");
ragSheet.showGridLines = false;
ragSheet.getRange("A1:D1").values = [["知识类型", "当前数量", "建议切片方式", "上线前动作"]];
ragSheet.getRange("A2:D5").values = [
  ["产品事实", products.length, "一个产品/价格档 = 一条知识", "确认价格、链接、赠品、排期有效性"],
  ["FAQ", faqs.length, "一个标准问题 = 一条知识", "补齐相似问法，删除空问题和重复回答"],
  ["话术/SOP", scripts.length, "一个用户意图或流程节点 = 一条知识", "归并重复话术，补禁忌和转人工规则"],
  ["长文/PDF/素材", documents.filter((item) => item.cleaning_priority === "P2").length, "按章节或素材用途单独入库", "先不要混入主事实库"],
];
ragSheet.getRange("A1:D1").format = {
  fill: "#1F4E79",
  font: { bold: true, color: "#FFFFFF", name: "Microsoft YaHei" },
  alignment: { horizontal: "center" },
};
ragSheet.getRange("A1:D5").format = {
  font: { name: "Microsoft YaHei", size: 10 },
  wrapText: true,
};
ragSheet.getRange("A1:D5").format.borders = { preset: "all", style: "thin", color: "#D9E2F3" };
setWidths(ragSheet, [130, 90, 280, 360]);

for (const sheet of workbook.worksheets.items) {
  const used = sheet.getUsedRange();
  if (used) {
    used.format.autofitRows();
  }
}

await fs.mkdir(outputDir, { recursive: true });

for (const sheetName of ["清洗总览", "产品事实", "FAQ问答摘录", "RAG导入建议"]) {
  const preview = await workbook.render({ sheetName, autoCrop: "all", scale: 1, format: "png" });
  await fs.writeFile(
    path.join(outputDir, `${sheetName}.png`),
    new Uint8Array(await preview.arrayBuffer()),
  );
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
await xlsx.save(path.join(outputDir, "yuanfudao_kb_cleaning_review.xlsx"));
