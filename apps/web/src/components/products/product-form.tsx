"use client";

import Link from "next/link";
import { useActionState, useEffect, useRef } from "react";
import type { FormState } from "@/app/(dashboard)/products/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Category, Product } from "@/lib/api/types";
import { FormField } from "./form-field";

type ProductAction = (state: FormState, formData: FormData) => Promise<FormState>;

interface ProductFormProps {
  action: ProductAction;
  categories: Category[];
  /** Present when editing. */
  product?: Product;
  submitLabel: string;
  cancelHref: string;
}

const initialState: FormState = { status: "idle" };

export function ProductForm({ action, categories, product, submitLabel, cancelHref }: ProductFormProps) {
  const [state, formAction, isPending] = useActionState(action, initialState);
  const summaryRef = useRef<HTMLDivElement>(null);
  const isEdit = Boolean(product);

  // After a failed submit, move focus to the error summary (WCAG: focus-management).
  useEffect(() => {
    if (state.status === "error") summaryRef.current?.focus();
  }, [state]);

  const value = (key: string, fallback: string | number | null | undefined) =>
    state.values?.[key] ?? (fallback === null || fallback === undefined ? "" : String(fallback));
  const error = (key: string) => state.fields?.[key];

  return (
    <form action={formAction} noValidate className="grid gap-6">
      {state.status === "error" && (
        <div
          ref={summaryRef}
          tabIndex={-1}
          role="alert"
          className="rounded-sm border border-destructive/40 bg-destructive/5 px-4 py-3 text-sm outline-none"
        >
          <p className="font-semibold text-destructive">{state.message}</p>
          {state.fields && Object.keys(state.fields).length > 0 && (
            <p className="mt-0.5 text-muted-foreground">Check the highlighted fields below.</p>
          )}
        </div>
      )}

      <fieldset className="grid gap-4">
        <legend className="mb-1 text-lg font-semibold">Details</legend>
        <FormField id="name" label="Product name" required error={error("name")}>
          {(describedBy) => (
            <Input
              id="name"
              name="name"
              required
              maxLength={160}
              defaultValue={value("name", product?.name)}
              aria-invalid={Boolean(error("name"))}
              aria-describedby={describedBy}
              autoComplete="off"
            />
          )}
        </FormField>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField id="sku" label="SKU" required hint="Your own code for this product." error={error("sku")}>
            {(describedBy) => (
              <Input
                id="sku"
                name="sku"
                required
                maxLength={64}
                defaultValue={value("sku", product?.sku)}
                aria-invalid={Boolean(error("sku"))}
                aria-describedby={describedBy}
                autoComplete="off"
              />
            )}
          </FormField>
          <FormField id="barcode" label="Barcode" hint="Optional. Scan it or type it." error={error("barcode")}>
            {(describedBy) => (
              <Input
                id="barcode"
                name="barcode"
                inputMode="numeric"
                maxLength={64}
                defaultValue={value("barcode", product?.barcode)}
                aria-invalid={Boolean(error("barcode"))}
                aria-describedby={describedBy}
                autoComplete="off"
              />
            )}
          </FormField>
        </div>

        <div className="grid gap-4 sm:grid-cols-2">
          <FormField id="category_id" label="Category" error={error("category_id")}>
            {(describedBy) => (
              <select
                id="category_id"
                name="category_id"
                defaultValue={value("category_id", product?.category?.id)}
                aria-invalid={Boolean(error("category_id"))}
                aria-describedby={describedBy}
                className="h-9 rounded-sm border border-input bg-card px-2.5 text-sm"
              >
                <option value="">No category</option>
                {categories.map((category) => (
                  <option key={category.id} value={category.id}>
                    {category.name}
                  </option>
                ))}
              </select>
            )}
          </FormField>
          <FormField id="unit" label="Unit" hint="How you count it: pcs, btl, can, pack." error={error("unit")}>
            {(describedBy) => (
              <Input
                id="unit"
                name="unit"
                maxLength={16}
                defaultValue={value("unit", product?.unit ?? "pcs")}
                aria-invalid={Boolean(error("unit"))}
                aria-describedby={describedBy}
              />
            )}
          </FormField>
        </div>
      </fieldset>

      <fieldset className="grid gap-4">
        <legend className="mb-1 text-lg font-semibold">Pricing</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField id="price" label="Selling price (₱)" required error={error("price")}>
            {(describedBy) => (
              <Input
                id="price"
                name="price"
                required
                inputMode="decimal"
                placeholder="0.00"
                defaultValue={value("price", product?.price)}
                aria-invalid={Boolean(error("price"))}
                aria-describedby={describedBy}
                className="tabular"
              />
            )}
          </FormField>
          <FormField id="cost" label="Cost (₱)" hint="What you pay the supplier. Used for profit." error={error("cost")}>
            {(describedBy) => (
              <Input
                id="cost"
                name="cost"
                inputMode="decimal"
                placeholder="0.00"
                defaultValue={value("cost", product?.cost)}
                aria-invalid={Boolean(error("cost"))}
                aria-describedby={describedBy}
                className="tabular"
              />
            )}
          </FormField>
        </div>
      </fieldset>

      <fieldset className="grid gap-4">
        <legend className="mb-1 text-lg font-semibold">Stock</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            id="reorder_level"
            label="Reorder level"
            hint="Marked “Low stock” at or below this number."
            error={error("reorder_level")}
          >
            {(describedBy) => (
              <Input
                id="reorder_level"
                name="reorder_level"
                type="number"
                min={0}
                step={1}
                inputMode="numeric"
                defaultValue={value("reorder_level", product?.reorder_level ?? 0)}
                aria-invalid={Boolean(error("reorder_level"))}
                aria-describedby={describedBy}
                className="tabular"
              />
            )}
          </FormField>
          {!isEdit && (
            <FormField
              id="initial_stock"
              label="Opening stock"
              hint="How many you have right now."
              error={error("initial_stock")}
            >
              {(describedBy) => (
                <Input
                  id="initial_stock"
                  name="initial_stock"
                  type="number"
                  min={0}
                  step={1}
                  inputMode="numeric"
                  defaultValue={value("initial_stock", 0)}
                  aria-invalid={Boolean(error("initial_stock"))}
                  aria-describedby={describedBy}
                  className="tabular"
                />
              )}
            </FormField>
          )}
        </div>
        {isEdit && (
          <p className="text-[0.8125rem] text-muted-foreground">
            To change stock on hand, use <span className="font-medium text-foreground">Adjust stock</span> on the
            product page, so every change is recorded.
          </p>
        )}
      </fieldset>

      <div className="flex flex-wrap gap-2 border-t border-border pt-5">
        <Button type="submit" size="lg" disabled={isPending}>
          {isPending ? "Saving…" : submitLabel}
        </Button>
        <Button variant="ghost" size="lg" asChild>
          <Link href={cancelHref}>Cancel</Link>
        </Button>
      </div>
    </form>
  );
}
