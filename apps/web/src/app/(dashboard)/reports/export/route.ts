import { type NextRequest, NextResponse } from "next/server";
import { ApiError, ApiUnavailableError } from "@/lib/api/client";
import { getSalesReport } from "@/lib/api/reports";
import { type ExportKind, exportKinds, parseReportParams, reportCsv } from "@/lib/reports";

/**
 * CSV download for one part of the report: /reports/export?kind=products&preset=last_7_days.
 * Runs on the server with the signed-in session; the API refuses cashiers (403), so they get
 * no file. Products are exported in full, not just the top 10 on screen.
 */
export async function GET(request: NextRequest) {
  const search = request.nextUrl.searchParams;
  const kind = search.get("kind") as ExportKind | null;
  if (!kind || !exportKinds.includes(kind)) {
    return NextResponse.json({ error: { code: "bad_request", message: "Unknown export." } }, { status: 400 });
  }
  const params = parseReportParams(Object.fromEntries(search.entries()));

  try {
    const report = await getSalesReport({ ...params, top: kind === "products" ? 500 : undefined });
    const { filename, body } = reportCsv(report, kind);
    return new NextResponse(body, {
      headers: {
        "Content-Type": "text/csv; charset=utf-8",
        "Content-Disposition": `attachment; filename="${filename}"`,
        "Cache-Control": "no-store",
      },
    });
  } catch (error) {
    if (error instanceof ApiError) {
      return NextResponse.json({ error: { code: error.code, message: error.message } }, { status: error.status });
    }
    if (error instanceof ApiUnavailableError) {
      return NextResponse.json({ error: { code: "unavailable", message: "Can't reach Tindawise right now." } }, { status: 503 });
    }
    throw error;
  }
}
