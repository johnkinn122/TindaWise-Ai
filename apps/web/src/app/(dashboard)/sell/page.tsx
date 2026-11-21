import type { Metadata } from "next";
import { MonitorSmartphone } from "lucide-react";
import { PlannedModule } from "@/components/dashboard/planned-module";

export const metadata: Metadata = {
  title: "Sell",
};

export default function SellPage() {
  return (
    <PlannedModule
      title="Sell"
      icon={MonitorSmartphone}
      summary="Ring up sales by barcode or name, take cash or e-wallet payments, and print receipts. Stock updates with every sale."
    />
  );
}
