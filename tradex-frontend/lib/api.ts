/**
 * TradeX OIE v17.56.7 — API Client
 * Connects to the Railway Flask backend.
 * Supports dual-mode alerts, session analytics, and filtered stats.
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || 'https://web-production-b63af.up.railway.app';
const API_KEY = process.env.NEXT_PUBLIC_API_KEY || '';

interface FetchOptions {
  method?: string;
  body?: any;
  cache?: RequestCache;
}

async function apiFetch<T = any>(path: string, opts: FetchOptions = {}): Promise<T> {
  const url = `${API_BASE}${path}`;
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
  };
  if (API_KEY) {
    headers['X-API-Key'] = API_KEY;
  }

  const res = await fetch(url, {
    method: opts.method || 'GET',
    headers,
    body: opts.body ? JSON.stringify(opts.body) : undefined,
    cache: opts.cache || 'no-store',
  });

  if (!res.ok) {
    throw new Error(`API ${res.status}: ${res.statusText}`);
  }

  return res.json();
}

// ─── Health ────────────────────────────────────────────
export async function getHealth() {
  return apiFetch<{ status: string; version: string; service: string; features?: string[] }>('/api/v1/health');
}

// ─── Opportunities (OIE) ──────────────────────────────
export interface Opportunity {
  id: number;
  pair: string;
  setup_type: string;
  setup_id: string;
  h4_bias: string;
  pd_zone: string;
  kill_zone: string;
  guardian: string;
  entry_price: number;
  sl_price: number;
  tp_price: number;
  risk_pips: number;
  reward_pips: number;
  rr_ratio: number;
  quality_score: number | null;
  poi_score: number | null;
  confluence: number | null;
  dt_stage: number | null;
  status: string;
  identified_at: string;
  version: string;
  mode?: string;
  session_tag?: string;
  valid?: boolean;
}

export async function getOpportunities(params?: Record<string, string>) {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return apiFetch<{ opportunities: Opportunity[]; total: number }>(`/api/v1/opportunities${qs}`);
}

export async function getOpportunitySummary(params?: Record<string, string>) {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return apiFetch<Record<string, any>>(`/api/v1/opportunities/summary${qs}`);
}

export async function getOpportunityDetail(id: number) {
  return apiFetch<Opportunity & { outcomes?: any[] }>(`/api/v1/opportunities/${id}`);
}

// ─── Legacy Signals ───────────────────────────────────
export interface Signal {
  signal_id: string;
  pair: string;
  direction: string;
  signal_type: string;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  status: string;
  actual_rr: number | null;
  pips_gained: number | null;
  poi_score: number | null;
  kill_zone: string;
  signal_timestamp: string;
  trade_status: string;
  mode?: string;
  session_tag?: string;
  valid?: boolean;
}

export type AlertMode = 'ALL' | 'EXECUTION' | 'DATA';
export type SessionFilter = 'ALL' | 'LONDON' | 'NY';

export async function getSignals(params?: Record<string, string>) {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return apiFetch<{ signals: Signal[]; total: number }>(`/api/v1/signals${qs}`);
}

export async function getMetrics(params?: Record<string, string>) {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return apiFetch<Record<string, any>>(`/api/v1/metrics${qs}`);
}

export async function getPnlCurve(params?: Record<string, string>) {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return apiFetch<{ data: any[] }>(`/api/v1/pnl${qs}`);
}

// ─── v17.56.7 New Endpoints ───────────────────────────

/** Fetch filtered stats (defaults to EXECUTION mode) */
export async function getStats(params?: Record<string, string>) {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return apiFetch<Record<string, any>>(`/api/v1/stats${qs}`);
}

/** Session performance comparison (London vs NY) */
export interface SessionPerformance {
  session: string;
  total_trades: number;
  wins: number;
  losses: number;
  win_rate: number;
  avg_rr: number;
  expectancy: number;
  best_rr: number;
  worst_rr: number;
}

export interface SessionPerformanceResponse {
  london: SessionPerformance;
  ny: SessionPerformance;
  comparison: {
    better_session: string;
    win_rate_diff: number;
    rr_diff: number;
  };
  filters: {
    mode: string;
    pair: string;
    days: number;
  };
}

export async function getSessionPerformance(params?: Record<string, string>) {
  const qs = params ? '?' + new URLSearchParams(params).toString() : '';
  return apiFetch<SessionPerformanceResponse>(`/api/v1/session-performance${qs}`);
}

// ─── Helpers ──────────────────────────────────────────

/** Check if a trade should be classified as INVALID (missing prices) */
export function isInvalidTrade(signal: Signal): boolean {
  return (
    !signal.entry_price ||
    signal.entry_price === 0 ||
    !signal.stop_loss ||
    signal.stop_loss === 0 ||
    !signal.take_profit ||
    signal.take_profit === 0
  );
}

/** Get the display status — overrides LOST with INVALID when prices are missing */
export function getDisplayStatus(signal: Signal): string {
  if (signal.status === 'INVALID') return 'INVALID';
  if (isInvalidTrade(signal) && (signal.status === 'LOST' || signal.status === 'ACTIVE')) {
    return 'INVALID';
  }
  return signal.status;
}
