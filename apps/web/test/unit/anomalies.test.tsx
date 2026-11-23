import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { WorthALookList } from "@/components/dashboard/worth-a-look-list";
import {
  anomalyDetail,
  anomalyKey,
  anomalySummary,
  anomalyTitle,
  stockItem,
  stockLossDetail,
  stockLossSummary,
} from "@/lib/anomalies";
import type { AnomalyAlert, StockLossAlert } from "@/lib/api/types";
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

const loss = (overrides: Partial<StockLossAlert> = {}): StockLossAlert => ({
  product_id: "p9",
  name: "Bear Brand 33g",
  sku: "BEAR",
  unit: "pcs",
  day: "2026-11-20",
  missing_units: 9,
  units_sold: 100,
  missing_share: "0.0891",
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

describe("stock going missing wording", () => {
  it("shows the missing units against sales", () => {
    expect(stockLossDetail(loss())).toBe(
      "9 pcs missing in counts · 8.9% of 100 sold in 8 weeks",
    );
  });

  it("counts the products", () => {
    expect(stockLossSummary(1)).toBe(
      "1 product lost 5% or more of its sales in stock counts over the last 8 weeks.",
    );
    expect(stockLossSummary(2)).toBe(
      "2 products lost 5% or more of their sales in stock counts over the last 8 weeks.",
    );
  });

  it("dates the alert by the count that found the loss", () => {
    const item = stockItem(loss());
    expect(item).toMatchObject({
      kind: "shrinkage",
      day: "2026-11-20",
      when: "Counted Fri, Nov 20",
      title: "Missing in stock counts",
    });
    expect(anomalyKey(item)).not.toBe(anomalyKey({ ...item, day: "2026-11-25" }));
  });
});

describe("WorthALookList", () => {
  beforeEach(() => dismissAnomalyAction.mockReset());

  it("says when nothing stands out", () => {
    render(<WorthALookList alerts={[]} losses={[]} />);
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
        losses={[]}
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
    render(<WorthALookList alerts={[alert()]} losses={[]} />);
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
    render(<WorthALookList alerts={[alert()]} losses={[]} />);
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
    render(<WorthALookList alerts={[alert()]} losses={[]} />);
    fireEvent.click(screen.getByRole("button", { name: /^Dismiss alert for/ }));
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /^Dismiss alert for/ }),
    ).toHaveFocus();
  });

  it("says when no stock is going missing", () => {
    render(<WorthALookList alerts={[]} losses={[]} />);
    expect(
      screen.getByRole("heading", { level: 3, name: "Stock going missing" }),
    ).toBeInTheDocument();
    expect(
      screen.getByText(
        "No stock count in the last 8 weeks found 5% or more of sales missing.",
      ),
    ).toBeInTheDocument();
  });

  it("lists stock going missing and links to the product's history", () => {
    render(<WorthALookList alerts={[]} losses={[loss()]} />);
    expect(screen.getByText("Missing in stock counts")).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Bear Brand 33g" }),
    ).toHaveAttribute("href", "/products/p9");
    expect(
      screen.getByRole("button", {
        name: "Dismiss alert for Bear Brand 33g, Counted Fri, Nov 20",
      }),
    ).toBeInTheDocument();
  });

  it("dismisses stock going missing by the day of its count", async () => {
    dismissAnomalyAction.mockResolvedValue({ status: "success" });
    render(<WorthALookList alerts={[]} losses={[loss()]} />);
    fireEvent.click(screen.getByRole("button", { name: /^Dismiss alert for/ }));
    fireEvent.click(screen.getByRole("button", { name: "Dismiss alert" }));
    await waitFor(() =>
      expect(screen.getByRole("status")).toHaveTextContent(
        "Alert for Bear Brand 33g dismissed.",
      ),
    );
    expect(dismissAnomalyAction).toHaveBeenCalledWith({
      product_id: "p9",
      day: "2026-11-20",
      kind: "shrinkage",
      note: "",
    });
  });
});
