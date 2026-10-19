// Individual contribution statement (submission item 7). Names and roles in [brackets] are for the group to fill in.
const path = require("path");
const L = require("./lib");
const { p, h, table, makeDoc, save, setBodySize, AlignmentType } = L;

setBodySize(24);
const W = 9026;
const children = [
  h("Individual Contribution Statement", 0),
  p("IPL Phase-Performance and Style-Drift Data Warehouse  |  Data Wrangling group project, B.Tech CSE (Data Science), Semester V, NMIMS MPSTME", { align: AlignmentType.CENTER, after: 240 }),
  table([
    ["Member", "Roll no.", "Primary responsibility"],
    ["Sanjeet Singh Tuteja", "L076", "Data extraction, cleaning and the cleaning log, warehouse loading and the validation gates (guidelines 4.1, 4.2, 4.4)"],
    ["[Member 2 name]", "[Roll no.]", "Data transformation and feature engineering (aggregate facts, phase index, SCD Type 2 player profile) and the insights analysis (4.3, 4.5)"],
    ["[Member 3 name]", "[Roll no.]", "Machine-learning models and evaluation, the Power BI dashboard, and the written report (4.6, 4.7)"],
  ], [2600, 1300, W - 3900], { size: 22 }),
  p("", { after: 200 }),
  p("We confirm that the statement above is an accurate description of each member's primary responsibility, and that all three members reviewed the final notebook, report and dashboard.", { after: 480 }),
  table([
    ["Signature", "Signature", "Signature"],
    ["\n\n", "\n\n", "\n\n"],
    ["Sanjeet Singh Tuteja", "[Member 2 name]", "[Member 3 name]"],
  ], [3009, 3009, 3008], { size: 22, header: false }),
  p("Date: ____________________", { before: 240 }),
];

save(makeDoc(children, { title: "Individual Contribution Statement" }), path.join(L.ROOT, "submission", "07_Contribution_Statement.docx"));
