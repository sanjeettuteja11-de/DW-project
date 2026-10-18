// Shared helpers for the written deliverables: plain academic style
// (Times New Roman, black text, bold black headings, plain single-line table borders).
const fs = require("fs");
const path = require("path");
const {
  AlignmentType, BorderStyle, Document, Footer, ImageRun, LevelFormat, Packer, PageNumber,
  Paragraph, Table, TableCell, TableRow, TextRun, WidthType, VerticalAlign, PageBreak,
  TableLayoutType,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const FACTS = JSON.parse(fs.readFileSync(path.join(ROOT, "reports", "facts.json"), "utf8"));
const FONT = "Times New Roman";

let BODY = 22; // half-points (11 pt); builders may change with setBodySize
function setBodySize(halfPoints) { BODY = halfPoints; }

// "**bold**" and "^^italic^^" inline markup -> TextRuns (underscores are left alone for snake_case names)
function runs(text, opts = {}) {
  const out = [];
  const re = /(\*\*[^*]+\*\*|\^\^[^^]+\^\^)/g;
  let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), font: FONT, size: opts.size || BODY, bold: opts.bold, italics: opts.italics }));
    const t = m[0];
    if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), font: FONT, size: opts.size || BODY, bold: true, italics: opts.italics }));
    else out.push(new TextRun({ text: t.slice(2, -2), font: FONT, size: opts.size || BODY, italics: true, bold: opts.bold }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), font: FONT, size: opts.size || BODY, bold: opts.bold, italics: opts.italics }));
  return out;
}

function p(text, opts = {}) {
  return new Paragraph({
    children: runs(text, opts),
    alignment: opts.align || AlignmentType.JUSTIFIED,
    spacing: { after: opts.after ?? 100, before: opts.before ?? 0, line: opts.line || 252 },
    keepNext: opts.keepNext,
    indent: opts.indent,
  });
}

function h(text, level = 1) {
  const size = level === 0 ? 30 : level === 1 ? 26 : 23;
  return new Paragraph({
    children: [new TextRun({ text, font: FONT, size, bold: true })],
    spacing: { before: level === 0 ? 0 : level === 1 ? 200 : 140, after: 80 },
    alignment: level === 0 ? AlignmentType.CENTER : AlignmentType.LEFT,
    keepNext: true,
    outlineLevel: level === 0 ? undefined : level - 1,
  });
}

function bullet(text, level = 0, opts = {}) {
  return new Paragraph({
    children: runs(text, opts),
    numbering: { reference: "bullets", level },
    alignment: AlignmentType.LEFT,
    spacing: { after: opts.after ?? 40, line: opts.line || 252 },
  });
}

function numbered(text, ref = "numbers", opts = {}) {
  return new Paragraph({
    children: runs(text, opts),
    numbering: { reference: ref, level: 0 },
    alignment: AlignmentType.LEFT,
    spacing: { after: opts.after ?? 40, line: opts.line || 252 },
  });
}

const BORDER = { style: BorderStyle.SINGLE, size: 4, color: "000000" };
const BORDERS = { top: BORDER, bottom: BORDER, left: BORDER, right: BORDER };

// rows: array of arrays of strings (first row = header). widths in DXA (1440 = 1 inch).
function table(rows, widths, opts = {}) {
  const size = opts.size || (BODY - 3);
  const total = widths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths: widths,
    layout: TableLayoutType.FIXED,
    rows: rows.map((r, i) => new TableRow({
      tableHeader: i === 0,
      cantSplit: true,
      children: r.map((c, j) => new TableCell({
        borders: BORDERS,
        width: { size: widths[j], type: WidthType.DXA },
        margins: { top: 30, bottom: 30, left: 70, right: 70 },
        verticalAlign: VerticalAlign.TOP,
        children: String(c).split("\n").map((line) => new Paragraph({
          children: runs(line, { size, bold: i === 0 && opts.header !== false }),
          alignment: (opts.align && opts.align[j]) || AlignmentType.LEFT,
          spacing: { after: 0, line: 228 },
        })),
      })),
    })),
  });
}

function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

function image(file, widthInches, opts = {}) {
  const { w, h: hh } = pngSize(file);
  const width = Math.round(widthInches * 96);
  const height = Math.round((width * hh) / w);
  return new Paragraph({
    children: [new ImageRun({ type: "png", data: fs.readFileSync(file), transformation: { width, height },
      altText: { title: opts.title || path.basename(file), description: opts.title || path.basename(file), name: path.basename(file) } })],
    alignment: AlignmentType.CENTER,
    spacing: { before: 60, after: 40 },
    keepNext: true,
  });
}

function caption(text) {
  return new Paragraph({
    children: runs(text, { size: BODY - 3 }),
    alignment: AlignmentType.CENTER,
    spacing: { after: 140 },
  });
}

function pageBreak() { return new Paragraph({ children: [new PageBreak()] }); }

function footer() {
  return new Footer({
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [
        new TextRun({ children: ["Page ", PageNumber.CURRENT, " of ", PageNumber.TOTAL_PAGES], font: FONT, size: 18 }),
      ],
    })],
  });
}

function makeDoc(children, opts = {}) {
  const margin = opts.margin || 1440;
  return new Document({
    creator: opts.creator || "Data Wrangling Group",
    title: opts.title || "",
    styles: { default: { document: { run: { font: FONT, size: BODY } } } },
    numbering: {
      config: [
        { reference: "bullets", levels: [
          { level: 0, format: LevelFormat.BULLET, text: "•", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 240 } } } },
          { level: 1, format: LevelFormat.BULLET, text: "–", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 720, hanging: 240 } } } },
        ] },
        ...["numbers", "numbers2", "numbers3", "numbers4", "numbers5", "numbers6"].map((ref) => ({ reference: ref, levels: [
          { level: 0, format: LevelFormat.DECIMAL, text: "%1.", alignment: AlignmentType.LEFT, style: { paragraph: { indent: { left: 360, hanging: 300 } } } },
        ] })),
      ],
    },
    sections: [{
      properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: margin, bottom: margin, left: margin, right: margin } } },
      footers: { default: footer() },
      children,
    }],
  });
}

async function save(doc, file) {
  fs.mkdirSync(path.dirname(file), { recursive: true });
  fs.writeFileSync(file, await Packer.toBuffer(doc));
  console.log("wrote", path.relative(ROOT, file));
}

const fmt = (n, d = 0) => Number(n).toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });

module.exports = { ROOT, FACTS, FONT, p, h, bullet, numbered, table, image, caption, pageBreak, makeDoc, save, fmt, setBodySize, runs, AlignmentType };
