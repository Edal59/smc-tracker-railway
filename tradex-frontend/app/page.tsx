"use client";

import { useEffect, useState } from "react";
import {
  getHealth,
  getOpportunitySummary,
  getStats,
  getSessionPerformance,
  type SessionPerformanceResponse,
} from "@/lib/api";

// ─── Reusable Components ──────────────────────────────

interface StatCardProps {
  label: string;
  value: string | number;
  subtitle?: string;
  color?: string;
}

function StatCard({
  label,
  value,
  subtitle,
  color = "text-white",
}: StatCardProps) {
  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-5 hover:shadow-md transition-shadow">
      <span className="text-xs font-medium uppercase tracking-wider text-zinc-500">
        {label}
      </span>
      <div className={`mt-1 font-mono text-2xl font-bold ${color}`}>
        {value}
      </div>
      {subtitle && <span className="text-xs text-zinc-500">{subtitle}</span>}
    </div>
  );
}

function BiasBadge({ bias }: { bias: string }) {
  if (bias === "Bullish")
    return <span className="text-emerald-400 font-semibold">▲ Bullish</span>;
  if (bias === "Bearish")
    return <span className="text-red-400 font-semibold">▼ Bearish</span>;
  return <span className="text-zinc-500">— Neutral</span>;
}

function ZoneBadge({ zone }: { zone: string }) {
  const styles: Record<string, string> = {
    Premium: "bg-red-900/30 text-red-400",
    Discount: "bg-emerald-900/30 text-emerald-400",
    Equilibrium: "bg-amber-900/30 text-amber-400",
  };
  return (
    <span
      className={`rounded px-1.5 py-0.5 text-xs font-medium ${styles[zone] || "text-zinc-500"}`}
    >
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
  return (
    <span className={`text-xs font-medium ${styles[kz] || "text-zinc-500"}`}>
      {kz || "Off-Session"}
    </span>
  );
}

// ─── Session Performance Panel ────────────────────────

function SessionPerformancePanel({
  data,
}: {
  data: SessionPerformanceResponse | null;
}) {
  if (!data) {
    return (
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6 mb-8">
        <h2 className="text-lg font-semibold mb-4">
          📊 Session Performance Comparison
        </h2>
        <p className="text-sm text-zinc-500">
          Loading session data or no EXECUTION trades yet...
        </p>
      </div>
    );
  }

  const { london, ny, comparison } = data;

  function SessionColumn({
    label,
    icon,
    perf,
    accentColor,
    borderColor,
    isBetter,
  }: {
    label: string;
    icon: string;
    perf: typeof london;
    accentColor: string;
    borderColor: string;
    isBetter: boolean;
  }) {
    return (
      <div
        className={`flex-1 rounded-lg border ${borderColor} bg-zinc-900 p-5 ${isBetter ? "ring-1 ring-emerald-600/50" : ""}`}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className={`text-lg font-bold ${accentColor}`}>
            {icon} {label}
          </h3>
          {isBetter && (
            <span className="rounded-full bg-emerald-900/50 text-emerald-400 px-2 py-0.5 text-xs font-medium border border-emerald-700">
              ★ Better
            </span>
          )}
        </div>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between">
            <span className="text-zinc-500">Win Rate</span>
            <span
              className={`font-mono font-bold ${(perf?.win_rate || 0) >= 50 ? "text-emerald-400" : "text-red-400"}`}
            >
              {(perf?.win_rate || 0).toFixed(1)}%
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-zinc-500">Avg R:R</span>
            <span className="font-mono font-bold text-cyan-400">
              {(perf?.avg_rr || 0).toFixed(2)}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-zinc-500">Trades</span>
            <span className="font-mono font-bold">
              {perf?.total_trades || 0}
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-zinc-500">W / L</span>
            <span className="font-mono">
              <span className="text-emerald-400">{perf?.wins || 0}</span>
              <span className="text-zinc-600 mx-1">/</span>
              <span className="text-red-400">{perf?.losses || 0}</span>
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-zinc-500">Expectancy</span>
            <span
              className={`font-mono font-bold ${(perf?.expectancy || 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}
            >
              {(perf?.expectancy || 0).toFixed(2)}R
            </span>
          </div>
          <div className="flex justify-between">
            <span className="text-zinc-500">Best R:R</span>
            <span className="font-mono text-emerald-400">
              {(perf?.best_rr || 0).toFixed(2)}
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-zinc-800 bg-zinc-950 p-6 mb-8">
      <div className="flex items-center justify-between mb-5">
        <h2 className="text-lg font-semibold">
          📊 Session Performance Comparison
        </h2>
        <span className="text-xs text-zinc-500 bg-zinc-800 px-2 py-1 rounded">
          EXECUTION trades only
        </span>
      </div>
      <div className="flex flex-col md:flex-row gap-4">
        <SessionColumn
          label="LONDON"
          icon="🇬🇧"
          perf={london}
          accentColor="text-orange-400"
          borderColor="border-orange-800/50"
          isBetter={comparison?.better_session === "LONDON"}
        />
        <SessionColumn
          label="NEW YORK"
          icon="🗽"
          perf={ny}
          accentColor="text-purple-400"
          borderColor="border-purple-800/50"
          isBetter={comparison?.better_session === "NY"}
        />
      </div>
      {comparison && (
        <div className="mt-4 flex items-center gap-4 text-xs text-zinc-500">
          <span>
            Win rate diff:{" "}
            <span className="font-mono text-zinc-300">
              {Math.abs(comparison.win_rate_diff || 0).toFixed(1)}%
            </span>
          </span>
          <span>
            R:R diff:{" "}
            <span className="font-mono text-zinc-300">
              {Math.abs(comparison.rr_diff || 0).toFixed(2)}
            </span>
          </span>
        </div>
      )}
    </div>
  );
}

// ─── Dashboard Page ───────────────────────────────────

export default function DashboardPage() {
  const [health, setHealth] = useState({ version: "loading...", status: "unknown" });
  const [summary, setSummary] = useState<Record<string, any>>({});
  const [stats, setStats] = useState<Record<string, any>>({});
  const [sessionPerf, setSessionPerf] =
    useState<SessionPerformanceResponse | null>(null);
  const [showDataTrades, setShowDataTrades] = useState(false);

  useEffect(() => {
    async function load() {
      try {
        setHealth(await getHealth());
      } catch {}
      try {
        setSummary(await getOpportunitySummary());
      } catch {}
      try {
        const mode = showDataTrades ? "ALL" : "EXECUTION";
        setStats(await getStats({ mode, days: "30" }));
      } catch {}
      try {
        setSessionPerf(await getSessionPerformance());
      } catch {}
    }
    load();
  }, [showDataTrades]);

  const metricsSummary = stats?.summary || stats || {};
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
            Real-time v17.56.7 OIE tracking — dual-mode alerts, session
            analytics, H4 bias, P&D zones.
          </p>
        </div>
        <div className="flex items-center gap-2 text-xs text-zinc-500">
          <span className="font-mono">Backend:</span>
          <span
            className={`font-mono ${health.status === "ok" ? "text-emerald-400" : "text-red-400"}`}
          >
            {health.version}
          </span>
        </div>
      </div>

      {/* OIE Summary Cards */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4 mb-8">
        <StatCard label="Total Opportunities" value={totalOpps} />
        <StatCard
          label="Avg R:R"
          value={`${avgRR}:1`}
          color="text-cyan-400"
        />
        <StatCard
          label="Win Rate"
          value={`${winRate}%`}
          color={
            parseFloat(winRate) >= 50 ? "text-emerald-400" : "text-red-400"
          }
        />
        <StatCard
          label="Sniper Setups"
          value={sniperCount}
          color="text-emerald-400"
          subtitle="⊕ Precision entries"
        />
        <StatCard
          label="Retrace Setups"
          value={retraceCount}
          color="text-amber-400"
          subtitle="↩ Pullback entries"
        />
        <StatCard
          label="Active"
          value={activeCount}
          color="text-blue-400"
          subtitle="Open opportunities"
        />
      </div>

      {/* Session Performance Comparison */}
      <SessionPerformancePanel data={sessionPerf} />

      {/* EXECUTION Performance with toggle */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6 mb-8">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">
            {showDataTrades ? "All Trades" : "⚡ EXECUTION"} Performance (30d)
          </h2>
          <label className="flex items-center gap-2 cursor-pointer">
            <span className="text-xs text-zinc-500">Show DATA trades</span>
            <div className="relative">
              <input
                type="checkbox"
                checked={showDataTrades}
                onChange={(e) => setShowDataTrades(e.target.checked)}
                className="sr-only"
              />
              <div
                className={`w-9 h-5 rounded-full transition-colors ${showDataTrades ? "bg-blue-600" : "bg-zinc-700"}`}
              />
              <div
                className={`absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-white transition-transform ${showDataTrades ? "translate-x-4" : ""}`}
              />
            </div>
          </label>
        </div>
        {!showDataTrades && (
          <p className="text-xs text-zinc-500 mb-4">
            💡 Showing only EXECUTION-mode trades. Toggle above to include DATA
            signals.
          </p>
        )}
        <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
          <StatCard
            label="Total Signals"
            value={metricsSummary.total_signals || metricsSummary.total_trades || 0}
          />
          <StatCard
            label="Win Rate"
            value={`${(metricsSummary.win_rate || 0).toFixed(1)}%`}
            color={
              (metricsSummary.win_rate || 0) >= 50
                ? "text-emerald-400"
                : "text-red-400"
            }
          />
          <StatCard
            label="W / L"
            value={`${metricsSummary.wins || 0} / ${metricsSummary.losses || 0}`}
          />
          <StatCard
            label="Expectancy"
            value={`${(metricsSummary.expectancy || 0).toFixed(2)}R`}
            color={
              (metricsSummary.expectancy || 0) >= 0
                ? "text-emerald-400"
                : "text-red-400"
            }
          />
          <StatCard
            label="Profit Factor"
            value={(metricsSummary.profit_factor || 0).toFixed(2)}
          />
        </div>
      </div>

      {/* Architecture Info */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
          <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            System Architecture
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-zinc-500">Pine Script</span>
              <span className="font-mono text-emerald-400">v17.56.7</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Alert Modes</span>
              <span className="font-mono">
                DATA + EXECUTION
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Sessions</span>
              <span className="font-mono">London 🇬🇧 + NY 🗽</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Currency Pairs</span>
              <span className="font-mono">9</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Alert Types</span>
              <span className="font-mono">4 (Sniper + Retrace × Long/Short)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Trigger</span>
              <span className="font-mono">Bar Close Only</span>
            </div>
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
          <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">
            v17.56.7 Features
          </h3>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-zinc-500">Dual Mode Alerts</span>
              <span className="text-emerald-400">
                ⚡ EXECUTION / 📊 DATA
              </span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Session Analytics</span>
              <span>🇬🇧 London vs 🗽 NY</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Zombie Prevention</span>
              <span className="text-emerald-400">✓ Active</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">INVALID Classification</span>
              <span className="text-emerald-400">✓ Active</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">POI Scoring</span>
              <span className="font-mono">/6 (OTE bonus)</span>
            </div>
            <div className="flex justify-between">
              <span className="text-zinc-500">Backend</span>
              <span className="font-mono text-blue-400">
                Flask + Gunicorn
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Decode Reference */}
      <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
        <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-4">
          v17.56.7 Decode Reference
        </h3>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-6 text-sm">
          <div>
            <h4 className="font-semibold text-zinc-300 mb-2">H4 Bias</h4>
            <div className="space-y-1">
              <div>
                <code className="text-emerald-400">1</code> →{" "}
                <BiasBadge bias="Bullish" />
              </div>
              <div>
                <code className="text-red-400">-1</code> →{" "}
                <BiasBadge bias="Bearish" />
              </div>
              <div>
                <code className="text-zinc-500">0</code> →{" "}
                <BiasBadge bias="Neutral" />
              </div>
            </div>
          </div>
          <div>
            <h4 className="font-semibold text-zinc-300 mb-2">P&D Zone</h4>
            <div className="space-y-1">
              <div>
                <code className="text-red-400">1</code> →{" "}
                <ZoneBadge zone="Premium" />
              </div>
              <div>
                <code className="text-emerald-400">0</code> →{" "}
                <ZoneBadge zone="Discount" />
              </div>
              <div>
                <code className="text-amber-400">-1</code> →{" "}
                <ZoneBadge zone="Equilibrium" />
              </div>
            </div>
          </div>
          <div>
            <h4 className="font-semibold text-zinc-300 mb-2">Mode</h4>
            <div className="space-y-1 text-xs">
              <div>
                <span className="inline-flex items-center rounded-md border border-emerald-700 bg-emerald-900/60 px-1.5 py-0.5 text-emerald-300 font-bold">
                  EXECUTION
                </span>{" "}
                Live trades
              </div>
              <div>
                <span className="inline-flex items-center rounded-md border border-blue-800 bg-blue-900/40 px-1.5 py-0.5 text-blue-300">
                  DATA
                </span>{" "}
                Analysis only
              </div>
            </div>
          </div>
          <div>
            <h4 className="font-semibold text-zinc-300 mb-2">Session</h4>
            <div className="space-y-1 text-xs">
              <div>
                <span className="text-orange-400">🇬🇧 LONDON</span> — 02:00–05:00 EST
              </div>
              <div>
                <span className="text-purple-400">🗽 NY</span> — 07:00–10:00 EST
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
