import { describe, expect, it } from "vitest";

import { answerBlocks, daysUntil, dueLabel, initials, splitCitations } from "@/lib/format";

describe("splitCitations", () => {
  it("splits text and [n] markers", () => {
    expect(splitCitations("Pro is $49 [1] and annual saves 20% [2][3].")).toEqual([
      { type: "text", text: "Pro is $49 " },
      { type: "cite", n: 1 },
      { type: "text", text: " and annual saves 20% " },
      { type: "cite", n: 2 },
      { type: "cite", n: 3 },
      { type: "text", text: "." },
    ]);
  });
  it("leaves plain text alone", () => {
    expect(splitCitations("no sources")).toEqual([{ type: "text", text: "no sources" }]);
  });
});

describe("answerBlocks", () => {
  it("groups bullets into lists", () => {
    expect(answerBlocks("Intro\n\n- one [1]\n- two\nOutro")).toEqual([
      { type: "p", text: "Intro" },
      { type: "ul", items: ["one [1]", "two"] },
      { type: "p", text: "Outro" },
    ]);
  });
});

describe("dates", () => {
  const today = new Date(2026, 10, 18);
  it("computes days until a date", () => {
    expect(daysUntil("2026-11-20", today)).toBe(2);
    expect(daysUntil("2026-11-15", today)).toBe(-3);
  });
  it("labels deadlines", () => {
    expect(dueLabel(null, today)).toBe("No deadline");
    expect(dueLabel("2026-11-18", today)).toBe("Due today");
    expect(dueLabel("2026-11-19", today)).toBe("Due tomorrow");
    expect(dueLabel("2026-11-16", today)).toBe("2d overdue");
  });
});

it("builds initials", () => {
  expect(initials("Ada Lovelace")).toBe("AL");
  expect(initials("bob.smith@acme.com")).toBe("BS");
});
