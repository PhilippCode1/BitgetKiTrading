import {
  orderStatusCountsNonEmpty,
  prettyJsonLine,
  recordHasKeys,
} from "@/lib/live-broker-console";

describe("live-broker-console", () => {
  it("prettyJsonLine formatiert ein Objekt", () => {
    expect(prettyJsonLine({ a: 1 })).toContain('"a"');
    expect(prettyJsonLine({ a: 1 })).toContain("1");
  });

  it("recordHasKeys erkennt leere Objekte und Arrays", () => {
    expect(recordHasKeys({})).toBe(false);
    expect(recordHasKeys([])).toBe(false);
    expect(recordHasKeys({ x: 1 })).toBe(true);
    expect(recordHasKeys([1])).toBe(true);
  });

  it("orderStatusCountsNonEmpty", () => {
    expect(orderStatusCountsNonEmpty(undefined)).toBe(false);
    expect(orderStatusCountsNonEmpty({})).toBe(false);
    expect(orderStatusCountsNonEmpty({ open: 2 })).toBe(true);
  });
});
