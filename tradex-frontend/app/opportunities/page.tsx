"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getOpportunities,
  getOpportunitySummary,
  type Opportunity,
  type AlertMode,
  type SessionFilter,
} from "@/lib/api";

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
    <span
      className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium ${styles[type] || "bg-zinc-800 text-zinc-400 border-zinc-700"}`}
    >
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
    invalid: "bg-zinc-600/50 text-zinc-400 border border-zinc-500",
  };
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs font-medium ${styles[status] || "bg-zinc-800 text-zinc-400"}`}
    >
      {status?.toUpperCase() || "UNKNOWN"}
    </span>
  );
}

function ModeBadge({ mode }: { mode?: string }) {
  if (mode === "EXECUTION") {
    return (
      <span className="rounded px-2 py-0.5 text-xs font-bold bg-emerald-900/60 text-emerald-300 border border-emerald-700" title="EXECUTION mode — live trade signals">
        EXECUTION
      </span>
    );
  }
  return (
    <span className="rounded px-2 py-0.5 text-xs font-medium bg-blue-900/40 text-blue-300 border border-blue-800" title="DATA mode — analysis signals">
      DATA
    </span>
  );
}

function SessionBadge({ session }: { session?: string }) {
  if (session === "LONDON") {
    return (
      <span className="rounded px-2 py-0.5 text-xs font-medium bg-orange-900/50 text-orange-300 border border-orange-800">
        🇬🇧 LONDON
      </span>
    );
  }
  if (session === "NY") {
    return (
      <span className="rounded px-2 py-0.5 text-xs font-medium bg-purple-900/50 text-purple-300 border border-purple-800">
        🗽 NY
      </span>
    );
  }
  return (
    <span className="rounded px-2 py-0.5 text-xs font-medium bg-zinc-800 text-zinc-400">
      {session || "—"}
    </span>
  );
}

function FilterBtn({
  label,
  active,
  onClick,
  color = "zinc",
}: {
  label: string;
  active: boolean;
  onClick: () => void;
  color?: string;
}) {
  const colorMap: Record<string, { active: string; inactive: string }> = {
    zinc: {
      active: "bg-zinc-100 text-zinc-900 border-zinc-300",
      inactive: "bg-zinc-900 text-zinc-400 border-zinc-700 hover:border-zinc-500 hover:text-zinc-200",
    },
    emerald: {
      active: "bg-emerald-600 text-white border-emerald-500",
      inactive: "bg-zinc-900 text-emerald-400 border-zinc-700 hover:border-emerald-600",
    },
    blue: {
      active: "bg-blue-600 text-white border-blue-500",
      inactive: "bg-zinc-900 text-blue-400 border-zinc-700 hover:border-blue-600",
    },
    orange: {
      active: "bg-orange-600 text-white border-orange-500",
      inactive: "bg-zinc-900 text-orange-400 border-zinc-700 hover:border-orange-600",
    },
    purple: {
      active: "bg-purple-600 text-white border-purple-500",
      inactive: "bg-zinc-900 text-purple-400 border-zinc-700 hover:border-purple-600",
    },
  };
  const c = colorMap[color] || colorMap.zinc;
  return (
    <button
      onClick={onClick}
      className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-all ${active ? c.active : c.inactive}`}
    >
      {label}
    </button>
  );
}

function OppRow({ o }: { o: Opportunity }) {
  const isLong = o.setup_type.includes("long");
  const ts = o.identified_at
    ? new Date(o.identified_at).toLocaleString()
    : "—";
  const isExec = o.mode === "EXECUTION";

  return (
    <tr className={`border-b border-zinc-800 hover:bg-zinc-800/50 transition-colors ${isExec ? "bg-emerald-950/10" : ""}`}>
      <td className="px-3 py-2 text-xs text-zinc-500">{ts}</td>
      <td className="px-3 py-2 font-mono font-semibold">{o.pair}</td>
      <td className="px-3 py-2">
        <SetupBadge type={o.setup_type} />
      </td>
      <td className="px-3 py-2">
        <ModeBadge mode={o.mode} />
      </td>
      <td className="px-3 py-2">
        <SessionBadge session={o.session_tag} />
      </td>
      <td className="px-3 py-2">
        <span className={isLong ? "text-emerald-400" : "text-red-400"}>
          {o.h4_bias === "Bullish"
            ? "▲"
            : o.h4_bias === "Bearish"
              ? "▼"
              : "—"}{" "}
          {o.h4_bias}
        </span>
      </td>
      <td className="px-3 py-2">
        <span
          className={`rounded px-1.5 py-0.5 text-xs ${
            o.pd_zone === "Premium"
              ? "bg-red-900/30 text-red-400"
              : o.pd_zone === "Discount"
                ? "bg-emerald-900/30 text-emerald-400"
                : "bg-amber-900/30 text-amber-400"
          }`}
        >
          {o.pd_zone}
        </span>
      </td>
      <td className="px-3 py-2 font-mono text-xs">{o.entry_price}</td>
      <td className="px-3 py-2 font-mono text-xs text-red-400">
        {o.sl_price}
      </td>
      <td className="px-3 py-2 font-mono text-xs text-emerald-400">
        {o.tp_price}
      </td>
      <td className="px-3 py-2 font-mono font-semibold">
        {o.rr_ratio?.toFixed(1)}:1
      </td>
      <td className="px-3 py-2 text-center">{o.poi_score ?? "—"}</td>
      <td className="px-3 py-2">
        <StatusBadge status={o.status} />
      </td>
    </tr>
  );
}

export default function OpportunitiesPage() {
  const [opps, setOpps] = useState<Opportunity[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [modeFilter, setModeFilter] = useState<AlertMode>("ALL");
  const [sessionFilter, setSessionFilter] = useState<SessionFilter>("ALL");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = { limit: "100" };
      if (modeFilter !== "ALL") params.mode = modeFilter;
      if (sessionFilter !== "ALL") params.session = sessionFilter;
      const data = await getOpportunities(params);
      setOpps(data.opportunities || []);
      setTotal(data.total || 0);
    } catch {
      setOpps([]);
      setTotal(0);
    }
    try {
      setSummary(await getOpportunitySummary());
    } catch {}
    setLoading(false);
  }, [modeFilter, sessionFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">
            Opportunity Intelligence Engine
          </h1>
          <p className="text-sm text-zinc-500">
            v17.56.7 decoded opportunities — {total} total
            {modeFilter !== "ALL" && (
              <span className="ml-1 text-emerald-400">
                ({modeFilter} only)
              </span>
            )}
            {sessionFilter !== "ALL" && (
              <span className="ml-1 text-purple-400">
                • {sessionFilter} session
              </span>
            )}
          </p>
        </div>
        {loading && (
          <span className="text-xs text-zinc-500 animate-pulse">
            Loading...
          </span>
        )}
      </div>

      {/* Filters */}
      <div className="flex flex-wrap items-center gap-4 mb-6 p-4 rounded-lg border border-zinc-800 bg-zinc-900/50">
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500 uppercase font-semibold tracking-wider">Mode:</span>
          <FilterBtn label="ALL" active={modeFilter === "ALL"} onClick={() => setModeFilter("ALL")} />
          <FilterBtn label="⚡ EXECUTION" active={modeFilter === "EXECUTION"} onClick={() => setModeFilter("EXECUTION")} color="emerald" />
          <FilterBtn label="📊 DATA" active={modeFilter === "DATA"} onClick={() => setModeFilter("DATA")} color="blue" />
        </div>
        <div className="h-6 w-px bg-zinc-700" />
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500 uppercase font-semibold tracking-wider">Session:</span>
          <FilterBtn label="ALL" active={sessionFilter === "ALL"} onClick={() => setSessionFilter("ALL")} />
          <FilterBtn label="🇬🇧 LONDON" active={sessionFilter === "LONDON"} onClick={() => setSessionFilter("LONDON")} color="orange" />
          <FilterBtn label="🗽 NY" active={sessionFilter === "NY"} onClick={() => setSessionFilter("NY")} color="purple" />
        </div>
      </div>

      {/* Summary Row */}
      <div className="grid grid-cols-3 md:grid-cols-6 gap-3 mb-6">
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
          <div className="text-xs text-zinc-500 uppercase">Total</div>
          <div className="text-xl font-bold font-mono">
            {summary.total || 0}
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
          <div className="text-xs text-zinc-500 uppercase">Avg R:R</div>
          <div className="text-xl font-bold font-mono text-cyan-400">
            {(summary.avg_rr || 0).toFixed(1)}
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
          <div className="text-xs text-zinc-500 uppercase">Win Rate</div>
          <div
            className={`text-xl font-bold font-mono ${(summary.win_rate || 0) >= 50 ? "text-emerald-400" : "text-red-400"}`}
          >
            {(summary.win_rate || 0).toFixed(1)}%
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
          <div className="text-xs text-zinc-500 uppercase">Sniper</div>
          <div className="text-xl font-bold font-mono text-emerald-400">
            {summary.sniper_count || 0}
          </div>
        </div>
        <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
          <div className="text-xs text-zinc-500 uppercase">Retrace</div>
          <div className="text-xl font-bold font-mono text-amber-400">
            {summary.retrace_count || 0}
          </div>
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
                <th className="px-3 py-3">Mode</th>
                <th className="px-3 py-3">Session</th>
                <th className="px-3 py-3">H4 Bias</th>
                <th className="px-3 py-3">P&D Zone</th>
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
                  <td
                    colSpan={13}
                    className="px-3 py-12 text-center text-zinc-500"
                  >
                    {loading
                      ? "Loading opportunities..."
                      : "No opportunities match the current filters."}
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
