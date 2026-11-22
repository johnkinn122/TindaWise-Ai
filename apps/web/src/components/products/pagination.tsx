import { ChevronLeft, ChevronRight } from "lucide-react";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { formatNumber } from "@/lib/format";

interface PaginationProps {
  page: number;
  pageSize: number;
  total: number;
  /** Current query string without the page, so filters are kept. */
  searchParams: Record<string, string>;
  /** List page the links point to. */
  basePath?: string;
}

function hrefFor(page: number, searchParams: Record<string, string>, basePath: string) {
  const params = new URLSearchParams(searchParams);
  if (page > 1) params.set("page", String(page));
  else params.delete("page");
  const query = params.toString();
  return query ? `${basePath}?${query}` : basePath;
}

export function Pagination({ page, pageSize, total, searchParams, basePath = "/products" }: PaginationProps) {
  const lastPage = Math.max(1, Math.ceil(total / pageSize));
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1;
  const to = Math.min(page * pageSize, total);

  return (
    <nav aria-label="Pagination" className="flex items-center justify-between gap-3 px-4 py-3 sm:px-5">
      <p className="tabular text-[0.8125rem] text-muted-foreground">
        {formatNumber(from)}–{formatNumber(to)} of {formatNumber(total)}
      </p>
      <div className="flex gap-2">
        {page > 1 ? (
          <Button variant="outline" asChild>
            <Link href={hrefFor(page - 1, searchParams, basePath)}>
              <ChevronLeft aria-hidden="true" />
              Previous
            </Link>
          </Button>
        ) : (
          <Button variant="outline" disabled>
            <ChevronLeft aria-hidden="true" />
            Previous
          </Button>
        )}
        {page < lastPage ? (
          <Button variant="outline" asChild>
            <Link href={hrefFor(page + 1, searchParams, basePath)}>
              Next
              <ChevronRight aria-hidden="true" />
            </Link>
          </Button>
        ) : (
          <Button variant="outline" disabled>
            Next
            <ChevronRight aria-hidden="true" />
          </Button>
        )}
      </div>
    </nav>
  );
}
