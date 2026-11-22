"use client";

import { useState } from "react";
import {
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Button } from "@/components/ui/button";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { formatPeso, formatPesoWhole } from "@/lib/format";
import { compactPeso, niceTicks } from "@/lib/chart";
import type { DailySales } from "@/lib/overview";
import { Panel } from "./panel";

// A forecast series (dashed, so it is never mistaken for actuals) returns with the ML phase.
const series = [
  { key: "thisWeek", label: "This week", color: "var(--chart-1)", dashed: false },
  { key: "lastWeek", label: "Last week", color: "var(--chart-2)", dashed: false },
] as const;


interface SalesChartProps {
  title?: string;
  data: DailySales[];
  /** Plain-language summary of the chart for screen readers. */
  summary: string;
}

/**
 * Weekly sales line chart: this week's actual sales against the same days last week.
 * "View as table" gives an accessible alternative to the chart (MASTER.md §9).
 */
export function SalesChart({ title = "Sales this week", data, summary }: SalesChartProps) {
  const [showTable, setShowTable] = useState(false);
  const ticks = niceTicks(Math.max(...data.flatMap((row) => [row.thisWeek ?? 0, row.lastWeek])));

  return (
    <Panel
      title={title}
      action={
        <Button variant="outline" onClick={() => setShowTable((value) => !value)} aria-pressed={showTable}>
          {showTable ? "View as chart" : "View as table"}
        </Button>
      }
    >
      {showTable ? (
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="pl-4 sm:pl-5">Day</TableHead>
              {series.map((s) => (
                <TableHead key={s.key} className="text-right last:pr-4 sm:last:pr-5">
                  {s.label}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.map((row) => (
              <TableRow key={row.day}>
                <TableCell className="pl-4 sm:pl-5">{row.day}</TableCell>
                {series.map((s) => {
                  const value = row[s.key];
                  return (
                    <TableCell key={s.key} className="text-right last:pr-4 sm:last:pr-5">
                      {value === null ? <span className="text-muted-foreground">—</span> : formatPeso(value)}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      ) : (
        <div className="px-2 pb-3 pt-4 sm:px-4">
          <ul className="mb-2 flex flex-wrap gap-x-4 gap-y-1 px-2 text-xs text-muted-foreground">
            {series.map((s) => (
              <li key={s.key} className="inline-flex items-center gap-1.5">
                <span
                  aria-hidden="true"
                  className="inline-block w-3.5 border-t-2"
                  style={{ borderColor: s.color, borderTopStyle: s.dashed ? "dashed" : "solid" }}
                />
                {s.label}
              </li>
            ))}
          </ul>
          <div role="img" aria-label={summary} className="h-56 sm:h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data} margin={{ top: 8, right: 12, bottom: 0, left: 0 }}>
                <CartesianGrid vertical={false} stroke="var(--border)" />
                <XAxis
                  dataKey="day"
                  tickLine={false}
                  axisLine={false}
                  tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
                />
                <YAxis
                  width={48}
                  domain={[0, ticks.at(-1) ?? 0]}
                  ticks={ticks}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={compactPeso}
                  tick={{ fill: "var(--muted-foreground)", fontSize: 12 }}
                />
                <Tooltip
                  formatter={(value, name) => [formatPesoWhole(Number(value)), name]}
                  contentStyle={{
                    background: "var(--popover)",
                    border: "1px solid var(--border)",
                    borderRadius: "var(--radius-sm)",
                    boxShadow: "var(--shadow-float-value)",
                    fontSize: 13,
                  }}
                  labelStyle={{ color: "var(--foreground)", fontWeight: 600 }}
                  itemStyle={{ color: "var(--foreground)" }}
                  cursor={{ stroke: "var(--border)" }}
                />
                {series.map((s) => (
                  <Line
                    key={s.key}
                    dataKey={s.key}
                    name={s.label}
                    type="monotone"
                    stroke={s.color}
                    strokeWidth={s.key === "thisWeek" ? 2.5 : 2}
                    strokeDasharray={s.dashed ? "6 5" : undefined}
                    // Dots on this week's days, so a week with one day so far still shows a mark.
                    dot={s.key === "thisWeek" ? { r: 3, fill: s.color, strokeWidth: 0 } : false}
                    activeDot={{ r: 4 }}
                    connectNulls={false}
                    isAnimationActive={false}
                  />
                ))}
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}
    </Panel>
  );
}
