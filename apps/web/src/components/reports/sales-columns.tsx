"use client";

import { useState } from "react";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Panel } from "@/components/dashboard/panel";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { compactPeso, niceTicks } from "@/lib/chart";
import { formatNumber, formatPeso, formatPesoWhole } from "@/lib/format";
import type { SeriesRow } from "@/lib/reports";

interface SalesColumnsProps {
  title: string;
  rows: SeriesRow[];
  /** Plain-language summary for screen readers. */
  summary: string;
  /** First column name in the table view: "Day", "Week of", "Month". */
  bucketName: string;
  action?: React.ReactNode;
}

/**
 * Sales per day/week/month as columns: one measure, so one hue (chart-1) and no legend; the
 * title names it (dataviz: a single series needs no legend box). Columns are capped at 24px with
 * a 4px rounded top, gridlines are hairlines, and "View as table" gives every value without hover.
 */
export function SalesColumns({ title, rows, summary, bucketName, action }: SalesColumnsProps) {
  const [showTable, setShowTable] = useState(false);
  const ticks = niceTicks(Math.max(...rows.map((row) => row.sales), 0));

  return (
    <Panel
      title={title}
      action={
        <div className="flex flex-wrap gap-2">
          {action}
          <Button variant="outline" onClick={() => setShowTable((value) => !value)} aria-pressed={showTable}>
            {showTable ? "View as chart" : "View as table"}
          </Button>
        </div>
      }
    >
      {showTable ? (
        <div className="max-h-96 overflow-auto">
          <Table>
            <TableHeader>
              <TableRow className="hover:bg-transparent">
                <TableHead className="pl-4 sm:pl-5">{bucketName}</TableHead>
                <TableHead className="text-right">Sales</TableHead>
                <TableHead className="text-right">Transactions</TableHead>
                <TableHead className="pr-4 text-right sm:pr-5">Gross profit</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((row) => (
                <TableRow key={row.longLabel}>
                  <TableCell className="pl-4 sm:pl-5">{row.longLabel}</TableCell>
                  <TableCell className="tabular text-right">{formatPeso(row.sales)}</TableCell>
                  <TableCell className="tabular text-right">{formatNumber(row.transactions)}</TableCell>
                  <TableCell className="tabular pr-4 text-right sm:pr-5">{formatPeso(row.grossProfit)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <div className="px-2 pb-3 pt-4 sm:px-4">
          <div role="img" aria-label={summary} className="h-64 sm:h-72">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={rows} margin={{ top: 8, right: 12, bottom: 0, left: 0 }} barCategoryGap="20%">
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis
                  dataKey="label"
                  tickLine={false}
                  axisLine={{ stroke: "var(--border)" }}
                  tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
                  interval="preserveStartEnd"
                  minTickGap={12}
                />
                <YAxis
                  width={52}
                  domain={[0, ticks.at(-1) ?? 0]}
                  ticks={ticks}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={compactPeso}
                  tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
                />
                <Tooltip
                  cursor={{ fill: "var(--muted)", opacity: 0.6 }}
                  content={({ active, payload }) => {
                    const row = active ? (payload?.[0]?.payload as SeriesRow | undefined) : undefined;
                    if (!row) return null;
                    // Values lead, labels follow (dataviz: the reader already knows the series).
                    return (
                      <div className="rounded-sm border border-border bg-popover px-3 py-2 text-[0.8125rem] shadow-[var(--shadow-float-value)]">
                        <p className="tabular text-base font-semibold">{formatPesoWhole(row.sales)}</p>
                        <p className="text-muted-foreground">{row.longLabel}</p>
                        <p className="tabular mt-1 text-muted-foreground">
                          {formatNumber(row.transactions)} {row.transactions === 1 ? "sale" : "sales"} · profit{" "}
                          {formatPesoWhole(row.grossProfit)}
                        </p>
                      </div>
                    );
                  }}
                />
                <Bar
                  dataKey="sales"
                  name="Sales"
                  fill="var(--chart-1)"
                  maxBarSize={24}
                  radius={[4, 4, 0, 0]}
                  isAnimationActive={false}
                />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </Panel>
  );
}
