import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorthALookList } from "@/components/dashboard/worth-a-look-list";
import {
  anomalyDetail,
  anomalyKey,
  anomalySummary,
  anomalyTitle,
} from "@/lib/anomalies";
import type { AnomalyAlert } from "@/lib/api/types";
import { formatCalendarDay } from "@/lib/format";

const dismissAnomalyAction = vi.fn();
vi.mock("@/app/(dashboard)/actions", () => ({
  dismissAnomalyAction: (...args: unknown[]) => dismissAnomalyAction(...args),
}));

const alert = (overrides: Partial<AnomalyAlert> = {}): AnomalyAlert => ({
  product_id: "p1",
  name: "Coke 1.5L",
  sku: "COKE-15",
  unit: "pcs",
  day: "2026-11-21",
  kind: "drop",
  units_sold: 0,
  usual_daily: "9.0",
  in_stock_days: 28,
  ...overrides,
});

describe("anomaly wording", () => {
  it("names what happened", () => {
    expect(anomalyTitle({ kind: "spike", units_sold: 20 })).toBe(
      "More sales than usual",
    );
    expect(anomalyTitle({ kind: "drop", units_sold: 0 })).toBe(
      "No sales recorded",
    );
    expect(anomalyTitle({ kind: "drop", units_sold: 1 })).toBe(
      "Fewer sales than usual",
    );
  });

  it("shows the evidence, and says a drop happened while in stock", () => {
    expect(anomalyDetail(alert())).toBe(
      "Sold 0 pcs while in stock · usually about 9 a day",
    );
    expect(
      anomalyDetail(
        alert({
          kind: "spike",
          units_sold: 1200,
          usual_daily: "4.5",
          unit: "packs",
        }),
      ),
    ).toBe("Sold 1,200 packs · usually about 4.5 a day");
  });

  it("counts the days", () => {
    expect(anomalySummary(1)).toBe(
      "1 sales day stands out in the last 7 days.",
    );
    expect(anomalySummary(3)).toBe(
      "3 sales days stand out in the last 7 days.",
    );
  });

  it("keys an alert by product, day and direction", () => {
    expect(anomalyKey(alert())).not.toBe(anomalyKey(alert({ kind: "spike" })));
    expect(anomalyKey(alert())).not.toBe(
      anomalyKey(alert({ day: "2026-11-22" })),
    );
  });

  it("formats a store day with its weekday, whatever the machine's zone", () => {
    expect(formatCalendarDay("2026-11-21")).toBe("Sat, Nov 21");
    expect(formatCalendarDay("2026-01-01")).toBe("Thu, Jan 1");
  });
});

describe("WorthALookList", () => {
  beforeEach(() => dismissAnomalyAction.mockReset());

  it("says when nothing stands out", () => {
    render(<WorthALookList alerts={[]} />);
    expect(
      screen.getByText("Nothing unusual in the last 7 days."),
    ).toBeInTheDocument();
  });

  it("lists each alert with words and an icon, not color alone", () => {
    render(
      <WorthALookList
        alerts={[
          alert(),
          alert({
            product_id: "p2",
            name: "Lucky Me",
            kind: "spike",
            units_sold: 20,
            usual_daily: "4.0",
          }),
        ]}
      />,
    );
    expect(
      screen.getByText("2 sales days stand out in the last 7 days."),
    ).toBeInTheDocument();
    expect(screen.getByText("No sales recorded")).toBeInTheDocument();
    expect(screen.getByText("More sales than usual")).toBeInTheDocument();
    expect(
      screen.getByText("Sold 20 pcs · usually about 4 a day"),
    ).toBeInTheDocument();
    expect(
      screen.getAllByRole("button", { name: /^Dismiss alert for / }),
    ).toHaveLength(2);
  });

  it("dismisses with an optional note and announces it", async () => {
    dismissAnomalyAction.mockResolvedValue({ status: "success" });
    render(<WorthALookList alerts={[alert()]} />);
    fireEvent.click(
      screen.getByRole("button", {
        name: "Dismiss alert for Coke 1.5L, Sat, Nov 21",
      }),
    );
    const note = screen.getByRole("textbox", { name: "Note (optional)" });
    expect(note).toHaveFocus();
    fireEvent.change(note, { target: { value: "Closed for the fiesta" } });
    fireEvent.click(screen.getByRole("button", { name: "Dismiss alert" }));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "Alert for Coke 1.5L dismissed.",
      ),
    );
    expect(dismissAnomalyAction).toHaveBeenCalledWith({
      product_id: "p1",
      day: "2026-11-21",
      kind: "drop",
      note: "Closed for the fiesta",
    });
  });

  it("keeps the form open with the API's message when the dismissal is refused", async () => {
    dismissAnomalyAction.mockResolvedValue({
      status: "error",
      message: "That alert isn't on the list any more.",
    });
    render(<WorthALookList alerts={[alert()]} />);
    fireEvent.click(screen.getByRole("button", { name: /^Dismiss alert for/ }));
    fireEvent.click(screen.getByRole("button", { name: "Dismiss alert" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(
      "That alert isn't on the list any more.",
    );
    expect(
      screen.getByRole("textbox", { name: "Note (optional)" }),
    ).toHaveAttribute("aria-invalid", "true");
  });

  it("cancel closes the form and puts focus back on Dismiss", () => {
    render(<WorthALookList alerts={[alert()]} />);
    fireEvent.click(screen.getByRole("button", { name: /^Dismiss alert for/ }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^Dismiss alert for/ }),
    ).toHaveFocus();
  });
});
