"use server";

import { refresh } from "next/cache";
import { redirect } from "next/navigation";
import { ApiError, ApiUnavailableError, apiFetch } from "@/lib/api/client";
import type { Product, StockMovement } from "@/lib/api/types";

/**
 * Server Actions for the Products module. Each one calls the API, then either redirects or
 * returns a FormState that the form renders (field errors stay next to their fields).
 */

export interface FormState {
  status: "idle" | "error" | "success";
  message?: string;
  fields?: Record<string, string>;
  /** Submitted values, echoed back so inputs keep what the person typed after an error. */
  values?: Record<string, string>;
}

const text = (formData: FormData, key: string) => String(formData.get(key) ?? "").trim();
const optional = (value: string) => (value === "" ? null : value);

function toFormState(error: unknown, values?: Record<string, string>): FormState {
  if (error instanceof ApiError) {
    return { status: "error", message: error.message, fields: error.fields, values };
  }
  if (error instanceof ApiUnavailableError) {
    return {
      status: "error",
      message: "Can't reach the Tindawise API. Check that it is running, then try again.",
      values,
    };
  }
  throw error;
}

function productPayload(formData: FormData) {
  const values = {
    name: text(formData, "name"),
    sku: text(formData, "sku"),
    barcode: text(formData, "barcode"),
    category_id: text(formData, "category_id"),
    unit: text(formData, "unit"),
    price: text(formData, "price"),
    cost: text(formData, "cost"),
    reorder_level: text(formData, "reorder_level"),
    initial_stock: text(formData, "initial_stock"),
  };
  const payload = {
    name: values.name,
    sku: values.sku,
    barcode: optional(values.barcode),
    category_id: optional(values.category_id),
    unit: values.unit || "pcs",
    price: values.price,
    cost: values.cost || "0",
    reorder_level: values.reorder_level === "" ? 0 : Number(values.reorder_level),
  };
  return { values, payload };
}

export async function createProductAction(_prev: FormState, formData: FormData): Promise<FormState> {
  const { values, payload } = productPayload(formData);
  let product: Product;
  try {
    product = await apiFetch<Product>("/products", {
      method: "POST",
      body: { ...payload, initial_stock: values.initial_stock === "" ? 0 : Number(values.initial_stock) },
    });
  } catch (error) {
    return toFormState(error, values);
  }
  redirect(`/products/${product.id}`);
}

export async function updateProductAction(
  productId: string,
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  const { values, payload } = productPayload(formData);
  try {
    await apiFetch<Product>(`/products/${encodeURIComponent(productId)}`, { method: "PATCH", body: payload });
  } catch (error) {
    return toFormState(error, values);
  }
  redirect(`/products/${productId}`);
}

export async function adjustStockAction(
  productId: string,
  _prev: FormState,
  formData: FormData,
): Promise<FormState> {
  const values = {
    direction: text(formData, "direction"),
    quantity: text(formData, "quantity"),
    reason: text(formData, "reason"),
    note: text(formData, "note"),
  };
  const quantity = Number(values.quantity);
  const idempotencyKey = text(formData, "idempotency_key");
  if (!Number.isInteger(quantity) || quantity <= 0) {
    return {
      status: "error",
      message: "Enter how many units to add or remove.",
      fields: { quantity: "Enter a whole number greater than 0" },
      values,
    };
  }

  try {
    const movement = await apiFetch<StockMovement>(
      `/products/${encodeURIComponent(productId)}/stock-adjustments`,
      {
        method: "POST",
        body: {
          quantity_change: values.direction === "remove" ? -quantity : quantity,
          reason: values.reason,
          note: optional(values.note),
        },
        // One key per form submission: a double-click or network retry won't apply twice.
        headers: idempotencyKey ? { "Idempotency-Key": idempotencyKey } : {},
      },
    );
    refresh();
    return { status: "success", message: `Stock updated. New balance: ${movement.balance_after}.` };
  } catch (error) {
    // The API names the field "quantity_change"; the form calls it "quantity".
    const state = toFormState(error, values);
    if (state.fields?.quantity_change) {
      state.fields = { ...state.fields, quantity: state.fields.quantity_change };
    }
    return state;
  }
}

export async function archiveProductAction(productId: string): Promise<FormState> {
  try {
    await apiFetch<void>(`/products/${encodeURIComponent(productId)}`, { method: "DELETE" });
  } catch (error) {
    return toFormState(error);
  }
  redirect("/products");
}
