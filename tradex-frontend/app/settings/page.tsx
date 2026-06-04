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
  let health = { version: "unknown", status: "unknown", service: "", features: [] as string[] };
  try { health = await getHealth() as any; } catch {}

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
            <p className="text-xs text-zinc-500 mt-2">
              💡 <strong>v17.56.7:</strong> Add <code className="text-emerald-400">?api_key=YOUR_KEY</code> to the URL for authentication.
            </p>
          </div>

          {/* v17.56.7 Dual Mode Info */}
          <div className="rounded-lg border border-blue-800 bg-blue-950/30 p-6">
            <h2 className="text-lg font-semibold text-blue-400 mb-4">v17.56.7 Dual Mode Alert System</h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
              <div>
                <h3 className="font-semibold text-emerald-400 mb-2">⚡ EXECUTION Mode</h3>
                <p className="text-zinc-400 text-xs">
                  Fires during active trade sessions (London 02:00-05:00 EST, NY 07:00-10:00 EST).
                  These are actionable signals meant for live trading. Only high-quality setups with
                  valid POI scores pass through.
                </p>
              </div>
              <div>
                <h3 className="font-semibold text-blue-400 mb-2">📊 DATA Mode</h3>
                <p className="text-zinc-400 text-xs">
                  Fires outside trade sessions for market analysis and backtesting.
                  These signals are recorded for pattern research but should not be traded live.
                  Performance stats default to EXECUTION-only.
                </p>
              </div>
            </div>
            <div className="mt-4 p-3 rounded border border-amber-800/50 bg-amber-950/20">
              <p className="text-xs text-amber-300">
                <strong>Hard Block Rules:</strong> Alerts with POI=0 or invalid zones are automatically blocked.
                Zombie trades (missing entry/SL/TP) are classified as INVALID, not LOST.
              </p>
            </div>
          </div>

          {/* Alert Templates */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
            <h2 className="text-lg font-semibold mb-4">v17.56.7 Alert Architecture</h2>
            <p className="text-sm text-zinc-400 mb-4">
              v17.56.7 uses the <strong>alert() architecture</strong> with dual-mode JSON payloads.
              Each alert includes <code className="text-emerald-400">mode</code>,{" "}
              <code className="text-emerald-400">session</code>,{" "}
              <code className="text-emerald-400">direction</code>, and{" "}
              <code className="text-emerald-400">valid</code> fields alongside standard TradingView variables.
            </p>

            <p className="text-xs text-amber-300 mb-4">
              <strong>v17.56.7 alert() setup:</strong> In TradingView, select the alert type from the
              Condition dropdown. The indicator auto-populates the JSON with mode, session, and direction.
              Ensure the webhook URL includes your API key.
            </p>

            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-semibold text-emerald-400 mb-2">⊕ 1. A+ Sniper Buy (Long)</h3>
                <pre className="rounded-md border border-zinc-700 bg-zinc-800 p-4 text-xs font-mono text-zinc-300 overflow-x-auto">{`{"version":"v17.56.7","setup":"A+ SNIPER","direction":"LONG","mode":"EXECUTION","session":"LONDON","symbol":"{{ticker}}","timeframe":"{{interval}}","price":"{{close}}","valid":true}`}</pre>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-red-400 mb-2">⊖ 2. A+ Sniper Sell (Short)</h3>
                <pre className="rounded-md border border-zinc-700 bg-zinc-800 p-4 text-xs font-mono text-zinc-300 overflow-x-auto">{`{"version":"v17.56.7","setup":"A+ SNIPER","direction":"SHORT","mode":"EXECUTION","session":"NY","symbol":"{{ticker}}","timeframe":"{{interval}}","price":"{{close}}","valid":true}`}</pre>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-amber-400 mb-2">↩ 3. Retrace Long</h3>
                <pre className="rounded-md border border-zinc-700 bg-zinc-800 p-4 text-xs font-mono text-zinc-300 overflow-x-auto">{`{"version":"v17.56.7","setup":"RETRACE","direction":"LONG","mode":"DATA","session":"NY","symbol":"{{ticker}}","timeframe":"{{interval}}","price":"{{close}}","valid":true}`}</pre>
              </div>

              <div>
                <h3 className="text-sm font-semibold text-amber-400 mb-2">↪ 4. Retrace Short</h3>
                <pre className="rounded-md border border-zinc-700 bg-zinc-800 p-4 text-xs font-mono text-zinc-300 overflow-x-auto">{`{"version":"v17.56.7","setup":"RETRACE","direction":"SHORT","mode":"DATA","session":"LONDON","symbol":"{{ticker}}","timeframe":"{{interval}}","price":"{{close}}","valid":true}`}</pre>
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
                <h4 className="font-semibold text-zinc-300 mb-2">Mode</h4>
                <div className="space-y-1 text-xs">
                  <div><span className="text-emerald-400 font-bold">EXECUTION</span> = Live trades</div>
                  <div><span className="text-blue-400">DATA</span> = Analysis only</div>
                </div>
              </div>
              <div>
                <h4 className="font-semibold text-zinc-300 mb-2">Session</h4>
                <div className="space-y-1 text-xs">
                  <div>🇬🇧 <span className="text-orange-400">LONDON</span> = 02:00-05:00 EST</div>
                  <div>🗽 <span className="text-purple-400">NY</span> = 07:00-10:00 EST</div>
                </div>
              </div>
              <div>
                <h4 className="font-semibold text-zinc-300 mb-2">Status</h4>
                <div className="space-y-1 text-xs">
                  <div><span className="text-emerald-400">WON</span> = TP hit</div>
                  <div><span className="text-red-400">LOST</span> = SL hit</div>
                  <div><span className="text-zinc-400">INVALID</span> = Missing prices</div>
                  <div><span className="text-blue-400">ACTIVE</span> = Open trade</div>
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
              {health.features && health.features.length > 0 && (
                <div className="mt-2 pt-2 border-t border-zinc-800">
                  <span className="text-xs text-zinc-500 block mb-1">Features</span>
                  <div className="flex flex-wrap gap-1">
                    {health.features.map((f: string) => (
                      <span key={f} className="text-xs bg-zinc-800 text-zinc-300 px-1.5 py-0.5 rounded">
                        {f}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>

          {/* Quick Setup */}
          <div className="rounded-lg border border-blue-800 bg-blue-950/30 p-6">
            <h3 className="text-sm font-semibold text-blue-400 uppercase tracking-wider mb-3">Quick Setup</h3>
            <ol className="space-y-2 text-sm text-zinc-400 list-decimal list-inside">
              <li>Copy the <strong>Webhook URL</strong> above</li>
              <li>Append <code className="text-emerald-400">?api_key=YOUR_KEY</code></li>
              <li>In TradingView → Create Alert → Webhook URL → Paste</li>
              <li>v17.56.7 auto-populates mode, session, and direction</li>
              <li>Set trigger to <strong>Bar Close Only</strong></li>
              <li>EXECUTION alerts fire during London/NY sessions</li>
              <li>View performance on the <strong>Dashboard</strong>!</li>
            </ol>
          </div>

          {/* API Endpoints */}
          <div className="rounded-lg border border-zinc-800 bg-zinc-900 p-6">
            <h3 className="text-sm font-semibold text-zinc-400 uppercase tracking-wider mb-3">API Endpoints</h3>
            <div className="space-y-1 text-xs font-mono">
              <div className="text-zinc-500 font-sans font-semibold text-xs mt-2 mb-1">Core</div>
              <div><span className="text-emerald-400">POST</span> /api/v1/signal</div>
              <div><span className="text-blue-400">GET</span> /api/v1/health</div>
              <div><span className="text-blue-400">GET</span> /api/v1/signals <span className="text-zinc-600">?mode=&session=</span></div>
              <div><span className="text-blue-400">GET</span> /api/v1/metrics</div>
              <div><span className="text-blue-400">GET</span> /api/v1/pnl</div>
              <div className="text-zinc-500 font-sans font-semibold text-xs mt-2 mb-1">v17.56.7 New</div>
              <div><span className="text-blue-400">GET</span> /api/v1/stats <span className="text-zinc-600">?mode=&session=</span></div>
              <div><span className="text-blue-400">GET</span> /api/v1/session-performance</div>
              <div className="text-zinc-500 font-sans font-semibold text-xs mt-2 mb-1">OIE</div>
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
