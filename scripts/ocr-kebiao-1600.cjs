#!/usr/bin/env node
/*
 * OCR source:
 * Ministry of Education, PRC, 《义务教育英语课程标准（2022年版）》,
 * Appendix 3, level-three vocabulary list, printed pages 98-132.
 *
 * Tesseract.js is a build-time dependency. Run with NODE_PATH pointing to an
 * installation of tesseract.js and TESS_LANG_PATH pointing to a directory that
 * contains eng.traineddata.gz. OCR output is retained as an audit artifact and
 * is never used directly as the runtime whitelist.
 */

const fs = require("node:fs");
const path = require("node:path");
const { createWorker, PSM } = require("tesseract.js");

async function main() {
  const [, , imageDirectory, outputDirectory] = process.argv;
  if (!imageDirectory || !outputDirectory) {
    throw new Error("Usage: node ocr-kebiao-1600.cjs <image-dir> <output-dir>");
  }
  if (!process.env.TESS_LANG_PATH) {
    throw new Error("TESS_LANG_PATH is required");
  }

  fs.mkdirSync(outputDirectory, { recursive: true });
  const worker = await createWorker("eng", 1, {
    langPath: process.env.TESS_LANG_PATH,
    cachePath: process.env.TESS_LANG_PATH,
  });
  const psm = process.env.TESS_PSM;
  const psmModes = {
    sparse: PSM.SPARSE_TEXT,
    block: PSM.SINGLE_BLOCK,
    column: PSM.SINGLE_COLUMN,
    auto: PSM.AUTO,
  };
  if (psm && psmModes[psm]) {
    await worker.setParameters({ tessedit_pageseg_mode: psmModes[psm] });
  }

  try {
    for (let page = 105; page <= 139; page += 1) {
      const image = path.join(imageDirectory, `kebiao-p${String(page).padStart(3, "0")}.png`);
      const suffix = psm ? `.${psm}` : "";
      const output = path.join(outputDirectory, `kebiao-p${page}${suffix}.txt`);
      const result = await worker.recognize(image, {}, { blocks: true, tsv: true, text: true });
      fs.writeFileSync(output, result.data.text, "utf8");
      fs.writeFileSync(output.replace(/\.txt$/, ".tsv"), result.data.tsv, "utf8");
      console.log(`${output} confidence=${result.data.confidence.toFixed(2)}`);
    }
  } finally {
    await worker.terminate();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
