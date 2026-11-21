import type { Metadata } from "next";
import { Package } from "lucide-react";
import { PlannedModule } from "@/components/dashboard/planned-module";

export const metadata: Metadata = {
  title: "Products",
};

export default function ProductsPage() {
  return (
    <PlannedModule
      title="Products"
      icon={Package}
      summary="Add products with prices, barcodes, and categories, and keep them organized as your store grows."
    />
  );
}
