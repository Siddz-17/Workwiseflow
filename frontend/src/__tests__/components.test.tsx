import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Badge, Empty } from "@/components/ui/card";
import { Button } from "@/components/ui/button";

describe("ui primitives", () => {
  it("renders a button with variant classes", () => {
    render(<Button variant="accent">Go</Button>);
    expect(screen.getByRole("button", { name: "Go" }).className).toContain("bg-acid");
  });
  it("renders badge and empty state", () => {
    render(
      <div>
        <Badge tone="signal">Overdue</Badge>
        <Empty title="Nothing here">Add something</Empty>
      </div>,
    );
    expect(screen.getByText("Overdue").className).toContain("bg-signal");
    expect(screen.getByText("Nothing here")).toBeTruthy();
  });
});
