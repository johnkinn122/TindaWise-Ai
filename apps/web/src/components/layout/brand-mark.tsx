import { ShoppingBasket } from "lucide-react";

export function BrandMark() {
  return (
    <span className="flex items-center gap-2.5 font-display text-xl font-bold leading-none">
      <span className="grid size-7 place-items-center rounded-[7px] bg-primary text-primary-foreground">
        <ShoppingBasket className="size-4" strokeWidth={2.2} aria-hidden="true" />
      </span>
      Tindawise
    </span>
  );
}
