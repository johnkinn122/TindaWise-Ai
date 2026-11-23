import { describe, expect, it } from "vitest";
import { actionLabels, activityLink, activityQuery, parseActivityParams } from "@/lib/activity";
import type { AuditEvent } from "@/lib/api/types";

const event = (overrides: Partial<AuditEvent>): AuditEvent => ({
  id: "e1",
  action: "store.updated",
  entity_type: "store",
  entity_id: "org-1",
  summary: "Changed store settings: name",
  details: {},
  actor_user_id: "u1",
  actor_name: "Nena Santos",
  created_at: "2026-11-23T02:00:00Z",
  ...overrides,
});

describe("parseActivityParams", () => {
  it("keeps known actions and positive pages only", () => {
    expect(parseActivityParams({ action: "refund.created", page: "3" })).toEqual({ action: "refund.created", page: 3 });
    expect(parseActivityParams({ action: "drop.table", page: "-2" })).toEqual({ page: 1 });
    expect(parseActivityParams({ action: ["product.archived", "x"], page: "abc" })).toEqual({
      action: "product.archived",
      page: 1,
    });
    expect(parseActivityParams({ action: "" })).toEqual({ page: 1 });
  });
});

describe("activityQuery", () => {
  it("turns a page into limit and offset", () => {
    expect(activityQuery({ page: 1 })).toEqual({ limit: "25", offset: "0" });
    expect(activityQuery({ action: "member.added", page: 3 })).toEqual({
      action: "member.added",
      limit: "25",
      offset: "50",
    });
  });
});

describe("activityLink", () => {
  it("opens the receipt a refund belongs to", () => {
    const refund = event({ action: "refund.created", entity_type: "refund", entity_id: "r1", details: { sale_id: "s9" } });
    expect(activityLink(refund)).toEqual({ href: "/sales/s9", label: "Open receipt" });
    expect(activityLink({ ...refund, details: {} })).toBeNull();
  });

  it("opens orders, products, the team and settings", () => {
    expect(activityLink(event({ entity_type: "purchase_order", entity_id: "p1" }))?.href).toBe("/purchase-orders/p1");
    expect(activityLink(event({ entity_type: "product", entity_id: "x1" }))?.href).toBe("/products/x1");
    expect(activityLink(event({ entity_type: "user", entity_id: "u2" }))?.href).toBe("/settings/team");
    expect(activityLink(event({}))?.href).toBe("/settings/store");
    expect(activityLink(event({ entity_type: "something_new" }))).toBeNull();
  });
});

describe("actionLabels", () => {
  it("names every action the API records", () => {
    expect(Object.keys(actionLabels).sort()).toEqual(
      [
        "anomaly.dismissed",
        "member.added",
        "product.archived",
        "product.price_changed",
        "purchase_order.approved",
        "purchase_order.cancelled",
        "purchase_order.closed",
        "refund.created",
        "store.updated",
      ].sort(),
    );
  });
});
