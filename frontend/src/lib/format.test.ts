import { describe, expect, it } from "vitest";

import {
  formatBytes,
  formatDuration,
  formatNumber,
  formatPercent,
  initials,
  titleCase,
} from "@/lib/format";

describe("formatBytes", () => {
  it("renders zero and invalid values as 0 B", () => {
    expect(formatBytes(0)).toBe("0 B");
    expect(formatBytes(-10)).toBe("0 B");
    expect(formatBytes(Number.NaN)).toBe("0 B");
  });

  it("scales to the appropriate unit", () => {
    expect(formatBytes(512)).toBe("512 B");
    expect(formatBytes(2048)).toBe("2.0 KB");
    expect(formatBytes(5 * 1024 * 1024)).toBe("5.0 MB");
  });
});

describe("formatDuration", () => {
  it("renders em dash for missing values", () => {
    expect(formatDuration(null)).toBe("—");
    expect(formatDuration(undefined)).toBe("—");
  });

  it("switches between ms and seconds", () => {
    expect(formatDuration(0)).toBe("0 ms");
    expect(formatDuration(750)).toBe("750 ms");
    expect(formatDuration(1500)).toBe("1.50 s");
  });
});

describe("formatNumber", () => {
  it("renders em dash for missing values", () => {
    expect(formatNumber(null)).toBe("—");
    expect(formatNumber(undefined)).toBe("—");
  });
});

describe("formatPercent", () => {
  it("renders a one-decimal percentage", () => {
    expect(formatPercent(0.5)).toBe("50.0%");
    expect(formatPercent(null)).toBe("—");
  });
});

describe("initials", () => {
  it("derives initials from names", () => {
    expect(initials("jane.doe")).toBe("JD");
    expect(initials("alice")).toBe("AL");
    expect(initials("   ")).toBe("?");
  });
});

describe("titleCase", () => {
  it("humanises snake_case and kebab-case", () => {
    expect(titleCase("partially_supported")).toBe("Partially Supported");
    expect(titleCase("document-manager")).toBe("Document Manager");
  });
});
