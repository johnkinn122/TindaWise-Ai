"use client";

import { Search } from "lucide-react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState, useTransition } from "react";
import { Input } from "@/components/ui/input";
import type { Category } from "@/lib/api/types";
import { sortOptions, stockStatusOptions } from "@/lib/products";
import { cn } from "@/lib/utils";

const selectClass =
  "h-9 rounded-sm border border-input bg-card px-2.5 text-sm text-foreground disabled:opacity-50";

/**
 * Search, status, category and sort live in the URL, so a filtered view can be bookmarked,
 * shared, and restored with the back button.
 */
export function ProductFilters({ categories }: { categories: Category[] }) {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const [isPending, startTransition] = useTransition();
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const debounce = useRef<ReturnType<typeof setTimeout>>(undefined);

  function update(key: string, value: string) {
    const params = new URLSearchParams(searchParams.toString());
    if (value) params.set(key, value);
    else params.delete(key);
    params.delete("page"); // a new filter starts from the first page
    startTransition(() => router.replace(`${pathname}?${params.toString()}`, { scroll: false }));
  }

  function onSearch(value: string) {
    setQuery(value);
    clearTimeout(debounce.current);
    debounce.current = setTimeout(() => update("q", value.trim()), 300);
  }

  useEffect(() => () => clearTimeout(debounce.current), []);

  return (
    <div
      role="search"
      aria-busy={isPending}
      className={cn("flex flex-wrap items-end gap-3 transition-opacity", isPending && "opacity-70")}
    >
      <div className="grid min-w-56 flex-1 gap-1.5">
        <label htmlFor="product-search" className="text-[0.8125rem] font-medium">
          Search
        </label>
        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted-foreground"
            strokeWidth={1.5}
            aria-hidden="true"
          />
          <Input
            id="product-search"
            type="search"
            value={query}
            onChange={(event) => onSearch(event.target.value)}
            placeholder="Name, SKU or barcode"
            className="h-9 bg-card pl-8"
          />
        </div>
      </div>

      <div className="grid gap-1.5">
        <label htmlFor="filter-status" className="text-[0.8125rem] font-medium">
          Stock
        </label>
        <select
          id="filter-status"
          className={selectClass}
          value={searchParams.get("status") ?? ""}
          onChange={(event) => update("status", event.target.value)}
        >
          <option value="">All</option>
          {stockStatusOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-1.5">
        <label htmlFor="filter-category" className="text-[0.8125rem] font-medium">
          Category
        </label>
        <select
          id="filter-category"
          className={selectClass}
          value={searchParams.get("category") ?? ""}
          onChange={(event) => update("category", event.target.value)}
        >
          <option value="">All</option>
          {categories.map((category) => (
            <option key={category.id} value={category.id}>
              {category.name}
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-1.5">
        <label htmlFor="filter-sort" className="text-[0.8125rem] font-medium">
          Sort
        </label>
        <select
          id="filter-sort"
          className={selectClass}
          value={searchParams.get("sort") ?? "name"}
          onChange={(event) => update("sort", event.target.value === "name" ? "" : event.target.value)}
        >
          {sortOptions.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}
