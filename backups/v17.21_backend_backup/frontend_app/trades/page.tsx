import { getSignals, getMetrics, type Signal } from "@/lib/api";

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    ACTIVE: "bg-blue-900/50 text-blue-400",
    WON: "bg-emerald-900/50 text-emerald-400",
    LOST: "bg-red-900/50 text-red-400",
    TIMEOUT: "bg-amber-900/50 text-amber-400",
    GET_OUT: "bg-purple-900/50 text-purple-400",
  };
  return (
    <span className={`rounded px-2 py-0.5 text-xs font-medium ${styles[status] || "bg-zinc-800 text-zinc-400"}`}>
      {status}
    </span>
  );
}

function SignalRow({ s }: { s: Signal }) {
  const isLong = s.direction === "LONG";
  const ts = s.signal_timestamp ? new Date(s.signal_timestamp).toLocaleString() : "—";
  const rrText = s.actual_rr != null ? `${s.actual_rr >= 0 ? "+" : ""}${s.actual_rr.toFixed(2)}R` : "—";
  const pipsText = s.pips_gained != null ? `${s.pips_gained >= 0 ? "+" : ""}${s.pips_gained.toFixed(1)}` : "—";

  return (
    <tr className="border-b border-zinc-800 hover:bg-zinc-800/50 transition-colors">
      <td className="px-3 py-2 text-xs text-zinc-500">{ts}</td>
      <td className="px-3 py-2 font-mono font-semibold">{s.pair}</td>
      <td className={`px-3 py-2 font-semibold ${isLong ? "text-emerald-400" : "text-red-400"}`}>{s.direction}</td>
      <td className="px-3 py-2 text-xs">{s.signal_type || "—"}</td>
      <td className="px-3 py-2 font-mono text-xs">{s.entry_price || "—"}</td>
      <td className="px-3 py-2 font-mono text-xs text-red-400">{s.stop_loss || "—"}</td>
      <td className="px-3 py-2 font-mono text-xs text-emerald-400">{s.take_profit || "—"}</td>
      <td className="px-3 py-2 text-center">{s.poi_score != null ? `${s.poi_score}/7` : "—"}</td>
      <td className="px-3 py-2"><StatusBadge status={s.status} /></td>
      <td className={`px-3 py-2 font-mono font-semibold ${
        s.actual_rr != null ? (s.actual_rr >= 0 ? "text-emerald-400" : "text-red-400") : "text-zinc-500"
      }`}>{rrText}</td>
      <td className="px-3 py-2 font-mono text-xs">{pipsText}</td>
    </tr>
  );
}

export default async function TradesPage() {
  let signals: Signal[] = [];
  let total = 0;
  let metrics: Record<string, any> = {};

  try {
    const data = await getSignals({ limit: "100" });
    signals = data.signals;
    total = data.total;
  } catch {}
  try {
    metrics = await getMetrics();
  } catch {}

  const summary = metrics?.summary || {};

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Trade Log</h1>
          <p className="text-sm text-zinc-500">{total} signals tracked via legacy pipeline</p>
        </div>
      </div>

      {/* Quick Stats */}
      {summary.total_signals > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
            <div className="text-xs text-zinc-500 uppercase">Total</div>
            <div className="text-xl font-bold">{summary.total_signals}</div>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
            <div className="text-xs text-zinc-500 uppercase">Win Rate</div>
            <div className={`text-xl font-bold ${(summary.win_rate || 0) >= 50 ? "text-emerald-400" : "text-red-400"}`}>
              {(summary.win_rate || 0).toFixed(1)}%
            </div>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
            <div className="text-xs text-zinc-500 uppercase">W / L</div>
            <div className="text-xl font-bold">{summary.wins || 0} / {summary.losses || 0}</div>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
            <div className="text-xs text-zinc-500 uppercase">Expectancy</div>
            <div className={`text-xl font-bold ${(summary.expectancy || 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}>
              {(summary.expectancy || 0).toFixed(2)}R
            </div>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
            <div className="text-xs text-zinc-500 uppercase">Profit Factor</div>
            <div className="text-xl font-bold">{(summary.profit_factor || 0).toFixed(2)}</div>
          </div>
        </div>
      )}

      {/* Signals Table */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-zinc-700 text-left text-xs uppercase tracking-wider text-zinc-500">
                <th className="px-3 py-3">Time</th>
                <th className="px-3 py-3">Pair</th>
                <th className="px-3 py-3">Dir</th>
                <th className="px-3 py-3">Type</th>
                <th className="px-3 py-3">Entry</th>
                <th className="px-3 py-3">SL</th>
                <th className="px-3 py-3">TP</th>
                <th className="px-3 py-3 text-center">POI</th>
                <th className="px-3 py-3">Status</th>
                <th className="px-3 py-3">R:R</th>
                <th className="px-3 py-3">Pips</th>
              </tr>
            </thead>
            <tbody>
              {signals.length === 0 ? (
                <tr>
                  <td colSpan={11} className="px-3 py-12 text-center text-zinc-500">
                    No signals yet. Alerts will appear here once the backend receives webhooks.
                  </td>
                </tr>
              ) : (
                signals.map((s) => <SignalRow key={s.signal_id} s={s} />)
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
