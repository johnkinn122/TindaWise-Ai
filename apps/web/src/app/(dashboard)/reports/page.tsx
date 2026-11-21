import type { Metadata } from "next";
import { BarChart3 } from "lucide-react";
import { PlannedModule } from "@/components/dashboard/planned-module";

export const metadata: Metadata = {
  title: "Reports",
};

export default function ReportsPage() {
  return (
    <PlannedModule
      title="Reports"
      icon={BarChart3}
      summary="Track revenue, costs, and profit over time, with demand forecasts once there is enough sales history."
    />
  );
}
