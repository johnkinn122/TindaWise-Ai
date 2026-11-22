/**
 * CSV for spreadsheets. Names come from what people typed (products, suppliers), so a cell like
 * "=HYPERLINK(...)" would run as a formula when opened in Excel or Sheets (CSV injection). Text that
 * starts with = + - @ or a tab/return gets a leading apostrophe; plain numbers are left alone.
 */

const PLAIN_NUMBER = /^-?\d+(\.\d+)?$/;
const FORMULA_START = /^[=+\-@\t\r]/;

export type CsvCell = string | number | null | undefined;

export function csvCell(value: CsvCell): string {
  if (value === null || value === undefined) return "";
  let text = String(value);
  if (typeof value === "string" && !PLAIN_NUMBER.test(text) && FORMULA_START.test(text)) text = `'${text}`;
  return /[",\r\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

/** Header row + rows, CRLF line ends, with a BOM so Excel reads ₱ and ñ as UTF-8. */
export function toCsv(headers: string[], rows: CsvCell[][]): string {
  return `\uFEFF${[headers, ...rows].map((row) => row.map(csvCell).join(",")).join("\r\n")}\r\n`;
}
