// TradeX OIE v17.14.1 — Opportunities Dashboard JS

let currentOffset = 0;
const pageSize = 50;

document.addEventListener('DOMContentLoaded', () => {
    loadOpportunities();
    loadSummary();
});

function getFilters() {
    const pair = document.getElementById('filter-pair').value;
    const setup = document.getElementById('filter-setup').value;
    const kz = document.getElementById('filter-kz').value;
    let params = new URLSearchParams();
    if (pair) params.set('pair', pair);
    if (setup) params.set('setup_type', setup);
    if (kz) params.set('kill_zone', kz);
    return params;
}

// ============================================================
// Summary
// ============================================================

async function loadSummary() {
    try {
        const res = await fetch('/dash/api/oie/summary');
        const data = await res.json();
        document.getElementById('stat-total').textContent = data.total || 0;
        document.getElementById('stat-avg-rr').textContent = (data.avg_rr || 0).toFixed(1);
        document.getElementById('stat-sniper').textContent = data.sniper_count || 0;
        document.getElementById('stat-retrace').textContent = data.retrace_count || 0;
        document.getElementById('stat-avg-poi').textContent = (data.avg_sniper_poi || 0).toFixed(0);
        document.getElementById('stat-active').textContent = (data.identified || 0) + (data.active || 0);
    } catch (err) {
        console.error('Summary load error:', err);
    }
}

// ============================================================
// Opportunities Table
// ============================================================

async function loadOpportunities() {
    const params = getFilters();
    params.set('limit', pageSize);
    params.set('offset', currentOffset);

    try {
        const res = await fetch(`/dash/api/oie/opportunities?${params.toString()}`);
        const data = await res.json();
        renderOpportunities(data.opportunities);
        updatePagination(data);
        document.getElementById('opp-count').textContent = `${data.total || 0} opportunities`;
    } catch (err) {
        console.error('Load opportunities error:', err);
    }
}

function renderOpportunities(opps) {
    const tbody = document.getElementById('opp-table');
    if (!opps || opps.length === 0) {
        tbody.innerHTML = '<tr><td colspan="13" class="text-center text-muted py-4">No opportunities yet. Configure v17.14.1 TradingView alerts to get started!</td></tr>';
        return;
    }
    tbody.innerHTML = opps.map(o => {
        const setupBadge = getSetupBadge(o.setup_type);
        const biasBadge = getBiasBadge(o.h4_bias);
        const zoneBadge = getZoneBadge(o.pd_zone);
        const kzBadge = getKzBadge(o.kill_zone);
        const guardianBadge = getGuardianBadge(o.guardian);
        const statusBadge = getOppStatusBadge(o.status);
        const ts = o.identified_at ? new Date(o.identified_at).toLocaleString() : '—';
        const rr = o.rr_ratio ? o.rr_ratio.toFixed(1) + ':1' : '—';
        const poi = o.poi_score != null ? o.poi_score : '—';

        return `<tr style="cursor:pointer" onclick="showOppDetail(${o.id})">
            <td class="small">${ts}</td>
            <td><strong>${o.pair}</strong></td>
            <td>${setupBadge}</td>
            <td>${biasBadge}</td>
            <td>${zoneBadge}</td>
            <td>${kzBadge}</td>
            <td>${guardianBadge}</td>
            <td class="font-monospace">${o.entry_price || '—'}</td>
            <td class="font-monospace text-danger">${o.sl_price || '—'}</td>
            <td class="font-monospace text-success">${o.tp_price || '—'}</td>
            <td class="fw-bold">${rr}</td>
            <td>${poi}</td>
            <td>${statusBadge}</td>
        </tr>`;
    }).join('');
}

// ============================================================
// Badge Helpers
// ============================================================

function getSetupBadge(setup) {
    const map = {
        'sniper_long': '<span class="badge bg-success"><i class="bi bi-crosshair me-1"></i>Sniper Long</span>',
        'sniper_short': '<span class="badge bg-danger"><i class="bi bi-crosshair me-1"></i>Sniper Short</span>',
        'retrace_long': '<span class="badge" style="background:#1a6b3c"><i class="bi bi-arrow-return-right me-1"></i>Retrace Long</span>',
        'retrace_short': '<span class="badge" style="background:#8b2020"><i class="bi bi-arrow-return-left me-1"></i>Retrace Short</span>',
    };
    return map[setup] || `<span class="badge bg-secondary">${setup}</span>`;
}

function getBiasBadge(bias) {
    if (bias === 'Bullish') return '<span class="text-success fw-bold">▲ Bullish</span>';
    if (bias === 'Bearish') return '<span class="text-danger fw-bold">▼ Bearish</span>';
    return '<span class="text-muted">— Neutral</span>';
}

function getZoneBadge(zone) {
    if (zone === 'Premium') return '<span class="badge bg-danger">Premium</span>';
    if (zone === 'Discount') return '<span class="badge bg-success">Discount</span>';
    if (zone === 'Equilibrium') return '<span class="badge bg-warning text-dark">Equilibrium</span>';
    return '<span class="badge bg-secondary">' + (zone || 'Unknown') + '</span>';
}

function getKzBadge(kz) {
    const colors = {
        'London': 'bg-primary',
        'NY AM': 'bg-info',
        'NY PM': 'bg-warning text-dark',
        'Asian': 'bg-secondary',
        'Off-Session': 'bg-dark',
    };
    return `<span class="badge ${colors[kz] || 'bg-secondary'}">${kz || 'Unknown'}</span>`;
}

function getGuardianBadge(guardian) {
    const map = {
        'Sniper Buy': '<span class="badge bg-success">Sniper Buy</span>',
        'Sniper Sell': '<span class="badge bg-danger">Sniper Sell</span>',
        'Retrace Buy': '<span class="badge" style="background:#1a6b3c">Retrace Buy</span>',
        'Retrace Sell': '<span class="badge" style="background:#8b2020">Retrace Sell</span>',
        'Trap Buy': '<span class="badge bg-warning text-dark">Trap Buy</span>',
        'Trap Sell': '<span class="badge bg-warning text-dark">Trap Sell</span>',
        'Waiting': '<span class="badge bg-dark">Waiting</span>',
    };
    return map[guardian] || `<span class="badge bg-secondary">${guardian || 'Unknown'}</span>`;
}

function getOppStatusBadge(status) {
    const map = {
        'identified': '<span class="badge bg-info">Identified</span>',
        'active': '<span class="badge badge-active">Active</span>',
        'tp_hit': '<span class="badge badge-won">TP Hit</span>',
        'sl_hit': '<span class="badge badge-lost">SL Hit</span>',
        'expired': '<span class="badge badge-timeout">Expired</span>',
    };
    return map[status] || `<span class="badge bg-secondary">${status}</span>`;
}

// ============================================================
// Pagination
// ============================================================

function updatePagination(data) {
    const total = data.total || 0;
    document.getElementById('opp-info').textContent =
        `Showing ${total > 0 ? currentOffset + 1 : 0}-${Math.min(currentOffset + pageSize, total)} of ${total}`;
    document.getElementById('btn-prev').disabled = currentOffset === 0;
    document.getElementById('btn-next').disabled = currentOffset + pageSize >= total;
}

function prevPage() { currentOffset = Math.max(0, currentOffset - pageSize); loadOpportunities(); }
function nextPage() { currentOffset += pageSize; loadOpportunities(); }

// ============================================================
// Detail Modal
// ============================================================

async function showOppDetail(oppId) {
    const modal = new bootstrap.Modal(document.getElementById('oppModal'));
    document.getElementById('opp-modal-title').textContent = `Opportunity #${oppId}`;
    document.getElementById('opp-modal-body').innerHTML = 'Loading...';
    modal.show();

    try {
        const res = await fetch(`/dash/api/oie/opportunity/${oppId}`);
        const o = await res.json();
        renderOppDetail(o);
    } catch (err) {
        document.getElementById('opp-modal-body').innerHTML = '<div class="text-danger">Error loading opportunity</div>';
    }
}

function renderOppDetail(o) {
    const html = `
    <div class="row g-3">
        <div class="col-md-6">
            <h6><i class="bi bi-info-circle me-1"></i> Signal Info</h6>
            <table class="table table-sm table-dark">
                <tr><td class="text-muted">Pair</td><td><strong>${o.pair}</strong></td></tr>
                <tr><td class="text-muted">Setup Type</td><td>${getSetupBadge(o.setup_type)}</td></tr>
                <tr><td class="text-muted">H4 Bias</td><td>${getBiasBadge(o.h4_bias)}</td></tr>
                <tr><td class="text-muted">P&D Zone</td><td>${getZoneBadge(o.pd_zone)}</td></tr>
                <tr><td class="text-muted">Kill Zone</td><td>${getKzBadge(o.kill_zone)}</td></tr>
                <tr><td class="text-muted">Guardian</td><td>${getGuardianBadge(o.guardian)}</td></tr>
                <tr><td class="text-muted">Status</td><td>${getOppStatusBadge(o.status)}</td></tr>
                <tr><td class="text-muted">Version</td><td><code>${o.version || 'unknown'}</code></td></tr>
            </table>
        </div>
        <div class="col-md-6">
            <h6><i class="bi bi-calculator me-1"></i> Risk / Reward</h6>
            <table class="table table-sm table-dark">
                <tr><td class="text-muted">Entry Price</td><td class="font-monospace">${o.entry_price}</td></tr>
                <tr><td class="text-muted">Stop Loss</td><td class="font-monospace text-danger">${o.sl_price}</td></tr>
                <tr><td class="text-muted">Take Profit</td><td class="font-monospace text-success">${o.tp_price}</td></tr>
                <tr><td class="text-muted">Risk (pips)</td><td>${o.risk_pips}</td></tr>
                <tr><td class="text-muted">Reward (pips)</td><td>${o.reward_pips}</td></tr>
                <tr><td class="text-muted">R:R Ratio</td><td class="fw-bold">${o.rr_ratio}:1</td></tr>
                <tr><td class="text-muted">POI Score</td><td>${o.poi_score != null ? o.poi_score : '—'}</td></tr>
                <tr><td class="text-muted">Quality</td><td>${o.quality_score || '—'}</td></tr>
                <tr><td class="text-muted">Confluence</td><td>${o.confluence || '—'}</td></tr>
            </table>
        </div>
    </div>
    <div class="mt-3">
        <h6><i class="bi bi-clock me-1"></i> Timeline</h6>
        <table class="table table-sm table-dark">
            <tr><td class="text-muted">Identified At</td><td>${o.identified_at ? new Date(o.identified_at).toLocaleString() : '—'}</td></tr>
            <tr><td class="text-muted">Setup ID</td><td><code>${o.setup_id || '—'}</code></td></tr>
        </table>
    </div>`;
    document.getElementById('opp-modal-body').innerHTML = html;
}
