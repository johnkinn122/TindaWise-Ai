"use client";

import { Minus, Plus, ScanBarcode, Trash2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useMemo, useRef, useState, useTransition } from "react";
import { type CheckoutInput, checkoutAction } from "@/app/(dashboard)/sell/actions";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import type { Product, Sale } from "@/lib/api/types";
import { formatCents, quickCashAmounts, toCents } from "@/lib/money";
import { cn } from "@/lib/utils";
import { Receipt } from "./receipt";

interface CartLine {
  product: Product;
  quantity: number;
}

type SearchState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "results"; items: Product[] }
  | { status: "message"; text: string; tone: "info" | "error" };

interface LookupResult {
  ok: boolean;
  status: number;
  items: Product[];
  message?: string;
}

async function fetchProducts(params: Record<string, string>, onSignedOut: () => void): Promise<LookupResult> {
  const response = await fetch(`/sell/products?${new URLSearchParams(params)}`, { cache: "no-store" });
  if (response.status === 401) {
    onSignedOut();
    return { ok: false, status: 401, items: [] };
  }
  const body = await response.json().catch(() => ({}));
  return { ok: response.ok, status: response.status, items: body.items ?? [], message: body.error?.message };
}

export function PosTerminal({ storeName }: { storeName: string }) {
  const router = useRouter();
  const signedOut = () => router.push("/login?reason=session&next=/sell");
  const [cart, setCart] = useState<CartLine[]>([]);
  const [query, setQuery] = useState("");
  const [search, setSearch] = useState<SearchState>({ status: "idle" });
  const [method, setMethod] = useState<"cash" | "e_wallet">("cash");
  const [cash, setCash] = useState("");
  const [reference, setReference] = useState("");
  const [error, setError] = useState<{ message: string; fields: Record<string, string> } | null>(null);
  const [sale, setSale] = useState<Sale | null>(null);
  const [announcement, setAnnouncement] = useState("");
  const [isPending, startTransition] = useTransition();

  const searchRef = useRef<HTMLInputElement>(null);
  const debounce = useRef<ReturnType<typeof setTimeout>>(undefined);
  // Kept across retries of the SAME checkout; cleared whenever the cart or payment changes.
  const checkoutKey = useRef<string | null>(null);

  const totalCents = useMemo(
    () => cart.reduce((sum, line) => sum + toCents(line.product.price) * line.quantity, 0),
    [cart],
  );
  const itemCount = cart.reduce((sum, line) => sum + line.quantity, 0);
  const cashCents = cash ? toCents(cash) : Number.NaN;
  const changeCents = Number.isNaN(cashCents) ? Number.NaN : cashCents - totalCents;
  const canPay =
    cart.length > 0 &&
    !isPending &&
    (method === "cash" ? !Number.isNaN(cashCents) && changeCents >= 0 : reference.trim().length > 0);

  useEffect(() => () => clearTimeout(debounce.current), []);

  function changed() {
    checkoutKey.current = null;
    setError(null);
  }

  function addToCart(product: Product) {
    if (product.stock_on_hand <= 0) {
      setSearch({ status: "message", text: `${product.name} is out of stock.`, tone: "error" });
      return;
    }
    changed();
    setCart((lines) => {
      const existing = lines.find((line) => line.product.id === product.id);
      if (!existing) return [...lines, { product, quantity: 1 }];
      return lines.map((line) =>
        line.product.id === product.id
          ? { ...line, quantity: Math.min(line.quantity + 1, product.stock_on_hand) }
          : line,
      );
    });
    setAnnouncement(`Added ${product.name}.`);
    setQuery("");
    setSearch({ status: "idle" });
    searchRef.current?.focus();
  }

  function setQuantity(productId: string, quantity: number) {
    changed();
    setCart((lines) =>
      lines
        .map((line) =>
          line.product.id === productId
            ? { ...line, quantity: Math.max(0, Math.min(quantity, line.product.stock_on_hand)) }
            : line,
        )
        .filter((line) => line.quantity > 0),
    );
  }

  function onQueryChange(value: string) {
    setQuery(value);
    clearTimeout(debounce.current);
    if (!value.trim()) {
      setSearch({ status: "idle" });
      return;
    }
    debounce.current = setTimeout(async () => {
      setSearch({ status: "loading" });
      const result = await fetchProducts({ q: value.trim() }, signedOut);
      if (!result.ok) setSearch({ status: "message", text: result.message ?? "Search failed.", tone: "error" });
      else if (result.items.length === 0) setSearch({ status: "message", text: `Nothing matches “${value.trim()}”.`, tone: "info" });
      else setSearch({ status: "results", items: result.items });
    }, 250);
  }

  /** Enter: a barcode scanner "types" the code and presses Enter. Try an exact match first. */
  async function onQueryEnter() {
    const code = query.trim();
    if (!code) return;
    clearTimeout(debounce.current);
    const exact = await fetchProducts({ code }, signedOut);
    if (exact.ok && exact.items[0]) return addToCart(exact.items[0]);
    if (search.status === "results" && search.items.length === 1) return addToCart(search.items[0]!);
    setSearch({
      status: "message",
      text: exact.status === 404 ? `No product with barcode or SKU “${code}”.` : (exact.message ?? "Lookup failed."),
      tone: "error",
    });
  }

  function completeSale() {
    if (!canPay) return;
    checkoutKey.current ??= crypto.randomUUID();
    const input: CheckoutInput = {
      lines: cart.map((line) => ({ product_id: line.product.id, quantity: line.quantity })),
      payment_method: method,
      amount_tendered: method === "cash" ? (cashCents / 100).toFixed(2) : undefined,
      payment_reference: method === "e_wallet" ? reference.trim() : undefined,
      idempotency_key: checkoutKey.current,
    };
    startTransition(async () => {
      const result = await checkoutAction(input);
      if (result.status === "success") {
        setSale(result.sale);
        setAnnouncement(`Sale complete. Receipt ${result.sale.receipt_code}.`);
      } else {
        setError({ message: result.message, fields: result.fields });
      }
    });
  }

  function newSale() {
    setSale(null);
    setCart([]);
    setCash("");
    setReference("");
    setMethod("cash");
    setError(null);
    checkoutKey.current = null;
    requestAnimationFrame(() => searchRef.current?.focus());
  }

  if (sale) {
    return <Receipt sale={sale} storeName={storeName} onNewSale={newSale} />;
  }

  return (
    <div className="grid items-start gap-5 pb-24 lg:grid-cols-12 lg:pb-0">
      <p aria-live="polite" className="sr-only">
        {announcement}
      </p>

      {/* ── Find products ─────────────────────────────────────────── */}
      <section aria-labelledby="pos-find" className="grid gap-3 rounded-lg border border-border bg-card p-4 sm:p-5 lg:col-span-7">
        <h2 id="pos-find" className="text-lg font-semibold">
          Scan or search
        </h2>
        <div className="relative">
          <ScanBarcode
            className="pointer-events-none absolute left-3 top-1/2 size-5 -translate-y-1/2 text-muted-foreground"
            strokeWidth={1.5}
            aria-hidden="true"
          />
          <Input
            ref={searchRef}
            type="search"
            aria-label="Scan a barcode or search products"
            aria-describedby="pos-find-hint"
            placeholder="Scan a barcode, or type a name or SKU"
            value={query}
            autoFocus
            autoComplete="off"
            onChange={(event) => onQueryChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                event.preventDefault();
                void onQueryEnter();
              }
            }}
            className="h-12 pl-10 text-base"
          />
        </div>
        <p id="pos-find-hint" className="text-[0.8125rem] text-muted-foreground">
          Press Enter to add an exact barcode or SKU match.
        </p>

        {search.status === "loading" && <p className="py-2 text-sm text-muted-foreground">Searching…</p>}
        {search.status === "message" && (
          <p role={search.tone === "error" ? "alert" : "status"} className={cn("py-2 text-sm", search.tone === "error" ? "text-destructive" : "text-muted-foreground")}>
            {search.text}
          </p>
        )}
        {search.status === "results" && (
          <ul aria-label="Search results" className="grid gap-2 sm:grid-cols-2">
            {search.items.map((product) => {
              const out = product.stock_on_hand <= 0;
              return (
                <li key={product.id}>
                  <button
                    type="button"
                    onClick={() => addToCart(product)}
                    disabled={out}
                    className="flex min-h-16 w-full items-center justify-between gap-3 rounded-sm border border-border bg-background px-3 py-2.5 text-left transition-colors hover:border-primary hover:bg-muted disabled:cursor-not-allowed disabled:opacity-60"
                  >
                    <span className="min-w-0">
                      <span className="block font-medium">{product.name}</span>
                      <span className="block text-xs text-muted-foreground">
                        {product.sku} · {out ? "Out of stock" : `${product.stock_on_hand} ${product.unit} left`}
                      </span>
                    </span>
                    <span className="tabular shrink-0 font-semibold">{formatCents(toCents(product.price))}</span>
                  </button>
                </li>
              );
            })}
          </ul>
        )}
      </section>

      {/* ── Cart and payment ──────────────────────────────────────── */}
      <section aria-labelledby="pos-cart" id="pos-checkout" className="rounded-lg border border-border bg-card lg:sticky lg:top-20 lg:col-span-5">
        <div className="flex items-baseline justify-between border-b border-border px-4 py-3 sm:px-5">
          <h2 id="pos-cart" className="text-lg font-semibold">
            Cart
          </h2>
          <span className="text-sm text-muted-foreground">
            {itemCount} {itemCount === 1 ? "item" : "items"}
          </span>
        </div>

        {cart.length === 0 ? (
          <p className="px-4 py-10 text-center text-muted-foreground sm:px-5">Scan or search to add the first item.</p>
        ) : (
          <ul className="divide-y divide-border">
            {cart.map((line) => {
              const lineError = error?.fields[line.product.id];
              const atMax = line.quantity >= line.product.stock_on_hand;
              return (
                <li key={line.product.id} className="grid gap-2 px-4 py-3 sm:px-5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="font-medium">{line.product.name}</div>
                      <div className="tabular text-xs text-muted-foreground">
                        {formatCents(toCents(line.product.price))} each
                      </div>
                    </div>
                    <div className="tabular font-semibold">
                      {formatCents(toCents(line.product.price) * line.quantity)}
                    </div>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <div className="inline-flex items-center rounded-sm border border-input" role="group" aria-label={`Quantity of ${line.product.name}`}>
                      <Button variant="ghost" size="icon" aria-label={`One less ${line.product.name}`} onClick={() => setQuantity(line.product.id, line.quantity - 1)}>
                        <Minus aria-hidden="true" />
                      </Button>
                      <input
                        type="number"
                        inputMode="numeric"
                        min={1}
                        max={line.product.stock_on_hand}
                        value={line.quantity}
                        aria-label={`Quantity of ${line.product.name}`}
                        onChange={(event) => setQuantity(line.product.id, Number(event.target.value) || 1)}
                        className="tabular h-9 w-12 border-x border-input bg-transparent text-center text-sm [appearance:textfield] [&::-webkit-inner-spin-button]:appearance-none"
                      />
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label={`One more ${line.product.name}`}
                        disabled={atMax}
                        onClick={() => setQuantity(line.product.id, line.quantity + 1)}
                      >
                        <Plus aria-hidden="true" />
                      </Button>
                    </div>
                    <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={() => setQuantity(line.product.id, 0)}>
                      <Trash2 aria-hidden="true" />
                      Remove
                    </Button>
                  </div>
                  {atMax && !lineError && (
                    <p className="text-xs text-muted-foreground">That&apos;s all {line.product.stock_on_hand} in stock.</p>
                  )}
                  {lineError && <p className="text-sm text-destructive">{lineError}</p>}
                </li>
              );
            })}
          </ul>
        )}

        <div className="border-t border-border px-4 py-4 sm:px-5">
          <div className="flex items-baseline justify-between">
            <span className="font-medium">Total</span>
            <span className="tabular font-display text-kpi font-semibold">{formatCents(totalCents)}</span>
          </div>
        </div>

        <fieldset className="grid gap-3 border-t border-border px-4 py-4 sm:px-5" disabled={cart.length === 0}>
          <legend className="sr-only">Payment</legend>
          <div className="grid grid-cols-2 gap-1 rounded-sm border border-input p-1" role="radiogroup" aria-label="Payment method">
            {(
              [
                ["cash", "Cash"],
                ["e_wallet", "E-wallet"],
              ] as const
            ).map(([value, label]) => (
              <label
                key={value}
                className={cn(
                  "flex h-10 cursor-pointer items-center justify-center rounded-[4px] text-sm font-medium has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-ring",
                  method === value ? "bg-primary text-primary-foreground" : "text-muted-foreground hover:bg-muted",
                )}
              >
                <input
                  type="radio"
                  name="payment-method"
                  value={value}
                  checked={method === value}
                  onChange={() => {
                    changed();
                    setMethod(value);
                  }}
                  className="sr-only"
                />
                {label}
              </label>
            ))}
          </div>

          {method === "cash" ? (
            <>
              <label className="grid gap-1.5">
                <span className="text-sm font-medium">Cash received (₱)</span>
                <Input
                  inputMode="decimal"
                  value={cash}
                  placeholder="0.00"
                  onChange={(event) => {
                    changed();
                    setCash(event.target.value);
                  }}
                  aria-invalid={Boolean(error?.fields.amount_tendered)}
                  className="tabular h-11 text-base"
                />
              </label>
              {totalCents > 0 && (
                <div className="flex flex-wrap gap-2" aria-label="Quick cash amounts">
                  {quickCashAmounts(totalCents).map((amount) => (
                    <Button
                      key={amount}
                      variant="outline"
                      size="sm"
                      className="tabular h-9"
                      onClick={() => {
                        changed();
                        setCash((amount / 100).toFixed(2));
                      }}
                    >
                      {amount === totalCents ? "Exact" : formatCents(amount)}
                    </Button>
                  ))}
                </div>
              )}
              <div className="flex items-baseline justify-between" aria-live="polite">
                {Number.isNaN(changeCents) ? (
                  <span className="text-sm text-muted-foreground">Enter the cash received to see the change.</span>
                ) : changeCents >= 0 ? (
                  <>
                    <span className="font-medium">Change</span>
                    <span className="tabular font-display text-2xl font-semibold text-success">{formatCents(changeCents)}</span>
                  </>
                ) : (
                  <span className="text-sm font-medium text-destructive">Short by {formatCents(-changeCents)}</span>
                )}
              </div>
            </>
          ) : (
            <label className="grid gap-1.5">
              <span className="text-sm font-medium">Reference number</span>
              <Input
                value={reference}
                maxLength={64}
                autoComplete="off"
                placeholder="From the GCash or Maya confirmation"
                onChange={(event) => {
                  changed();
                  setReference(event.target.value);
                }}
                className="h-11 text-base"
              />
            </label>
          )}

          {error && (
            <p role="alert" className="rounded-sm border border-destructive/40 bg-destructive/5 px-3 py-2.5 text-sm text-destructive">
              {error.message}
            </p>
          )}

          <Button size="lg" className="h-12 w-full text-base" disabled={!canPay} onClick={completeSale}>
            {isPending ? "Recording sale…" : `Complete sale · ${formatCents(totalCents)}`}
          </Button>
        </fieldset>
      </section>

      {/* ── Phone: total stays visible while scrolling through search results ── */}
      {cart.length > 0 && (
        <div className="fixed inset-x-0 bottom-0 z-30 flex items-center justify-between gap-3 border-t border-border bg-card px-4 py-3 lg:hidden">
          <div>
            <div className="text-xs text-muted-foreground">
              {itemCount} {itemCount === 1 ? "item" : "items"}
            </div>
            <div className="tabular font-display text-xl font-semibold">{formatCents(totalCents)}</div>
          </div>
          <Button size="lg" asChild>
            <a href="#pos-checkout">Pay</a>
          </Button>
        </div>
      )}
    </div>
  );
}
