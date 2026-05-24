import { getHealth } from "@/lib/api";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "https://web-production-b63af.up.railway.app";

function CopyBlock({ id, label, content }: { id: string; label: string; content: string }) {
  return (
    <div className="mb-4">
      <label className="text-xs font-medium text-zinc-500 uppercase tracking-wider">{label}</label>
      <div className="mt-1 flex">
        <code className="flex-1 rounded-l-md border border-zinc-700 bg-zinc-800 px-3 py-2 font-mono text-sm text-zinc-300 overflow-x-auto">
          {content}
        </code>
      </div>
    </div>
  );
}

export default async function SettingsPage() {
  let health = { version: "unknown", status: "unknown", service: "" };
  try { health = await getHealth(); } catch {}

  const webhookUrl = `${API_BASE}/api/v1/signal`;

  return (
    <div>
      <h1 className="text-2xl font-bold mb-6">Setup Guide</h1>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        {/* Main column */}
        <div className="md:col-span-2 space-y-6">
          {/* Webhook URL */}
          <div className="rounded-lg border border-emerald-800 bg-emerald-950/30 p-6">
            <h2 className="text-lg font-semibold text-emerald-400 mb-4">Webhook URL</h2>
            <p className="text-sm text-zinc-400 mb-3">Paste this URL into your TradingView alert webhook settings:</p>
            <CopyBlock id="webhook" label="Webhook Endpoint" content={webhookUrl} />
          </div>

          {/* Alert Templates */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
            <h2 className="text-lg font-semibold mb-4">v17.54 Alert Templates</h2>
            <p className="text-sm text-zinc-400 mb-4">
              v17.54 uses the <strong>alert() architecture</strong> with dynamic JSON payloads.
              No more <code className="text-emerald-400">{"{{plot_X}}"}</code> placeholders &mdash; each alert
              fires a clean JSON with <code className="text-emerald-400">{"{{ticker}}"}</code>,{" "}
              <code className="text-emerald-400">{"{{interval}}"}</code>, and{" "}
              <code className="text-emerald-400">{"{{close}}"}</code> TradingView variables.
            </p>

            <p className="text-xs text-amber-300 mb-4">
              <strong>v17.54 alert() setup:</strong> In TradingView, select the alert type from the
              Condition dropdown (Sniper Long, Sniper Short, Retrace Long, Retrace Short).
              The message body is auto-populated by the indicator. Just ensure the webhook URL is set.
            </p>

            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-semibold text-emerald-400 mb-2">⊕ 1. A+ Sniper Buy (Long)</h3>
                <pre className="rounded-md border border-zinc-700 bg-zinc-800 p-4 text-xs font-mono text-zinc-300 overflow-x-auto">{`{"version":"v17.54","alert":"A_PLUS_SNIPER_BUY","symbol":"{{ticker}}","timeframe":"{{interval}}","price":"{{close}}","message":"v17.54 A+ SNIPER BUY - Aligned with Trend. Target 1:3 RR."}`}</pre>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-red-400 mb-2">⊖ 2. A+ Sniper Sell (Short)</h3>
                <pre className="rounded-md border border-zinc-700 bg-zinc-800 p-4 text-xs font-mono text-zinc-300 overflow-x-auto">{`{"version":"v17.54","alert":"A_PLUS_SNIPER_SELL","symbol":"{{ticker}}","timeframe":"{{interval}}","price":"{{close}}","message":"v17.54 A+ SNIPER SELL - Aligned with Trend. Target 1:3 RR."}`}</pre>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-amber-400 mb-2">↩ 3. Retrace Long</h3>
                <pre className="rounded-md border border-zinc-700 bg-zinc-800 p-4 text-xs font-mono text-zinc-300 overflow-x-auto">{`{"version":"v17.54","alert":"RETRACE_LONG","subtype":"standard","symbol":"{{ticker}}","timeframe":"{{interval}}","price":"{{close}}","message":"v17.54 RETRACE LONG - Target: EQ Line."}`}</pre>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-amber-400 mb-2">↪ 4. Retrace Short</h3>
                <pre className="rounded-md border border-zinc-700 bg-zinc-800 p-4 text-xs font-mono text-zinc-300 overflow-x-auto">{`{"version":"v17.54","alert":"RETRACE_SHORT","subtype":"standard","symbol":"{{ticker}}","timeframe":"{{interval}}","price":"{{close}}","message":"v17.54 RETRACE SHORT - Target: EQ Line."}`}</pre>
              </div>
            </div>
          </div>

          {/* Decode Reference */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
            <h2 className="text-lg font-semibold mb-4">Decode Reference</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
              <div>
                <h4 className="font-semibold text-zinc-300 mb-2">H4 Bias</h4>
                <div className="space-y-1 text-xs">
                  <div><code className="text-emerald-400">1</code> = Bullish</div>
                  <div><code className="text-red-400">-1</code> = Bearish</div>
                  <div><code className="text-zinc-500">0</code> = Neutral</div>
                </div>
              </div>
              <div>
                <h4 className="font-semibold text-zinc-300 mb-2">P&D Zone</h4>
                <div className="space-y-1 text-xs">
                  <div><code className="text-red-400">1</code> = Premium</div>
                  <div><code className="text-emerald-400">0</code> = Discount</div>
                  <div><code className="text-amber-400">-1</code> = Equilibrium</div>
                </div>
              </div>
              <div>
                <h4 className="font-semibold text-zinc-300 mb-2">Guardian</h4>
                <div className="space-y-1 text-xs">
                  <div><code>0</code> = Waiting</div>
                  <div><code>1/2</code> = Sniper Buy/Sell</div>
                  <div><code>3/4</code> = Retrace Buy/Sell</div>
                  <div><code>5/6</code> = Trap Buy/Sell</div>
                </div>
              </div>
              <div>
                <h4 className="font-semibold text-zinc-300 mb-2">Kill Zone</h4>
                <div className="space-y-1 text-xs">
                  <div><code>0</code> = Off-Session</div>
                  <div><code>1</code> = London</div>
                  <div><code>2</code> = NY AM</div>
                  <div><code>3</code> = NY PM</div>
                  <div><code>4</code> = Asian</div>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Sidebar */}
        <div className="space-y-6">
          {/* Server Info */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
            <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">Server Info</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-zinc-500">Status</span>
                <span className={health.status === "ok" ? "text-emerald-400" : "text-red-400"}>
                  {health.status === "ok" ? "● Online" : "● Offline"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Version</span>
                <span className="font-mono text-emerald-400">{health.version}</span>
              </div>
              <div className="flex justify-between">
                <span className="text-zinc-500">Service</span>
                <span className="text-xs">{health.service}</span>
              </div>
            </div>
          </div>

          {/* Quick Setup */}
          <div className="rounded-lg border border-blue-800 bg-blue-950/30 p-6">
            <h3 className="text-sm font-semibold text-blue-400 uppercase tracking-wider mb-3">Quick Setup</h3>
            <ol className="space-y-2 text-sm text-zinc-400 list-decimal list-inside">
              <li>Copy the <strong>Webhook URL</strong> above</li>
              <li>In TradingView → Create Alert → Webhook URL → Paste</li>
              <li>Copy the appropriate <strong>Alert Template</strong> into the body</li>
              <li>Set <strong>type</strong> to match: sniper_long, sniper_short, retrace_long, retrace_short</li>
              <li>Add your <strong>API key</strong> to the JSON</li>
              <li>Set trigger to <strong>Bar Close Only</strong></li>
              <li>View opportunities on the <strong>Dashboard</strong>!</li>
            </ol>
          </div>

          {/* API Endpoints */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
            <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">API Endpoints</h3>
            <div className="space-y-1 text-xs font-mono">
              <div className="text-zinc-500 font-sans font-semibold text-xs mt-2 mb-1">Core</div>
              <div><span className="text-emerald-400">POST</span> /api/v1/signal</div>
              <div><span className="text-blue-400">GET</span> /api/v1/health</div>
              <div><span className="text-blue-400">GET</span> /api/v1/signals</div>
              <div><span className="text-blue-400">GET</span> /api/v1/metrics</div>
              <div><span className="text-blue-400">GET</span> /api/v1/pnl</div>
              <div className="text-zinc-500 font-sans font-semibold text-xs mt-2 mb-1">OIE v17.54</div>
              <div><span className="text-blue-400">GET</span> /api/v1/opportunities</div>
              <div><span className="text-blue-400">GET</span> /api/v1/opportunities/summary</div>
              <div><span className="text-blue-400">GET</span> /api/v1/opportunities/:id</div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
