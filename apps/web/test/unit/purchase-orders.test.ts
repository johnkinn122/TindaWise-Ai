import { describe, expect, it } from "vitest";
import { draftTotalCents } from "@/components/purchase-orders/purchase-order-editor";
import type { PurchaseOrderStatus } from "@/lib/api/types";
import { formatCalendarDate } from "@/lib/format";
import { approvalBlocker, availableActions, findStatusFilter } from "@/lib/purchase-orders";

const order = (status: PurchaseOrderStatus) => ({ status });

describe("availableActions", () => {
  it("lets only the owner approve a draft", () => {
    expect(availableActions(order("draft"), "owner")).toMatchObject({ edit: true, approve: true, cancel: true });
    expect(availableActions(order("draft"), "manager")).toMatchObject({ edit: true, approve: false, cancel: true });
  });

  it("lets only the owner cancel an approved order, and nobody edit it", () => {
    expect(availableActions(order("approved"), "owner")).toMatchObject({ edit: false, cancel: true, receive: true });
    expect(availableActions(order("approved"), "manager")).toMatchObject({ cancel: false, receive: true });
  });

  it("offers close-short, never cancel, once something was received", () => {
    expect(availableActions(order("partially_received"), "manager")).toMatchObject({
      receive: true,
      closeShort: true,
      cancel: false,
    });
  });

  it.each(["received", "closed", "cancelled"] as const)("offers nothing on a %s order", (status) => {
    expect(Object.values(availableActions(order(status), "owner")).some(Boolean)).toBe(false);
  });

  it("offers cashiers nothing at all", () => {
    for (const status of ["draft", "approved", "partially_received"] as const) {
      expect(Object.values(availableActions(order(status), "cashier")).some(Boolean)).toBe(false);
    }
  });
});

describe("approvalBlocker", () => {
  it("explains a missing or archived supplier", () => {
    expect(approvalBlocker({ status: "draft", supplier: null })).toMatch(/Choose a supplier/);
    expect(approvalBlocker({ status: "draft", supplier: { id: "s", name: "Puregold", is_active: false } })).toBe(
      "Puregold is archived. Choose another supplier.",
    );
    expect(approvalBlocker({ status: "draft", supplier: { id: "s", name: "Puregold", is_active: true } })).toBeNull();
  });
});

describe("findStatusFilter", () => {
  it("maps tabs to statuses and falls back to all", () => {
    expect(findStatusFilter("open").statuses).toEqual(["approved", "partially_received"]);
    expect(findStatusFilter("nonsense").id).toBe("all");
    expect(findStatusFilter(undefined).id).toBe("all");
  });
});

describe("draftTotalCents", () => {
  it("adds lines exactly in centavos and skips lines still being typed", () => {
    expect(
      draftTotalCents([
        { quantity: "24", unitCost: "68.00" },
        { quantity: "3", unitCost: "0.10" },
        { quantity: "", unitCost: "5.00" },
        { quantity: "2", unitCost: "abc" },
      ]),
    ).toBe(163230);
  });
});

describe("formatCalendarDate", () => {
  it("never shifts a date-only value by time zone", () => {
    expect(formatCalendarDate("2026-11-30")).toBe("Nov 30, 2026");
  });
});
