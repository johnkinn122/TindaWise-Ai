import { ApiUnavailableError } from "@/lib/api/client";
import { getAnomalies } from "@/lib/api/anomalies";
import { formatNumber } from "@/lib/format";
import { Panel } from "./panel";
import { WorthALookList } from "./worth-a-look-list";

/**
 * Unusual sales days from the last week (services/api/app/services/anomalies.py), for owners and
 * managers. Like the reorder card, a plain Panel rather than the Resibo card: the rule is a
 * ratio against a recent average, not a model, and the receipt look is kept for AI output
 * (MASTER.md §7).
 *
 * Fetches on its own behind Suspense, so a slow check never holds up the rest of the Overview.
 */
export async function WorthALook() {
  let anomalies;
  try {
    anomalies = await getAnomalies();
  } catch (error) {
    if (error instanceof ApiUnavailableError) {
      return (
        <Panel title="Worth a look">
          <p role="alert" className="px-4 py-5 text-[0.8125rem] text-muted-foreground sm:px-5">
            Can&apos;t check recent sales right now. The Tindawise API isn&apos;t responding.
          </p>
        </Panel>
      );
    }
    throw error;
  }

  const { alerts, stock_losses: losses, window_days: windowDays } = anomalies;
  const dismissedCount = anomalies.dismissed_count + anomalies.stock_losses_dismissed;

  return (
    <Panel title="Worth a look">
      <WorthALookList alerts={alerts} losses={losses} />
      <div className="grid gap-1.5 border-t border-border px-4 pb-4 pt-3 text-xs text-muted-foreground sm:px-5">
        <p>
          Sales days: each product&apos;s sales are compared with its average on days it was in stock over the previous{" "}
          {windowDays} days. A big day can be a bulk buyer or a sale rung up twice. Nothing sold while in stock can mean
          sales weren&apos;t recorded.
        </p>
        <p>
          Missing stock: what your stock count corrections removed over the last 8 weeks, against units sold. Damage you
          recorded doesn&apos;t count. It can mean theft, damage nobody wrote down, or short deliveries, and it only
          shows if you count stock regularly.
        </p>
        {dismissedCount > 0 && (
          <p>{dismissedCount === 1 ? "1 alert" : `${formatNumber(dismissedCount)} alerts`} already dismissed.</p>
        )}
      </div>
    </Panel>
  );
}
