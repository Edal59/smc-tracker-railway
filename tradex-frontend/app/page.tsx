import { getHealth, getOpportunitySummary, getMetrics } from "@/lib/api";

interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  color?: string;
}

function StatCard({ label, value, subtitle, color = "text-white" }: StatCardProps) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5 hover:shadow-md transition-shadow">
      <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">{label}</span>
      <div className={`mt-1 font-mono text-2xl font-bold ${color}`}>{value}</div>
      {subtitle && <span className="text-xs text-zinc-500">{subtitle}</span>}
    </div>
  );
}

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

function BiasBadge({ bias }: { bias: string }) {
  if (bias === "Bullish") return <span className="text-emerald-400 font-semibold">▲ Bullish</span>;
  if (bias === "Bearish") return <span className="text-red-400 font-semibold">▼ Bearish</span>;
  return <span className="text-zinc-500">— Neutral</span>;
}

function ZoneBadge({ zone }: { zone: string }) {
  const styles: Record<string, string> = {
    Premium: "bg-red-900/30 text-red-400",
    Discount: "bg-emerald-900/30 text-emerald-400",
    Equilibrium: "bg-amber-900/30 text-amber-400",
  };
  return (
    <span className={`rounded px-1.5 py-0.5 text-xs font-medium ${styles[zone] || "text-zinc-500"}`}>
      {zone || "Unknown"}
    </span>
  );
}

function KzBadge({ kz }: { kz: string }) {
  const styles: Record<string, string> = {
    London: "text-blue-400",
    "NY AM": "text-cyan-400",
    "NY PM": "text-amber-400",
    Asian: "text-purple-400",
  };
  return <span className={`text-xs font-medium ${styles[kz] || "text-zinc-500"}`}>{kz || "Off-Session"}</span>;
}

export default async function DashboardPage() {
  let health = { version: "unknown", status: "unknown" };
  let summary: Record<string, any> = {};
  let metrics: Record<string, any> = {};

  try { health = await getHealth(); } catch {}
  try { summary = await getOpportunitySummary(); } catch {}
  try { metrics = await getMetrics({ days: "30" }); } catch {}

  const metricsSummary = metrics?.summary || {};
  const sniperCount = summary.sniper_count || 0;
  const retraceCount = summary.retrace_count || 0;
  const totalOpps = summary.total || 0;
  const avgRR = (summary.avg_rr || 0).toFixed(1);
  const winRate = (summary.win_rate || 0).toFixed(1);
  const activeCount = (summary.identified || 0) + (summary.active || 0);

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Performance Dashboard</h1>
          <p className="text-sm text-zinc-500">
            Real-time v17.17 OIE tracking — kill zones, H4 bias, P&D zones, guardian confluence.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <span className="font-mono">Backend:</span>
          <span className={`font-mono ${health.status === "ok" ? "text-emerald-400" : "text-red-400"}`}>
            {health.version}
          </span>
        </div>
      </div>

      {/* OIE Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
        <StatCard label="Total Opportunities" value={totalOpps} />
        <StatCard label="Avg R:R" value={`${avgRR}:1`} color="text-cyan-400" />
        <StatCard label="Win Rate" value={`${winRate}%`} color={parseFloat(winRate) >= 50 ? "text-emerald-400" : "text-red-400"} />
        <StatCard label="Sniper Setups" value={sniperCount} color="text-emerald-400" subtitle="⊕ Precision entries" />
        <StatCard label="Retrace Setups" value={retraceCount} color="text-amber-400" subtitle="↩ Pullback entries" />
        <StatCard label="Active" value={activeCount} color="text-blue-400" subtitle="Open opportunities" />
      </div>

      {/* Legacy Metrics (from signals pipeline) */}
      {metricsSummary.total_signals > 0 && (
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6 mb-8">
          <h2 className="text-lg font-semibold mb-4">Legacy Signals Performance (30d)</h2>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
            <StatCard label="Total Signals" value={metricsSummary.total_signals || 0} />
            <StatCard
              label="Win Rate"
              value={`${(metricsSummary.win_rate || 0).toFixed(1)}%`}
              color={(metricsSummary.win_rate || 0) >= 50 ? "text-emerald-400" : "text-red-400"}
            />
            <StatCard label="W / L" value={`${metricsSummary.wins || 0} / ${metricsSummary.losses || 0}`} />
            <StatCard
              label="Expectancy"
              value={`${(metricsSummary.expectancy || 0).toFixed(2)}R`}
              color={(metricsSummary.expectancy || 0) >= 0 ? "text-emerald-400" : "text-red-400"}
            />
            <StatCard label="Profit Factor" value={(metricsSummary.profit_factor || 0).toFixed(2)} />
          </div>
        </div>
      )}

      {/* Architecture Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
          <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">System Architecture</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-zinc-500">Pine Script</span><span className="font-mono text-emerald-400">v17.17</span></div>
            <div className="flex justify-between"><span className="text-zinc-500">Alert Types</span><span className="font-mono">4 (Sniper + Retrace × Long/Short)</span></div>
            <div className="flex justify-between"><span className="text-zinc-500">Currency Pairs</span><span className="font-mono">9</span></div>
            <div className="flex justify-between"><span className="text-zinc-500">Active Alerts</span><span className="font-mono">36</span></div>
            <div className="flex justify-between"><span className="text-zinc-500">Trigger</span><span className="font-mono">Bar Close Only</span></div>
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
          <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">OIE Decode Pipeline</h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between"><span className="text-zinc-500">Webhook Decoder</span><span className="text-emerald-400">Numeric → Human Readable</span></div>
            <div className="flex justify-between"><span className="text-zinc-500">OIE Engine</span><span>Pip &amp; RR Calculations</span></div>
            <div className="flex justify-between"><span className="text-zinc-500">Storage</span><span className="font-mono">SQLite (Railway)</span></div>
            <div className="flex justify-between"><span className="text-zinc-500">Backend</span><span className="font-mono text-blue-400">Flask + Gunicorn</span></div>
          </div>
        </div>
      </div>

      {/* Decode Reference */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
        <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-4">v17.17 Decode Reference</h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-sm">
          <div>
            <h4 className="font-semibold text-zinc-300 mb-2">H4 Bias</h4>
            <div className="space-y-1">
              <div><code className="text-emerald-400">1</code> → <BiasBadge bias="Bullish" /></div>
              <div><code className="text-red-400">-1</code> → <BiasBadge bias="Bearish" /></div>
              <div><code className="text-zinc-500">0</code> → <BiasBadge bias="Neutral" /></div>
            </div>
          </div>
          <div>
            <h4 className="font-semibold text-zinc-300 mb-2">P&D Zone</h4>
            <div className="space-y-1">
              <div><code className="text-red-400">1</code> → <ZoneBadge zone="Premium" /></div>
              <div><code className="text-emerald-400">0</code> → <ZoneBadge zone="Discount" /></div>
              <div><code className="text-amber-400">-1</code> → <ZoneBadge zone="Equilibrium" /></div>
            </div>
          </div>
          <div>
            <h4 className="font-semibold text-zinc-300 mb-2">Guardian</h4>
            <div className="space-y-1 text-xs">
              <div><code>1/2</code> → Sniper Buy/Sell</div>
              <div><code>3/4</code> → Retrace Buy/Sell</div>
              <div><code>5/6</code> → Trap Buy/Sell</div>
              <div><code>0</code> → Waiting</div>
            </div>
          </div>
          <div>
            <h4 className="font-semibold text-zinc-300 mb-2">Kill Zone</h4>
            <div className="space-y-1">
              <div><code>1</code> → <KzBadge kz="London" /></div>
              <div><code>2</code> → <KzBadge kz="NY AM" /></div>
              <div><code>3</code> → <KzBadge kz="NY PM" /></div>
              <div><code>4</code> → <KzBadge kz="Asian" /></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
