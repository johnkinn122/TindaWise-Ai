import type { Metadata } from "next";
import { Truck } from "lucide-react";
import { PlannedModule } from "@/components/dashboard/planned-module";

export const metadata: Metadata = {
  title: "Suppliers",
};

export default function SuppliersPage() {
  return (
    <PlannedModule
      title="Suppliers"
      icon={Truck}
      summary="Keep supplier contacts in one place and create purchase orders. Every order needs your approval before it is sent."
    />
  );
}
