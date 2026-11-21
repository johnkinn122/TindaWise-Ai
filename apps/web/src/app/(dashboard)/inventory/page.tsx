import type { Metadata } from "next";
import { Boxes } from "lucide-react";
import { PlannedModule } from "@/components/dashboard/planned-module";

export const metadata: Metadata = {
  title: "Inventory",
};

export default function InventoryPage() {
  return (
    <PlannedModule
      title="Inventory"
      icon={Boxes}
      summary="See stock on hand for every product, record adjustments, and review the full history of stock movements."
    />
  );
}
