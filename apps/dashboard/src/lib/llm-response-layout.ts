/**
 * Teilt lange Modell-Fliesstexte fuer die UI in Kurzfassung + optionalen Rest.
 * Keine inhaltliche Interpretation — nur Absatz- und Laengenheuristiken.
 */
export function splitExplanatoryText(
  raw: string | null | undefined,
  maxFirstParagraphChars = 480,
): { summary: string; detail: string } {
  const text = (raw ?? "").trim();
  if (!text) {
    return { summary: "", detail: "" };
  }

  const paragraphs = text
    .split(/\n\s*\n/)
    .map((p) => p.trim())
    .filter(Boolean);

  const first = paragraphs[0] ?? text;

  if (paragraphs.length >= 2 && first.length <= maxFirstParagraphChars) {
    return {
      summary: first,
      detail: paragraphs.slice(1).join("\n\n").trim(),
    };
  }

  if (first.length <= maxFirstParagraphChars) {
    return { summary: first, detail: "" };
  }

  const sentence = first.match(/^(.{20,}?[.!?])(\s+|$)/);
  if (sentence && sentence[1].length <= maxFirstParagraphChars + 120) {
    const summary = sentence[1].trim();
    const restOfFirst = first.slice(sentence[0].length).trim();
    const tail = paragraphs.slice(1);
    const detailParts = [restOfFirst, ...tail].filter(Boolean);
    return {
      summary,
      detail: detailParts.join("\n\n").trim(),
    };
  }

  const cut = first.lastIndexOf(" ", maxFirstParagraphChars);
  const boundary = cut > 120 ? cut : maxFirstParagraphChars;
  const summary = `${first.slice(0, boundary).trim()}…`;
  const remainder = first.slice(boundary).trim();
  const detailParts = [remainder, ...paragraphs.slice(1)].filter(Boolean);
  return {
    summary,
    detail: detailParts.join("\n\n").trim(),
  };
}
