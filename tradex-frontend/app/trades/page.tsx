"use client";

import { useEffect, useState, useCallback } from "react";
import {
  getSignals,
  getStats,
  type Signal,
  type AlertMode,
  type SessionFilter,
  getDisplayStatus,
} from "@/lib/api";

// ─── Badge Components ──────────────────────────────────

function StatusBadge({ status }: { status: string }) {
  const styles: Record<string, string> = {
    ACTIVE: "bg-blue-900/50 text-blue-400",
    WON: "bg-emerald-900/50 text-emerald-400",
    LOST: "bg-red-900/50 text-red-400",
    TIMEOUT: "bg-amber-900/50 text-amber-400",
    GET_OUT: "bg-purple-900/50 text-purple-400",
    CANCELLED: "bg-zinc-700/50 text-zinc-400",
    INVALID: "bg-zinc-600/50 text-zinc-400 border border-zinc-500",
  };
  return (
    <span
      className={`rounded px-2 py-0.5 text-xs font-medium ${styles[status] || "bg-zinc-800 text-zinc-400"}`}
    >
      {status}
    </span>
  );
}

function ModeBadge({ mode }: { mode?: string }) {
  if (mode === "EXECUTION") {
    return (
      <span
        className="rounded px-2 py-0.5 text-xs font-bold bg-emerald-900/60 text-emerald-300 border border-emerald-700"
        title="EXECUTION mode — live trade signals for real entries"
      >
        EXECUTION
      </span>
    );
  }
  return (
    <span
      className="rounded px-2 py-0.5 text-xs font-medium bg-blue-900/40 text-blue-300 border border-blue-800"
      title="DATA mode — market analysis signals for backtesting"
    >
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

// ─── Filter Button ─────────────────────────────────────

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
      inactive:
        "bg-zinc-900 text-zinc-400 border-zinc-700 hover:border-zinc-500 hover:text-zinc-200",
    },
    emerald: {
      active: "bg-emerald-600 text-white border-emerald-500",
      inactive:
        "bg-zinc-900 text-emerald-400 border-zinc-700 hover:border-emerald-600",
    },
    blue: {
      active: "bg-blue-600 text-white border-blue-500",
      inactive:
        "bg-zinc-900 text-blue-400 border-zinc-700 hover:border-blue-600",
    },
    orange: {
      active: "bg-orange-600 text-white border-orange-500",
      inactive:
        "bg-zinc-900 text-orange-400 border-zinc-700 hover:border-orange-600",
    },
    purple: {
      active: "bg-purple-600 text-white border-purple-500",
      inactive:
        "bg-zinc-900 text-purple-400 border-zinc-700 hover:border-purple-600",
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

// ─── Signal Row ────────────────────────────────────────

function SignalRow({ s }: { s: Signal }) {
  const isLong = s.direction === "LONG";
  const ts = s.signal_timestamp
    ? new Date(s.signal_timestamp).toLocaleString()
    : "—";
  const displayStatus = getDisplayStatus(s);
  const rrText =
    s.actual_rr != null
      ? `${s.actual_rr >= 0 ? "+" : ""}${s.actual_rr.toFixed(2)}R`
      : "—";
  const pipsText =
    s.pips_gained != null
      ? `${s.pips_gained >= 0 ? "+" : ""}${s.pips_gained.toFixed(1)}`
      : "—";

  const isExec = s.mode === "EXECUTION";

  return (
    <tr
      className={`border-b border-zinc-800 hover:bg-zinc-800/50 transition-colors ${isExec ? "bg-emerald-950/10" : ""}`}
    >
      <td className="px-3 py-2 text-xs text-zinc-500">{ts}</td>
      <td className="px-3 py-2 font-mono font-semibold">{s.pair}</td>
      <td
        className={`px-3 py-2 font-semibold ${isLong ? "text-emerald-400" : "text-red-400"}`}
      >
        {s.direction}
      </td>
      <td className="px-3 py-2 text-xs">{s.signal_type || "—"}</td>
      <td className="px-3 py-2">
        <ModeBadge mode={s.mode} />
      </td>
      <td className="px-3 py-2">
        <SessionBadge session={s.session_tag} />
      </td>
      <td className="px-3 py-2 font-mono text-xs">{s.entry_price || "—"}</td>
      <td className="px-3 py-2 font-mono text-xs text-red-400">
        {s.stop_loss || "—"}
      </td>
      <td className="px-3 py-2 font-mono text-xs text-emerald-400">
        {s.take_profit || "—"}
      </td>
      <td className="px-3 py-2 text-center">
        {s.poi_score != null ? `${s.poi_score}/6` : "—"}
      </td>
      <td className="px-3 py-2">
        <StatusBadge status={displayStatus} />
      </td>
      <td
        className={`px-3 py-2 font-mono font-semibold ${
          s.actual_rr != null
            ? s.actual_rr >= 0
              ? "text-emerald-400"
              : "text-red-400"
            : "text-zinc-500"
        }`}
      >
        {rrText}
      </td>
      <td className="px-3 py-2 font-mono text-xs">{pipsText}</td>
    </tr>
  );
}

// ─── Main Page ─────────────────────────────────────────

export default function TradesPage() {
  const [signals, setSignals] = useState<Signal[]>([]);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);

  // Filters
  const [modeFilter, setModeFilter] = useState<AlertMode>("ALL");
  const [sessionFilter, setSessionFilter] = useState<SessionFilter>("ALL");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = { limit: "100" };
      if (modeFilter !== "ALL") params.mode = modeFilter;
      if (sessionFilter !== "ALL") params.session = sessionFilter;

      const data = await getSignals(params);
      setSignals(data.signals || []);
      setTotal(data.total || 0);
    } catch {
      setSignals([]);
      setTotal(0);
    }
    try {
      const statsParams: Record<string, string> = {};
      if (modeFilter !== "ALL") statsParams.mode = modeFilter;
      else statsParams.mode = "ALL";
      const m = await getStats(statsParams);
      setStats(m);
    } catch {
      setStats({});
    }
    setLoading(false);
  }, [modeFilter, sessionFilter]);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const summary = stats?.summary || stats || {};

  return (
    <div>
      <div className="flex items-center justify-between mb-6">
        <div>
          <h1 className="text-2xl font-bold">Trade Log</h1>
          <p className="text-sm text-zinc-500">
            {total} signals tracked
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

      {/* ─── Filters ─────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-4 mb-6 p-4 rounded-lg border border-zinc-800 bg-zinc-900/50">
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500 uppercase font-semibold tracking-wider">
            Mode:
          </span>
          <FilterBtn
            label="ALL"
            active={modeFilter === "ALL"}
            onClick={() => setModeFilter("ALL")}
          />
          <FilterBtn
            label="⚡ EXECUTION"
            active={modeFilter === "EXECUTION"}
            onClick={() => setModeFilter("EXECUTION")}
            color="emerald"
          />
          <FilterBtn
            label="📊 DATA"
            active={modeFilter === "DATA"}
            onClick={() => setModeFilter("DATA")}
            color="blue"
          />
        </div>
        <div className="h-6 w-px bg-zinc-700" />
        <div className="flex items-center gap-2">
          <span className="text-xs text-zinc-500 uppercase font-semibold tracking-wider">
            Session:
          </span>
          <FilterBtn
            label="ALL"
            active={sessionFilter === "ALL"}
            onClick={() => setSessionFilter("ALL")}
          />
          <FilterBtn
            label="🇬🇧 LONDON"
            active={sessionFilter === "LONDON"}
            onClick={() => setSessionFilter("LONDON")}
            color="orange"
          />
          <FilterBtn
            label="🗽 NY"
            active={sessionFilter === "NY"}
            onClick={() => setSessionFilter("NY")}
            color="purple"
          />
        </div>
      </div>

      {/* Quick Stats */}
      {(summary.total_signals > 0 || summary.total_trades > 0) && (
        <div className="grid grid-cols-2 md:grid-cols-5 gap-3 mb-6">
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
            <div className="text-xs text-zinc-500 uppercase">Total</div>
            <div className="text-xl font-bold">
              {summary.total_signals || summary.total_trades || 0}
            </div>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
            <div className="text-xs text-zinc-500 uppercase">Win Rate</div>
            <div
              className={`text-xl font-bold ${(summary.win_rate || 0) >= 50 ? "text-emerald-400" : "text-red-400"}`}
            >
              {(summary.win_rate || 0).toFixed(1)}%
            </div>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
            <div className="text-xs text-zinc-500 uppercase">W / L</div>
            <div className="text-xl font-bold">
              {summary.wins || 0} / {summary.losses || 0}
            </div>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
            <div className="text-xs text-zinc-500 uppercase">Expectancy</div>
            <div
              className={`text-xl font-bold ${(summary.expectancy || 0) >= 0 ? "text-emerald-400" : "text-red-400"}`}
            >
              {(summary.expectancy || 0).toFixed(2)}R
            </div>
          </div>
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-4 text-center">
            <div className="text-xs text-zinc-500 uppercase">Profit Factor</div>
            <div className="text-xl font-bold">
              {(summary.profit_factor || 0).toFixed(2)}
            </div>
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
                <th className="px-3 py-3">Mode</th>
                <th className="px-3 py-3">Session</th>
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
                  <td
                    colSpan={13}
                    className="px-3 py-12 text-center text-zinc-500"
                  >
                    {loading
                      ? "Loading signals..."
                      : "No signals match the current filters."}
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
