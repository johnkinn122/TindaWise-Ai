"use client";

import { Search, Trash2 } from "lucide-react";
import Link from "next/link";
import { useEffect, useId, useRef, useState, useTransition } from "react";
import { type DraftInput, saveDraftAction } from "@/app/(dashboard)/purchase-orders/actions";
import { FormField } from "@/components/forms/form-field";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import type { Product, PurchaseOrder, Supplier } from "@/lib/api/types";
import { formatNumber } from "@/lib/format";
import type { FormState } from "@/lib/form-state";
import { centsToDecimal, formatCents, toCents } from "@/lib/money";

interface EditorLine {
  productId: string;
  name: string;
  sku: string;
  unit: string;
  /** Kept as typed, so a half-typed "1." doesn't jump around; validated on save. */
  quantity: string;
  unitCost: string;
}

interface PurchaseOrderEditorProps {
  /** The draft being edited; absent for a new order. */
  po?: PurchaseOrder;
  /** Active suppliers to choose from. */
  suppliers: Supplier[];
}

const quantityOf = (line: Pick<EditorLine, "quantity">) => (/^\d+$/.test(line.quantity.trim()) ? Number(line.quantity) : Number.NaN);

/** Line totals and the order total, in centavos. Invalid lines count as 0 until fixed. */
export function draftTotalCents(lines: Pick<EditorLine, "quantity" | "unitCost">[]): number {
  return lines.reduce((sum, line) => {
    const quantity = quantityOf(line);
    const cost = toCents(line.unitCost);
    return Number.isNaN(quantity) || Number.isNaN(cost) ? sum : sum + quantity * cost;
  }, 0);
}

/** Checks the browser can do before asking the server; the API checks everything again. */
function validateLines(lines: EditorLine[]): Record<string, string> {
  const fields: Record<string, string> = {};
  lines.forEach((line, index) => {
    const quantity = quantityOf(line);
    if (Number.isNaN(quantity) || quantity < 1) fields[`lines.${index}.quantity`] = "Enter a whole number of 1 or more";
    if (Number.isNaN(toCents(line.unitCost))) fields[`lines.${index}.unit_cost`] = "Enter an amount like 68.00";
  });
  return fields;
}

export function PurchaseOrderEditor({ po, suppliers }: PurchaseOrderEditorProps) {
  const [supplierId, setSupplierId] = useState(po?.supplier?.is_active ? po.supplier.id : "");
  const [expectedOn, setExpectedOn] = useState(po?.expected_on ?? "");
  const [notes, setNotes] = useState(po?.notes ?? "");
  const [lines, setLines] = useState<EditorLine[]>(
    po?.lines.map((line) => ({
      productId: line.product_id,
      name: line.product_name,
      sku: line.sku,
      unit: line.unit,
      quantity: String(line.quantity_ordered),
      unitCost: line.unit_cost,
    })) ?? [],
  );
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<Product[] | null>(null);
  const [searchMessage, setSearchMessage] = useState("");
  const [state, setState] = useState<FormState>({ status: "idle" });
  const [isPending, startTransition] = useTransition();
  const summaryRef = useRef<HTMLDivElement>(null);
  const searchRef = useRef<HTMLInputElement>(null);
  const debounce = useRef<ReturnType<typeof setTimeout>>(undefined);
  // One key per new order, kept across retries, so a double submit creates one draft.
  const createKey = useRef<string | null>(null);
  const resultsId = useId();

  useEffect(() => () => clearTimeout(debounce.current), []);
  useEffect(() => {
    if (state.status === "error") summaryRef.current?.focus();
  }, [state]);

  const fieldError = (key: string) => state.fields?.[key];
  const totalCents = draftTotalCents(lines);

  function onQueryChange(value: string) {
    setQuery(value);
    clearTimeout(debounce.current);
    if (!value.trim()) {
      setResults(null);
      setSearchMessage("");
      return;
    }
    debounce.current = setTimeout(async () => {
      // Same server route the checkout uses; it reads the API with the signed-in session.
      const response = await fetch(`/sell/products?${new URLSearchParams({ q: value.trim() })}`);
      if (!response.ok) {
        setResults([]);
        setSearchMessage("Search failed. Try again.");
        return;
      }
      const { items } = (await response.json()) as { items: Product[] };
      setResults(items);
      setSearchMessage(items.length === 0 ? `Nothing matches “${value.trim()}”.` : `${items.length} found.`);
    }, 250);
  }

  function addProduct(product: Product) {
    setLines((current) =>
      current.some((line) => line.productId === product.id)
        ? current
        : [
            ...current,
            {
              productId: product.id,
              name: product.name,
              sku: product.sku,
              unit: product.unit,
              quantity: "1",
              unitCost: product.cost ?? "0.00",
            },
          ],
    );
    setQuery("");
    setResults(null);
    setSearchMessage(`Added ${product.name}.`);
    searchRef.current?.focus();
  }

  function updateLine(productId: string, change: Partial<EditorLine>) {
    setLines((current) => current.map((line) => (line.productId === productId ? { ...line, ...change } : line)));
  }

  function removeLine(productId: string) {
    setLines((current) => current.filter((line) => line.productId !== productId));
  }

  function save() {
    if (lines.length === 0) {
      setState({ status: "error", message: "Add at least one product to the order.", fields: {} });
      return;
    }
    const fields = validateLines(lines);
    if (Object.keys(fields).length > 0) {
      setState({ status: "error", message: "Some lines need attention.", fields });
      return;
    }
    const input: DraftInput = {
      supplier_id: supplierId || null,
      expected_on: expectedOn || null,
      notes: notes.trim() || null,
      lines: lines.map((line) => ({
        product_id: line.productId,
        quantity: quantityOf(line),
        unit_cost: centsToDecimal(toCents(line.unitCost)),
      })),
    };
    createKey.current ??= crypto.randomUUID();
    startTransition(async () => {
      const result = await saveDraftAction(po?.id ?? null, input, createKey.current!);
      if (result?.status === "error") setState(result);
    });
  }

  const activeSuppliers = suppliers.filter((supplier) => supplier.is_active);

  return (
    <form
      noValidate
      className="grid gap-6"
      onSubmit={(event) => {
        event.preventDefault();
        save();
      }}
    >
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
        <legend className="mb-1 text-lg font-semibold">Order</legend>
        <div className="grid gap-4 sm:grid-cols-2">
          <FormField
            name="supplier_id"
            label="Supplier"
            hint={activeSuppliers.length === 0 ? "No suppliers yet." : "Needed before the owner can approve."}
            error={fieldError("supplier_id")}
          >
            {({ id, describedBy }) => (
              <select
                id={id}
                value={supplierId}
                onChange={(event) => setSupplierId(event.target.value)}
                aria-invalid={Boolean(fieldError("supplier_id"))}
                aria-describedby={describedBy}
                className="h-9 rounded-sm border border-input bg-card px-2.5 text-sm"
              >
                <option value="">Choose later</option>
                {activeSuppliers.map((supplier) => (
                  <option key={supplier.id} value={supplier.id}>
                    {supplier.name}
                  </option>
                ))}
              </select>
            )}
          </FormField>
          <FormField name="expected_on" label="Expected delivery" error={fieldError("expected_on")}>
            {({ id, describedBy }) => (
              <Input
                id={id}
                type="date"
                value={expectedOn}
                onChange={(event) => setExpectedOn(event.target.value)}
                aria-invalid={Boolean(fieldError("expected_on"))}
                aria-describedby={describedBy}
              />
            )}
          </FormField>
        </div>
        {activeSuppliers.length === 0 && (
          <p className="text-[0.8125rem] text-muted-foreground">
            <Link href="/suppliers/new" className="font-medium text-primary underline-offset-4 hover:underline">
              Add a supplier
            </Link>{" "}
            first, or save this draft and choose one later.
          </p>
        )}
        <FormField name="notes" label="Notes" error={fieldError("notes")}>
          {({ id, describedBy }) => (
            <Textarea
              id={id}
              rows={2}
              maxLength={500}
              value={notes}
              onChange={(event) => setNotes(event.target.value)}
              aria-describedby={describedBy}
            />
          )}
        </FormField>
      </fieldset>

      <fieldset className="grid gap-3">
        <legend className="mb-1 text-lg font-semibold">Products</legend>
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            aria-hidden="true"
          />
          <Input
            ref={searchRef}
            type="search"
            aria-label="Add a product"
            // Points at the results only while they're on screen (an id that doesn't exist is invalid ARIA).
            aria-controls={results ? resultsId : undefined}
            placeholder="Name, SKU or barcode"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            className="pl-8"
            autoComplete="off"
          />
        </div>
        <p className="sr-only" role="status">
          {searchMessage}
        </p>
        {results && (
          <ul id={resultsId} aria-label="Search results" className="grid max-h-72 overflow-auto rounded-sm border border-border">
            {results.length === 0 ? (
              <li className="px-3 py-2.5 text-sm text-muted-foreground">{searchMessage}</li>
            ) : (
              results.map((product) => {
                const added = lines.some((line) => line.productId === product.id);
                return (
                  <li key={product.id} className="border-b border-border last:border-b-0">
                    <button
                      type="button"
                      onClick={() => addProduct(product)}
                      disabled={added}
                      className="flex w-full items-center justify-between gap-3 px-3 py-2.5 text-left text-sm hover:bg-muted disabled:cursor-default disabled:opacity-60"
                    >
                      <span className="min-w-0">
                        <span className="block font-medium">{product.name}</span>
                        <span className="block text-xs text-muted-foreground">
                          {product.sku} · {formatNumber(product.stock_on_hand)} {product.unit} on hand
                        </span>
                      </span>
                      <span className="shrink-0 text-xs text-muted-foreground">{added ? "Added" : "Add"}</span>
                    </button>
                  </li>
                );
              })
            )}
          </ul>
        )}

        {lines.length === 0 ? (
          <p className="rounded-sm border border-dashed border-border px-4 py-6 text-center text-sm text-muted-foreground">
            {fieldError("lines") ?? "No products yet. Search above to add what you want to order."}
          </p>
        ) : (
          <ul className="divide-y divide-border rounded-sm border border-border" aria-label="Order lines">
            {lines.map((line, index) => {
              const quantity = quantityOf(line);
              const cost = toCents(line.unitCost);
              const lineCents = Number.isNaN(quantity) || Number.isNaN(cost) ? null : quantity * cost;
              const quantityError = fieldError(`lines.${index}.quantity`);
              const costError = fieldError(`lines.${index}.unit_cost`);
              return (
                <li key={line.productId} className="grid gap-3 px-3 py-3 sm:grid-cols-[1fr_7rem_8rem_7rem_auto] sm:items-start">
                  <div className="min-w-0 pt-1.5">
                    <p className="font-medium">{line.name}</p>
                    <p className="text-xs text-muted-foreground">{line.sku}</p>
                  </div>
                  <label className="grid gap-1 text-xs text-muted-foreground">
                    <span>Quantity ({line.unit})</span>
                    <Input
                      inputMode="numeric"
                      value={line.quantity}
                      onChange={(event) => updateLine(line.productId, { quantity: event.target.value })}
                      aria-invalid={Boolean(quantityError)}
                      aria-label={`Quantity (${line.unit}) of ${line.name}`}
                      className="tabular text-foreground"
                    />
                    {quantityError && <span className="text-destructive">{quantityError}</span>}
                  </label>
                  <label className="grid gap-1 text-xs text-muted-foreground">
                    <span>Unit cost (₱)</span>
                    <Input
                      inputMode="decimal"
                      value={line.unitCost}
                      onChange={(event) => updateLine(line.productId, { unitCost: event.target.value })}
                      aria-invalid={Boolean(costError)}
                      aria-label={`Unit cost (₱) of ${line.name}`}
                      className="tabular text-foreground"
                    />
                    {costError && <span className="text-destructive">{costError}</span>}
                  </label>
                  <div className="grid gap-1 text-xs text-muted-foreground sm:text-right">
                    <span>Line total</span>
                    <span className="tabular pt-2 text-sm font-semibold text-foreground">
                      {lineCents === null ? "—" : formatCents(lineCents)}
                    </span>
                  </div>
                  <Button
                    type="button"
                    variant="ghost"
                    size="icon"
                    onClick={() => removeLine(line.productId)}
                    aria-label={`Remove ${line.name}`}
                    className="justify-self-start sm:mt-5"
                  >
                    <Trash2 aria-hidden="true" />
                  </Button>
                </li>
              );
            })}
          </ul>
        )}
        <div className="tabular flex items-baseline justify-between px-1 text-lg font-semibold">
          <span>Total</span>
          <span>{formatCents(totalCents)}</span>
        </div>
      </fieldset>

      <div className="flex flex-wrap gap-2 border-t border-border pt-5">
        <Button type="submit" size="lg" disabled={isPending}>
          {isPending ? "Saving…" : po ? "Save draft" : "Create draft"}
        </Button>
        <Button variant="ghost" size="lg" asChild>
          <Link href={po ? `/purchase-orders/${po.id}` : "/purchase-orders"}>Cancel</Link>
        </Button>
      </div>
    </form>
  );
}
