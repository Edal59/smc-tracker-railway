/**
 * TradeX OIE v17.25 — API Client
 * Connects to the Railway Flask backend.
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
  return apiFetch<{ status: string; version: string; service: string }>('/api/v1/health');
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
}

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
