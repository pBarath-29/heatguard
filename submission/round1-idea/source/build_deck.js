const pptxgen = require("pptxgenjs");
const React = require("react");
const ReactDOMServer = require("react-dom/server");
const sharp = require("sharp");
const fa = require("react-icons/fa");

const OUT = process.argv[2] || "HeatGuard.pptx";

// Palette: template identity (DAISI red, navy, slate) + heat-band colours
const C = {
  red: "FF3621", navy: "112530", slate: "6B7A84", ink: "22323C",
  tint: "F3F5F7", line: "DDE2E6", white: "FFFFFF",
  high: "E5391F", mod: "F2A516", low: "2E9E6B", paleRed: "FFE9E5",
};
const FONT = "Arial";
const W = 13.333, M = 0.6;

async function icon(Comp, color, size = 256) {
  const svg = ReactDOMServer.renderToStaticMarkup(
    React.createElement(Comp, { color: "#" + color, size: String(size) })
  );
  const buf = await sharp(Buffer.from(svg)).png().toBuffer();
  return "image/png;base64," + buf.toString("base64");
}

function header(pres, slide, n, title) {
  // Template elements: red top strip, SLIDE N label, title
  slide.background = { color: C.white };
  slide.addShape(pres.shapes.RECTANGLE, { x: 0, y: 0, w: W, h: 0.16, fill: { color: C.red }, line: { color: C.red } });
  slide.addText(`SLIDE ${n}`, { x: M, y: 0.4, w: 3, h: 0.3, fontFace: FONT, fontSize: 13, bold: true, color: C.red, margin: 0, isTextBox: true });
  slide.addText(title, { x: M, y: 0.7, w: 9.2, h: 0.6, fontFace: FONT, fontSize: 30, bold: true, color: C.navy, margin: 0, isTextBox: true });
  // Product tag, top right
  slide.addText([
    { text: "HeatGuard", options: { bold: true, color: C.navy } },
    { text: "  ·  B1", options: { color: C.slate } },
  ], { x: W - M - 3, y: 0.78, w: 3, h: 0.4, fontFace: FONT, fontSize: 14, align: "right", margin: 0, isTextBox: true });
}

function footer(slide, sources, page) {
  slide.addText(sources, { x: M, y: 7.0, w: 10.6, h: 0.3, fontFace: FONT, fontSize: 8, color: C.slate, margin: 0, valign: "top", isTextBox: true });
  slide.addText(`DAISI Challenge Singapore 2026  ·  ${page}/3`, { x: W - M - 3, y: 7.0, w: 3, h: 0.3, fontFace: FONT, fontSize: 8, color: C.slate, align: "right", margin: 0, valign: "top", isTextBox: true });
}

function label(slide, text, x, y, w, color = C.red) {
  slide.addText(text, { x, y, w, h: 0.26, fontFace: FONT, fontSize: 11, bold: true, color, charSpacing: 1.5, margin: 0, isTextBox: true });
}

function bullets(items, size = 13, color = C.ink) {
  return items.map((it, i) => {
    const runs = Array.isArray(it) ? it : [{ text: it }];
    return runs.map((r, j) => ({
      text: r.text,
      options: {
        fontFace: FONT, fontSize: size, color: r.color || color, bold: !!r.bold,
        bullet: j === 0 ? { indent: 14 } : undefined,
        paraSpaceAfter: 5,
        breakLine: j === runs.length - 1 && i < items.length - 1,
      },
    }));
  }).flat();
}

(async () => {
  const pres = new pptxgen();
  pres.layout = "LAYOUT_WIDE";
  pres.title = "HeatGuard — DAISI Round 1";

  const I = {
    user: await icon(fa.FaUserFriends, C.white),
    walk: await icon(fa.FaWalking, C.white),
    build: await icon(fa.FaBuilding, C.white),
    cloud: await icon(fa.FaSatelliteDish, C.white),
    down: await icon(fa.FaFileImport, C.white),
    layers: await icon(fa.FaLayerGroup, C.white),
    brain: await icon(fa.FaChartLine, C.white),
    screen: await icon(fa.FaClipboardList, C.white),
    list: await icon(fa.FaListOl, C.white),
    clock: await icon(fa.FaClock, C.white),
    check: await icon(fa.FaSearch, C.white),
    shield: await icon(fa.FaShieldAlt, C.navy),
  };

  // ───────────────────────── SLIDE 1 ─────────────────────────
  {
    const s = pres.addSlide();
    header(pres, s, 1, "Problem & why it matters");

    // Team / problem statement chips
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 1.5, w: 3.1, h: 0.46, fill: { color: C.tint }, line: { color: C.tint }, rectRadius: 0.08 });
    s.addText([
      { text: "TEAM  ", options: { bold: true, color: C.red, fontSize: 10, charSpacing: 1.5 } },
      { text: "Knock Before Noon", options: { bold: true, color: C.navy, fontSize: 13 } },
    ], { x: M + 0.15, y: 1.5, w: 2.9, h: 0.46, fontFace: FONT, valign: "middle", margin: 0, isTextBox: true });
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M + 3.3, y: 1.5, w: 8.83, h: 0.46, fill: { color: C.tint }, line: { color: C.tint }, rectRadius: 0.08 });
    s.addText([
      { text: "PROBLEM STATEMENT  ", options: { bold: true, color: C.red, fontSize: 10, charSpacing: 1.5 } },
      { text: "B1 — HeatGuard: Urban heat risk mapping for vulnerable communities", options: { bold: true, color: C.navy, fontSize: 13 } },
    ], { x: M + 3.45, y: 1.5, w: 8.6, h: 0.46, fontFace: FONT, valign: "middle", margin: 0, isTextBox: true });

    const LX = M, LW = 7.55;
    label(s, "THE PROBLEM IN ONE SENTENCE", LX, 2.25, LW);
    s.addText(
      "Singapore’s heat is getting more dangerous for the seniors least able to cope, but today’s advisories say how hot it will be, not who needs a check-in, so outreach teams react during the heat instead of before it.",
      { x: LX, y: 2.55, w: LW, h: 1.2, fontFace: FONT, fontSize: 17, bold: true, color: C.navy, margin: 0, valign: "top", isTextBox: true }
    );

    label(s, "WHO IS AFFECTED, AND HOW BADLY", LX, 3.9, LW);
    s.addText(bullets([
      [{ text: "Seniors living alone: ", bold: true }, { text: "87,200 one-person households aged 65+ in 2024, double the 42,100 of 2014." }],
      [{ text: "Seniors in 1–2-room flats or with mobility limits: ", bold: true }, { text: "least able to cool down or reach help (Census 2020 tables)." }],
      [{ text: "Eldercare outreach teams: ", bold: true }, { text: "no early warning of which areas to prioritise." }],
    ], 12.5), { x: LX, y: 4.2, w: LW, h: 1.35, valign: "top", margin: 0, isTextBox: true });

    label(s, "WHY IT MATTERS NOW", LX, 5.6, LW);
    s.addText(bullets([
      [{ text: "2025 was Singapore’s hottest year on record; " }, { text: "heat-illness ED cases rose 42%", bold: true }, { text: " (280 → 398)." }],
      [{ text: "2026 is the " }, { text: "Year of Climate Adaptation", bold: true }, { text: " and the year Singapore turns super-aged; a S$40m heat-resilience programme names the elderly a priority." }],
    ], 12.5), { x: LX, y: 5.9, w: LW, h: 1.0, valign: "top", margin: 0, isTextBox: true });

    // Stat cards
    const RX = 8.55, RW = W - M - RX;
    const stats = [
      { n: "87,200", l: "seniors aged 65+ living alone (2024)", sub: "2× in ten years", c: C.navy },
      { n: "+42%", l: "heat-illness ED cases, 2024 → 2025", sub: "280 → 398 cases", c: C.red },
      { n: "1 in 5", l: "residents aged 65+ in 2026", sub: "Singapore becomes super-aged", c: C.navy },
    ];
    stats.forEach((st, i) => {
      const y = 2.25 + i * 1.58;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: RX, y, w: RW, h: 1.4, fill: { color: C.tint }, line: { color: C.tint }, rectRadius: 0.1 });
      s.addText(st.n, { x: RX + 0.3, y: y + 0.12, w: RW - 0.5, h: 0.7, fontFace: FONT, fontSize: 36, bold: true, color: st.c, margin: 0, valign: "middle", isTextBox: true });
      s.addText(st.l, { x: RX + 0.3, y: y + 0.8, w: RW - 0.5, h: 0.28, fontFace: FONT, fontSize: 12, bold: true, color: C.ink, margin: 0, isTextBox: true });
      s.addText(st.sub, { x: RX + 0.3, y: y + 1.06, w: RW - 0.5, h: 0.26, fontFace: FONT, fontSize: 10.5, color: C.slate, margin: 0, isTextBox: true });
    });

    footer(s, "Sources: MOH parliamentary reply (Jan 2026), seniors living alone; MOH via The Straits Times (2026), heat-illness ED cases; MSE Year of Climate Adaptation 2026; DAISI problem brief B1.", 1);
    s.addNotes("Heat is now a health risk for the people Singapore is ageing into: seniors living alone, in small rental flats, with limited mobility. NEA already publishes live heat-stress readings, but nothing links that hazard to who is vulnerable, so outreach happens after the heat, not before it.");
  }

  // ───────────────────────── SLIDE 2 ─────────────────────────
  {
    const s = pres.addSlide();
    header(pres, s, 2, "Solution & data");

    // Solution band
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: 1.45, w: W - 2 * M, h: 0.98, fill: { color: C.navy }, line: { color: C.navy }, rectRadius: 0.1 });
    s.addText("OUR SOLUTION IN ONE SENTENCE", { x: M + 0.3, y: 1.55, w: 6, h: 0.26, fontFace: FONT, fontSize: 10.5, bold: true, color: "FF8A78", charSpacing: 1.5, margin: 0, isTextBox: true });
    s.addText("Every afternoon, HeatGuard forecasts tomorrow’s heat stress for each of Singapore’s ~330 subzones, combines it with who lives there, and tells outreach teams where to check on seniors first, and why.",
      { x: M + 0.3, y: 1.83, w: W - 2 * M - 0.6, h: 0.52, fontFace: FONT, fontSize: 15, bold: true, color: C.white, margin: 0, valign: "top", isTextBox: true });

    // Left: users → decisions
    const LX = M, LW = 6.3;
    label(s, "WHO USES IT, AND WHAT DECISION IT CHANGES", LX, 2.62, LW);
    const users = [
      { ic: I.user, who: "Active Ageing Centre coordinators", what: "which clients to call first, before tomorrow’s peak heat" },
      { ic: I.walk, who: "Silver Generation Office ambassadors", what: "which neighbourhoods get door-knock rounds" },
      { ic: I.build, who: "Community Clubs (People’s Association)", what: "where to open as a cool rest spot, and when" },
    ];
    users.forEach((u, i) => {
      const y = 2.93 + i * 0.44;
      s.addShape(pres.shapes.OVAL, { x: LX, y: y + 0.03, w: 0.36, h: 0.36, fill: { color: C.red }, line: { color: C.red } });
      s.addImage({ data: u.ic, x: LX + 0.08, y: y + 0.11, w: 0.2, h: 0.2 });
      s.addText([
        { text: u.who, options: { bold: true, color: C.navy } },
        { text: "  →  " + u.what, options: { color: C.ink } },
      ], { x: LX + 0.48, y, w: LW - 0.48, h: 0.42, fontFace: FONT, fontSize: 11, valign: "middle", margin: 0, isTextBox: true });
    });
    s.addText("HeatGuard says where and when; each team’s own client list says who. No personal data is used.",
      { x: LX, y: 4.28, w: LW, h: 0.24, fontFace: FONT, fontSize: 10, italic: true, color: C.slate, margin: 0, isTextBox: true });

    label(s, "DATASETS WE WILL USE  (all on data.gov.sg)", LX, 4.62, LW);
    const ds = [
      ["Heat stress (WBGT) observations", "NEA · live API · 30 stations, every 15 min, since Feb 2025", "Heat now + what we predict"],
      ["Air temperature & relative humidity", "NEA · live API + yearly files 2016–2024", "More hot seasons to learn from"],
      ["24-hour forecast & 4-day outlook", "NEA · live API + archives", "What NEA expects tomorrow"],
      ["Census 2020: seniors 65+, flat type, living alone, mobility", "SingStat · by subzone or planning area", "Who lives there? How vulnerable?"],
      ["Subzone map + Community Clubs & public libraries", "URA · People’s Association · NLB", "Nearest air-conditioned space?"],
    ];
    const rows = [[
      { text: "", options: {} },
      { text: "Dataset", options: { bold: true, color: C.slate } },
      { text: "Question it answers", options: { bold: true, color: C.slate } },
    ]].concat(ds.map((d, i) => [
      { text: String(i + 1), options: { bold: true, color: C.red, align: "center" } },
      { text: [
        { text: d[0], options: { bold: true, color: C.navy, breakLine: true } },
        { text: d[1], options: { color: C.slate, fontSize: 8.5 } },
      ] },
      { text: d[2], options: { color: C.ink, italic: true } },
    ]));
    s.addTable(rows, {
      x: LX, y: 4.9, w: LW, colW: [0.3, 3.75, 2.25],
      fontFace: FONT, fontSize: 9.5, valign: "middle", margin: [1, 4, 1, 4],
      border: { type: "solid", pt: 0.75, color: C.line }, rowH: [0.22, 0.33, 0.33, 0.33, 0.33, 0.33],
      fill: { color: C.white },
    });

    // Right: differentiators
    const RX = 7.25, RW = W - M - RX;
    label(s, "DIFFERENT FROM A GENERIC DASHBOARD", RX, 2.62, RW);
    const diffs = [
      { ic: I.list, t: "An action list, not just a map", b: "Ranked subzones, each with a reason and a suggested next step." },
      { ic: I.clock, t: "Tomorrow, not today", b: "Next-day heat-stress forecast, scored vs. a “same as today” baseline." },
      { ic: I.check, t: "Honest about the data", b: "We checked every dataset (e.g. 16 temperature stations, not ~50) and show which inputs are estimates." },
    ];
    let dy = 2.93;
    diffs.forEach((d, i) => {
      const h = i === 2 ? 0.74 : 0.56;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: RX, y: dy, w: RW, h, fill: { color: C.tint }, line: { color: C.tint }, rectRadius: 0.08 });
      s.addShape(pres.shapes.OVAL, { x: RX + 0.15, y: dy + 0.1, w: 0.36, h: 0.36, fill: { color: C.navy }, line: { color: C.navy } });
      s.addImage({ data: d.ic, x: RX + 0.24, y: dy + 0.19, w: 0.18, h: 0.18 });
      s.addText([
        { text: d.t, options: { bold: true, color: C.navy, fontSize: 12, breakLine: true } },
        { text: d.b, options: { color: C.ink, fontSize: 10.5 } },
      ], { x: RX + 0.65, y: dy + 0.06, w: RW - 0.8, h: h - 0.12, fontFace: FONT, valign: "top", margin: 0, isTextBox: true });
      dy += h + 0.1;
    });

    // Example check-in list
    const ry = dy + 0.04;
    s.addText([
      { text: "Tomorrow’s check-in list", options: { bold: true, color: C.navy } },
      { text: "   illustrative example, not real output", options: { italic: true, color: C.slate, fontSize: 9 } },
    ], { x: RX, y: ry, w: RW, h: 0.26, fontFace: FONT, fontSize: 11.5, margin: 0, isTextBox: true });
    const pill = (t, c) => ({ text: t, options: { bold: true, color: C.white, fill: { color: c }, align: "center", fontSize: 8 } });
    const hd = (t, a) => ({ text: t, options: { bold: true, color: C.slate, align: a || "left" } });
    const roster = [
      [hd("#"), hd("Subzone"), hd("2–4 pm", "center"), hd("Why"), hd("Suggested action")],
      ["1", "Bedok North", pill("HIGH", C.high), "Many seniors 65+ · many live alone", "Call clients who live alone by 11 am"],
      ["2", "Toa Payoh Central", pill("HIGH", C.high), "Many 1–2-room rental flats", "Door-knock rental blocks; share CC hours"],
      ["3", "Jurong West Central", pill("MODERATE", C.mod), "Nearest air-con space over 1 km", "Offer escort to nearest CC or library"],
    ].map(r => r.map(c => typeof c === "string" ? { text: c, options: { color: C.ink } } : c));
    s.addTable(roster, {
      x: RX, y: ry + 0.28, w: RW, colW: [0.22, 1.0, 0.78, 1.63, RW - 3.63],
      fontFace: FONT, fontSize: 8.5, valign: "middle", margin: [1, 3, 1, 3], rowH: [0.22, 0.33, 0.33, 0.33],
      border: { type: "solid", pt: 0.5, color: C.line }, fill: { color: C.white },
    });
    s.addText("Rank = tomorrow’s heat band × how vulnerable the area is. Actions come from a fixed rulebook, not AI.",
      { x: RX, y: ry + 1.55, w: RW, h: 0.2, fontFace: FONT, fontSize: 8.5, italic: true, color: C.slate, margin: 0, isTextBox: true });

    footer(s, "Risk bands reuse NEA’s own Low / Moderate / High heat-stress categories. All datasets are open data from data.gov.sg.", 2);
    s.addNotes("How the list is built: (1) a model trained on NEA heat-stress, temperature and humidity history plus NEA's own forecast predicts tomorrow's afternoon heat stress at each station; (2) each subzone takes a distance-weighted average of nearby stations and is put in NEA's Low/Moderate/High band; (3) a vulnerability score per subzone uses Census 2020: seniors 65+ and 1-2-room flats by subzone, one-person households and members with daily-activity difficulty by planning area, plus distance to the nearest air-conditioned Community Club or library; (4) rank = heat band x vulnerability; (5) the top reason maps to an action through a fixed rulebook. The list is area-level only; coordinators apply it to their own client lists. Limits we state openly: Census 2020 is six years old, the living-alone and mobility tables are for all ages and only by planning area, and only 30 stations measure heat stress.");
  }

  // ───────────────────────── SLIDE 3 ─────────────────────────
  {
    const s = pres.addSlide();
    header(pres, s, 3, "Databricks architecture & impact");

    label(s, "PIPELINE:  SOURCE → INGESTION → TRANSFORM → MODEL / ANALYTICS → OUTPUT", M, 1.45, 10);
    const stages = [
      { ic: I.cloud, n: "SOURCE", t: "data.gov.sg", b: [["Live APIs: ", "heat stress, temperature, humidity, NEA forecasts"], ["Files: ", "Census 2020, subzone map, CCs, libraries"]] },
      { ic: I.down, n: "INGEST", t: "Lakeflow Jobs + Auto Loader", b: [["", "Job pulls live readings every 15 min into a "], ["Unity Catalog Volume", ""], ["", " → bronze Delta tables"]] },
      { ic: I.layers, n: "TRANSFORM", t: "Lakeflow Declarative Pipeline", b: [["Quality checks", " (missing, duplicate, impossible readings); "], ["Spatial SQL + H3:", " stations → subzones, distance to nearest CC / library"]] },
      { ic: I.brain, n: "MODEL", t: "MLflow", b: [["", "① Tomorrow’s heat stress per station"], ["", "② Vulnerability score per subzone"], ["", "③ Priority = heat × vulnerability"]] },
      { ic: I.screen, n: "OUTPUT", t: "AI/BI + Genie", b: [["3-tab dashboard", " for coordinators; "], ["Genie", " answers plain-English questions; "], ["Foundation Model API", " drafts advisories"]] },
    ];
    const bw = 2.2, gap = 0.283, by = 1.78, bh = 2.05;
    stages.forEach((st, i) => {
      const x = M + i * (bw + gap);
      const dark = i === 3;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x, y: by, w: bw, h: bh, fill: { color: dark ? C.navy : C.tint }, line: { color: dark ? C.navy : C.tint }, rectRadius: 0.1 });
      s.addShape(pres.shapes.OVAL, { x: x + 0.15, y: by + 0.13, w: 0.38, h: 0.38, fill: { color: C.red }, line: { color: C.red } });
      s.addImage({ data: st.ic, x: x + 0.245, y: by + 0.225, w: 0.19, h: 0.19 });
      s.addText(`${i + 1}  ${st.n}`, { x: x + 0.63, y: by + 0.17, w: bw - 0.7, h: 0.3, fontFace: FONT, fontSize: 10, bold: true, charSpacing: 1.5, color: dark ? "FF8A78" : C.red, margin: 0, valign: "middle", isTextBox: true });
      s.addText(st.t, { x: x + 0.15, y: by + 0.6, w: bw - 0.3, h: 0.42, fontFace: FONT, fontSize: 12, bold: true, color: dark ? C.white : C.navy, margin: 0, valign: "top", isTextBox: true });
      const runs = [];
      const lineMode = i === 0 || i === 3;
      st.b.forEach(([bold, rest], k) => {
        if (bold) runs.push({ text: bold, options: { bold: true } });
        if (rest) runs.push({ text: rest, options: {} });
        if (lineMode && k < st.b.length - 1) runs[runs.length - 1].options.breakLine = true;
      });
      s.addText(runs, { x: x + 0.15, y: by + 1.02, w: bw - 0.3, h: bh - 1.08, fontFace: FONT, fontSize: 9.5, color: dark ? "DCE3E8" : C.ink, margin: 0, valign: "top", paraSpaceAfter: 2, isTextBox: true });
      if (i < stages.length - 1) {
        s.addShape(pres.shapes.ISOSCELES_TRIANGLE, { x: x + bw + 0.07, y: by + bh / 2 - 0.1, w: 0.15, h: 0.2, rotate: 90, fill: { color: C.red }, line: { color: C.red } });
      }
    });

    // Governance band
    const gy = by + bh + 0.13;
    s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: M, y: gy, w: W - 2 * M, h: 0.4, fill: { color: C.paleRed }, line: { color: C.paleRed }, rectRadius: 0.08 });
    s.addImage({ data: I.shield, x: M + 0.18, y: gy + 0.09, w: 0.22, h: 0.22 });
    s.addText([
      { text: "Unity Catalog governance:  ", options: { bold: true, color: C.navy } },
      { text: "lineage from raw API to final list · area-level data only, no personal data · every source and known gap documented", options: { color: C.ink } },
    ], { x: M + 0.55, y: gy, w: W - 2 * M - 0.7, h: 0.4, fontFace: FONT, fontSize: 10.5, valign: "middle", margin: 0, isTextBox: true });

    // Bottom: dashboard | impact | plan
    const cy = gy + 0.58;
    const w0 = 4.6, w1 = 3.45, w2 = W - 2 * M - w0 - w1 - 0.6;
    const x0 = M, x1 = x0 + w0 + 0.3, x2 = x1 + w1 + 0.3;

    label(s, "THE DASHBOARD WE WILL DEMO", x0, cy, w0);
    const tabs = [
      ["NOW", "Live heat stress at 30 stations in NEA’s Low / Moderate / High bands, refreshed every 15 min."],
      ["TOMORROW", "Subzone risk map + the ranked check-in list, with a reason and a suggested action per area."],
      ["WHY HERE?", "Click an area: what drove its rank, its nearest CC or library, and past forecast accuracy."],
    ];
    tabs.forEach(([t, d], i) => {
      const y = cy + 0.32 + i * 0.52;
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x0, y, w: w0, h: 0.46, fill: { color: C.tint }, line: { color: C.tint }, rectRadius: 0.06 });
      s.addShape(pres.shapes.ROUNDED_RECTANGLE, { x: x0 + 0.1, y: y + 0.11, w: 0.95, h: 0.24, fill: { color: i === 1 ? C.red : C.navy }, line: { color: i === 1 ? C.red : C.navy }, rectRadius: 0.05 });
      s.addText(t, { x: x0 + 0.1, y: y + 0.11, w: 0.95, h: 0.24, fontFace: FONT, fontSize: 8.5, bold: true, color: C.white, align: "center", valign: "middle", margin: 0, isTextBox: true });
      s.addText(d, { x: x0 + 1.15, y, w: w0 - 1.25, h: 0.46, fontFace: FONT, fontSize: 9.5, color: C.ink, valign: "middle", margin: 0, isTextBox: true });
    });
    s.addText([
      { text: "Plus: ", options: { bold: true, color: C.navy } },
      { text: "ask Genie “Which High subzones in Bedok are over 1 km from a CC?” and get advisory text in one click.", options: { color: C.ink } },
    ], { x: x0, y: cy + 1.9, w: w0, h: 0.4, fontFace: FONT, fontSize: 9.5, valign: "top", margin: 0, isTextBox: true });

    label(s, "MEASURABLE IMPACT IF IT WORKED", x1, cy, w1);
    s.addText(bullets([
      [{ text: "~24 h lead time: ", bold: true }, { text: "outreach planned the day before, not during the heat." }],
      [{ text: "Focus: ", bold: true }, { text: "the top ~20 of ~330 subzones where high heat meets vulnerable seniors." }],
      [{ text: "Honest accuracy: ", bold: true }, { text: "forecast error vs. “same as today”, tracked in MLflow." }],
      [{ text: "Outcome to track: ", bold: true }, { text: "heat-illness ED cases (398 in 2025)." }],
    ], 10), { x: x1, y: cy + 0.32, w: w1, h: 2.0, valign: "top", margin: 0, isTextBox: true });

    label(s, "TWO-WEEK SPRINT PLAN", x2, cy, w2);
    const plan = [
      ["Days 1–2", "Ingestion + history backfill"],
      ["Days 3–5", "Pipeline, subzone mapping, vulnerability score"],
      ["Days 6–9", "Forecast model + baseline in MLflow"],
      ["Days 10–12", "Dashboard, Genie, advisories, governance"],
      ["Days 13–14", "End-to-end test, backup recording, pitch"],
    ];
    s.addTable(plan.map(([d, t]) => [
      { text: d, options: { bold: true, color: C.red } },
      { text: t, options: { color: C.ink } },
    ]), {
      x: x2, y: cy + 0.32, w: w2, colW: [0.9, w2 - 0.9],
      fontFace: FONT, fontSize: 9.5, valign: "middle", margin: [1, 4, 1, 0], rowH: 0.36,
      border: { type: "none" },
    });

    footer(s, "Built on Databricks Free Edition: one Lakeflow pipeline and one serverless SQL warehouse, within free-tier quotas.", 3);
    s.addNotes("Demo story: at 4 pm a coordinator opens HeatGuard. The NOW tab shows live heat stress. The TOMORROW tab shows the risk map and the ranked check-in list with reasons and actions. WHY HERE? explains any area's rank and shows how accurate past forecasts were. Genie answers follow-up questions; the Foundation Model API drafts a plain-language advisory. One pipeline end to end: scheduled ingestion into Unity Catalog, a Lakeflow Declarative Pipeline with quality checks and spatial joins, MLflow-tracked models, and outputs a non-technical coordinator can act on.");
  }

  await pres.writeFile({ fileName: OUT });
  console.log("wrote", OUT);
})();
