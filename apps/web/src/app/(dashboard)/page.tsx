import type { Metadata } from "next";
import { KpiStrip } from "@/components/dashboard/kpi-strip";
import { PageHeader } from "@/components/dashboard/page-header";
import { Panel } from "@/components/dashboard/panel";
import { ResiboCard } from "@/components/dashboard/resibo-card";
import { SalesChart } from "@/components/dashboard/sales-chart";
import { SampleDataBadge } from "@/components/dashboard/sample-data-badge";
import { StockTable } from "@/components/dashboard/stock-table";
import {
  sampleKpis,
  sampleReorderSuggestion,
  sampleStockToWatch,
  sampleWeeklySales,
} from "@/lib/sample-data";

export const metadata: Metadata = {
  title: "Overview",
};

export default function OverviewPage() {
  return (
    <div className="grid gap-5">
      <PageHeader
        title="Overview"
        description={
          <span className="inline-flex flex-wrap items-center gap-2">
            What is selling, what is running low, and what to do next.
            <SampleDataBadge />
          </span>
        }
      />

      <KpiStrip kpis={sampleKpis} />

      <div className="grid items-start gap-5 lg:grid-cols-12">
        <div className="grid min-w-0 gap-5 lg:col-span-8">
          <SalesChart
            data={sampleWeeklySales}
            summary="Sales this week are running about 12 percent above last week. Saturday is forecast at 21,000 pesos."
          />
          <Panel title="Stock to watch">
            <StockTable items={sampleStockToWatch} />
          </Panel>
        </div>
        {/* On small screens the AI suggestion comes right after the KPIs: it is the "what to do next". */}
        <div className="order-first min-w-0 lg:order-none lg:col-span-4">
          <ResiboCard suggestion={sampleReorderSuggestion} />
        </div>
      </div>
    </div>
  );
}
