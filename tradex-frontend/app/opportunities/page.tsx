import { getOpportunities, getOpportunitySummary, type Opportunity } from "@/lib/api";

function SetupBadge({ type }: { type: string }) {
  const styles: Record<string, string> = {
    sniper_long: "bg-emerald-900/50 text-emerald-400 border-emerald-800",
    sniper_short: "bg-red-900/50 text-red-400 border-red-800",
    retrace_long: "bg-teal-900/50 text-teal-400 border-teal-800",
    retrace_short: "bg-orange-900/50 text-orange-400 border-orange-800",
  };
  const labels: Record<string, string> = {
    sniper_long: "⊕ Sniper Long",
    sniper_short: "⊖ Sniper Short",
    retrace_long: "↩ Retrace Long",
    retrace_short: "↪ Retrace Short",
  };
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${styles[type] || "bg-zinc-800 text-zinc-400 border-zinc-700"}`}>
      {labels[type] || type}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    identified: "bg-blue-900/50 text-blue-400",
    active: "bg-cyan-900/50 text-cyan-400",
    tp_hit: "bg-emerald-900/50 text-emerald-400",
    sl_hit: "bg-red-900/50 text-red-400",
    expired: "bg-amber-900/50 text-amber-400",
  };
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${styles[status] || "bg-zinc-800 text-zinc-400"}`}>
      {status?.toUpperCase() || "UNKNOWN"}
    </span>
  );
}

function OppRow({ o }: { o: Opportunity }) {
  const isLong = o.setup_type.includes("long");
  const ts = o.identified_at ? new Date(o.identified_at).toLocaleString() : "—";
  return (
    <tr className="border-b border-zinc-800 hover:bg-zinc-800/50 transition-colors">
      <td className="px-3 py-2 text-xs text-zinc-500">{ts}</td>
      <td className="px-3 py-2 font-mono font-semibold">{o.pair}</td>
      <td className="px-3 py-2"><SetupBadge type={o.setup_type} /></td>
      <td className="px-3 py-2">
        <span className={isLong ? "text-emerald-400" : "text-red-400"}>
          {o.h4_bias === "Bullish" ? "▲" : o.h4_bias === "Bearish" ? "▼" : "—"} {o.h4_bias}
        </span>
      </td>
      <td className="px-3 py-2">
        <span className={`rounded px-1.5 py-0.5 text-xs ${
          o.pd_zone === "Premium" ? "bg-red-900/30 text-red-400" :
          o.pd_zone === "Discount" ? "bg-emerald-900/30 text-emerald-400" :
          "bg-amber-900/30 text-amber-400"
        }`}>{o.pd_zone}</span>
      </td>
      <td className="px-3 py-2 text-xs">{o.kill_zone}</td>
      <td className="px-3 py-2 text-xs">{o.guardian}</td>
      <td className="px-3 py-2 font-mono text-xs">{o.entry_price}</td>
      <td className="px-3 py-2 font-mono text-xs text-red-400">{o.sl_price}</td>
      <td className="px-3 py-2 font-mono text-xs text-emerald-400">{o.tp_price}</td>
      <td className="px-3 py-2 font-mono font-semibold">{o.rr_ratio?.toFixed(1)}:1</td>
      <td className="px-3 py-2 text-center">{o.poi_score ?? "—"}</td>
      <td className="px-3 py-2"><StatusBadge status={o.status} /></td>
    </tr>
  );
}

export default async function OpportunitiesPage() {
  let opps: Opportunity[] = [];
  let total = 0;
  let summary: Record<string, any> = {};

  try {
    const data = await getOpportunities({ limit: "100" });
    opps = data.opportunities;
    total = data.total;
  } catch {}
  try {
    summary = await getOpportunitySummary();
  } catch {}

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Opportunity Intelligence Engine</h1>
          <p className="text-sm text-zinc-500">
            v17.20 decoded opportunities — {total} total across all pairs
          </p>
        </div>
      </div>

      {/* Summary Row */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-6">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
          <div className="text-xs text-zinc-500 uppercase">Total</div>
          <div className="text-xl font-bold font-mono">{summary.total || 0}</div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
          <div className="text-xs text-zinc-500 uppercase">Avg R:R</div>
          <div className="text-xl font-bold font-mono text-cyan-400">{(summary.avg_rr || 0).toFixed(1)}</div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
          <div className="text-xs text-zinc-500 uppercase">Win Rate</div>
          <div className={`text-xl font-bold font-mono ${(summary.win_rate || 0) >= 50 ? "text-emerald-400" : "text-red-400"}`}>
            {(summary.win_rate || 0).toFixed(1)}%
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
          <div className="text-xs text-zinc-500 uppercase">Sniper</div>
          <div className="text-xl font-bold font-mono text-emerald-400">{summary.sniper_count || 0}</div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
          <div className="text-xs text-zinc-500 uppercase">Retrace</div>
          <div className="text-xl font-bold font-mono text-amber-400">{summary.retrace_count || 0}</div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
          <div className="text-xs text-zinc-500 uppercase">TP / SL</div>
          <div className="text-xl font-bold font-mono">
            <span className="text-emerald-400">{summary.tp_hits || 0}</span>
            <span className="text-zinc-600 mx-1">/</span>
            <span className="text-red-400">{summary.sl_hits || 0}</span>
          </div>
        </div>
      </div>

      {/* Opportunities Table */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700 text-left text-xs uppercase tracking-wider text-zinc-500">
                <th className="px-3 py-3">Time</th>
                <th className="px-3 py-3">Pair</th>
                <th className="px-3 py-3">Setup</th>
                <th className="px-3 py-3">H4 Bias</th>
                <th className="px-3 py-3">P&D Zone</th>
                <th className="px-3 py-3">Kill Zone</th>
                <th className="px-3 py-3">Guardian</th>
                <th className="px-3 py-3">Entry</th>
                <th className="px-3 py-3">SL</th>
                <th className="px-3 py-3">TP</th>
                <th className="px-3 py-3">R:R</th>
                <th className="px-3 py-3 text-center">POI</th>
                <th className="px-3 py-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {opps.length === 0 ? (
                <tr>
                  <td colSpan={13} className="px-3 py-12 text-center text-zinc-500">
                    No opportunities yet. Configure v17.20 TradingView alerts to get started!
                  </td>
                </tr>
              ) : (
                opps.map((o) => <OppRow key={o.id} o={o} />)
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
