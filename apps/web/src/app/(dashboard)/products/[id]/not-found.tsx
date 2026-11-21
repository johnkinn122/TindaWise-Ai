import Link from "next/link";
import { Button } from "@/components/ui/button";

export default function ProductNotFound() {
  return (
    <div className="grid place-items-center rounded-lg border border-border bg-card px-6 py-16 text-center">
      <h1 className="font-display text-xl font-semibold">Product not found</h1>
      <p className="mt-1.5 max-w-md text-muted-foreground">
        It may have been removed, or the link is wrong. Find it from your product list.
      </p>
      <Button variant="outline" className="mt-5" asChild>
        <Link href="/products">Go to products</Link>
      </Button>
    </div>
  );
}
