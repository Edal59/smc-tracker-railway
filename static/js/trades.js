// SMC Performance Tracker — Trade Log JS (with Manual Trade Tracking)

let currentOffset = 0;
const pageSize = 50;

document.addEventListener('DOMContentLoaded', () => {
    loadSignals();
    loadAnalytics();

    // Auto-reload on filter changes
    document.getElementById('filter-pair').addEventListener('change', () => { currentOffset = 0; loadSignals(); loadAnalytics(); });
    document.getElementById('filter-status').addEventListener('change', () => { currentOffset = 0; loadSignals(); });
    document.getElementById('filter-trade-status').addEventListener('change', () => { currentOffset = 0; loadSignals(); });
});

function getFilters() {
    const pair = document.getElementById('filter-pair').value;
    const status = document.getElementById('filter-status').value;
    const tradeStatus = document.getElementById('filter-trade-status').value;
    let params = new URLSearchParams();
    if (pair) params.set('pair', pair);
    if (status) params.set('status', status);
    if (tradeStatus) params.set('trade_status', tradeStatus);
    return params;
}

// ============================================================
// Analytics
// ============================================================

async function loadAnalytics() {
    try {
        const pair = document.getElementById('filter-pair').value;
        let url = '/dash/api/analytics';
        if (pair) url += `?pair=${pair}`;
        const res = await fetch(url);
        const data = await res.json();
        updateAnalytics(data);
    } catch (err) {
        console.error('Analytics load error:', err);
    }
}

function updateAnalytics(a) {
    document.getElementById('stat-total').textContent = a.total_signals || 0;
    document.getElementById('stat-taken').textContent = `${a.taken_count || 0} (${a.taken_pct || 0}%)`;
    document.getElementById('stat-missed').textContent = `${a.missed_count || 0} (${a.missed_pct || 0}%)`;
    document.getElementById('stat-ignored').textContent = `${a.ignored_count || 0} (${a.ignored_pct || 0}%)`;
    document.getElementById('stat-pending').textContent = `${a.pending_count || 0} (${a.pending_pct || 0}%)`;

    document.getElementById('stat-actual-wr').textContent = `${a.actual_win_rate || 0}%`;
    document.getElementById('stat-theo-wr').textContent = `${a.theoretical_win_rate || 0}%`;
    document.getElementById('stat-actual-wl').textContent = `${a.actual_wins || 0}/${a.actual_losses || 0}`;
    document.getElementById('stat-theo-wl').textContent = `${a.theoretical_wins || 0}/${a.theoretical_losses || 0}`;

    const actualPnl = a.actual_total_pnl || 0;
    const theoPnl = a.theoretical_total_pnl || 0;
    document.getElementById('stat-actual-pnl').textContent = (actualPnl >= 0 ? '+' : '') + actualPnl.toFixed(1);
    document.getElementById('stat-actual-pnl').className = actualPnl >= 0 ? 'text-success' : 'text-danger';
    document.getElementById('stat-theo-pnl').textContent = (theoPnl >= 0 ? '+' : '') + theoPnl.toFixed(1);
    document.getElementById('stat-theo-pnl').className = theoPnl >= 0 ? 'text-success' : 'text-danger';

    const actualAvg = a.actual_avg_pnl || 0;
    const theoAvg = a.theoretical_avg_pnl || 0;
    document.getElementById('stat-actual-avg').textContent = (actualAvg >= 0 ? '+' : '') + actualAvg.toFixed(1);
    document.getElementById('stat-actual-avg').className = actualAvg >= 0 ? 'text-success' : 'text-danger';
    document.getElementById('stat-theo-avg').textContent = (theoAvg >= 0 ? '+' : '') + theoAvg.toFixed(1);
    document.getElementById('stat-theo-avg').className = theoAvg >= 0 ? 'text-success' : 'text-danger';
}

// ============================================================
// Signals Table
// ============================================================

async function loadSignals() {
    const params = getFilters();
    params.set('limit', pageSize);
    params.set('offset', currentOffset);

    try {
        const res = await fetch(`/dash/api/signals?${params.toString()}`);
        const data = await res.json();
        renderSignals(data.signals);
        updatePagination(data);
    } catch (err) {
        console.error('Load signals error:', err);
    }
}

function renderSignals(signals) {
    const tbody = document.getElementById('signals-table');
    if (!signals || signals.length === 0) {
        tbody.innerHTML = '<tr><td colspan="15" class="text-center text-muted py-4">No signals found</td></tr>';
        return;
    }
    tbody.innerHTML = signals.map(s => {
        const statusBadge = getStatusBadge(s.status);
        const tradeBadge = getTradeBadge(s.trade_status);
        const dirClass = s.direction === 'LONG' ? 'text-success' : 'text-danger';
        const rrText = s.actual_rr != null ? (s.actual_rr >= 0 ? '+' : '') + s.actual_rr.toFixed(2) + 'R' : '—';
        const rrClass = s.actual_rr != null ? (s.actual_rr >= 0 ? 'text-success' : 'text-danger') : '';
        const pipsText = s.pips_gained != null ? (s.pips_gained >= 0 ? '+' : '') + s.pips_gained.toFixed(1) : '—';
        const ts = s.signal_timestamp ? new Date(s.signal_timestamp).toLocaleString() : '—';
        const borderClass = getTradeRowBorder(s.trade_status);

        // Action buttons
        const actions = buildActionButtons(s);

        // Show actual PnL for taken trades
        let pnlInfo = '';
        if (s.trade_status === 'taken' && s.actual_pnl != null) {
            const pnlClass = s.actual_pnl >= 0 ? 'text-success' : 'text-danger';
            pnlInfo = `<br><small class="${pnlClass}">${s.actual_pnl >= 0 ? '+' : ''}${s.actual_pnl.toFixed(1)}p actual</small>`;
        }

        return `<tr class="${borderClass}">
            <td class="small">${ts}</td>
            <td class="small font-monospace" style="cursor:pointer" onclick="showDetail('${s.signal_id}')">${(s.signal_id || '').substring(0, 20)}...</td>
            <td><strong>${s.pair}</strong></td>
            <td class="${dirClass} fw-bold">${s.direction}</td>
            <td class="small">${s.signal_type || '—'}</td>
            <td>${s.entry_price || '—'}</td>
            <td>${s.stop_loss || '—'}</td>
            <td>${s.take_profit || '—'}</td>
            <td>${s.poi_score != null ? s.poi_score + '/7' : '—'}</td>
            <td class="small">${s.kill_zone || '—'}</td>
            <td>${statusBadge}</td>
            <td class="${rrClass} fw-bold">${rrText}${pnlInfo}</td>
            <td>${pipsText}</td>
            <td>${tradeBadge}</td>
            <td class="text-nowrap">${actions}</td>
        </tr>`;
    }).join('');
}

function buildActionButtons(s) {
    const sid = s.signal_id;
    const ts = s.trade_status || 'pending';

    if (ts === 'taken') {
        return `<button class="btn btn-xs btn-outline-info" onclick="event.stopPropagation(); openTradeModal('${sid}')" title="Edit trade">
                    <i class="bi bi-pencil"></i>
                </button>
                <button class="btn btn-xs btn-outline-secondary" onclick="event.stopPropagation(); quickMark('${sid}', 'pending')" title="Reset">
                    <i class="bi bi-arrow-counterclockwise"></i>
                </button>`;
    }
    if (ts === 'missed' || ts === 'ignored') {
        return `<button class="btn btn-xs btn-outline-secondary" onclick="event.stopPropagation(); quickMark('${sid}', 'pending')" title="Reset to pending">
                    <i class="bi bi-arrow-counterclockwise"></i>
                </button>`;
    }
    // Pending
    return `<button class="btn btn-xs btn-outline-success" onclick="event.stopPropagation(); openTradeModal('${sid}')" title="Took Trade">
                <i class="bi bi-check-circle"></i>
            </button>
            <button class="btn btn-xs btn-outline-warning" onclick="event.stopPropagation(); quickMark('${sid}', 'missed')" title="Missed">
                <i class="bi bi-exclamation-circle"></i>
            </button>
            <button class="btn btn-xs btn-outline-secondary" onclick="event.stopPropagation(); quickMark('${sid}', 'ignored')" title="Ignored">
                <i class="bi bi-dash-circle"></i>
            </button>`;
}

function getTradeRowBorder(tradeStatus) {
    switch (tradeStatus) {
        case 'taken': return 'trade-row-taken';
        case 'missed': return 'trade-row-missed';
        case 'ignored': return 'trade-row-ignored';
        default: return '';
    }
}

function getTradeBadge(tradeStatus) {
    switch (tradeStatus) {
        case 'taken': return '<span class="badge badge-trade-taken">TAKEN</span>';
        case 'missed': return '<span class="badge badge-trade-missed">MISSED</span>';
        case 'ignored': return '<span class="badge badge-trade-ignored">IGNORED</span>';
        case 'pending': return '<span class="badge badge-trade-pending">PENDING</span>';
        default: return '<span class="badge badge-trade-pending">PENDING</span>';
    }
}

function updatePagination(data) {
    document.getElementById('signals-info').textContent =
        `Showing ${data.total > 0 ? currentOffset + 1 : 0}-${Math.min(currentOffset + pageSize, data.total)} of ${data.total} signals`;
    document.getElementById('btn-prev').disabled = currentOffset === 0;
    document.getElementById('btn-next').disabled = currentOffset + pageSize >= data.total;
}

function prevPage() {
    currentOffset = Math.max(0, currentOffset - pageSize);
    loadSignals();
}

function nextPage() {
    currentOffset += pageSize;
    loadSignals();
}

// ============================================================
// Quick Mark (missed/ignored/pending)
// ============================================================

async function quickMark(signalId, status) {
    try {
        const res = await fetch(`/dash/api/signal/${signalId}/mark-trade`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ trade_status: status })
        });
        const data = await res.json();
        if (data.status === 'ok') {
            loadSignals();
            loadAnalytics();
        } else {
            alert('Error: ' + (data.error || 'Unknown error'));
        }
    } catch (err) {
        console.error('Quick mark error:', err);
        alert('Failed to update signal');
    }
}

// ============================================================
// Trade Modal
// ============================================================

async function openTradeModal(signalId) {
    // Fetch signal details to pre-fill
    try {
        const res = await fetch(`/dash/api/signal/${signalId}`);
        const signal = await res.json();

        document.getElementById('trade-signal-id').value = signalId;
        document.getElementById('trade-signal-info').value = `${signal.pair} ${signal.direction} @ ${signal.entry_price}`;

        // Pre-fill with existing data or signal defaults
        document.getElementById('trade-entry-price').value = signal.actual_entry_price || signal.entry_price || '';
        document.getElementById('trade-exit-price').value = signal.actual_exit_price || '';

        // Pre-fill times
        if (signal.actual_entry_time) {
            document.getElementById('trade-entry-time').value = signal.actual_entry_time.slice(0, 16);
        } else if (signal.signal_timestamp) {
            document.getElementById('trade-entry-time').value = signal.signal_timestamp.slice(0, 16);
        } else {
            document.getElementById('trade-entry-time').value = '';
        }
        document.getElementById('trade-exit-time').value = signal.actual_exit_time ? signal.actual_exit_time.slice(0, 16) : '';
        document.getElementById('trade-notes').value = signal.trade_notes || '';

        const modal = new bootstrap.Modal(document.getElementById('tradeModal'));
        modal.show();
    } catch (err) {
        console.error('Open trade modal error:', err);
        alert('Failed to load signal details');
    }
}

async function submitTrade() {
    const signalId = document.getElementById('trade-signal-id').value;
    const payload = {
        trade_status: 'taken',
        actual_entry_price: parseFloat(document.getElementById('trade-entry-price').value) || null,
        actual_exit_price: parseFloat(document.getElementById('trade-exit-price').value) || null,
        actual_entry_time: document.getElementById('trade-entry-time').value || null,
        actual_exit_time: document.getElementById('trade-exit-time').value || null,
        trade_notes: document.getElementById('trade-notes').value || null,
    };

    try {
        const res = await fetch(`/dash/api/signal/${signalId}/mark-trade`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        const data = await res.json();
        if (data.status === 'ok') {
            // Close modal
            const modal = bootstrap.Modal.getInstance(document.getElementById('tradeModal'));
            if (modal) modal.hide();
            loadSignals();
            loadAnalytics();
        } else {
            alert('Error: ' + (data.error || 'Unknown error'));
        }
    } catch (err) {
        console.error('Submit trade error:', err);
        alert('Failed to save trade');
    }
}

// ============================================================
// Signal Detail Modal
// ============================================================

async function showDetail(signalId) {
    const modal = new bootstrap.Modal(document.getElementById('signalModal'));
    document.getElementById('modal-title').textContent = `Signal: ${signalId}`;
    document.getElementById('modal-body').innerHTML = 'Loading...';
    modal.show();

    try {
        const res = await fetch(`/dash/api/signal/${signalId}`);
        const data = await res.json();
        renderDetail(data);
    } catch (err) {
        document.getElementById('modal-body').innerHTML = '<div class="text-danger">Error loading signal</div>';
    }
}

function renderDetail(s) {
    const statusBadge = getStatusBadge(s.status);
    const tradeBadge = getTradeBadge(s.trade_status);
    const dirClass = s.direction === 'LONG' ? 'text-success' : 'text-danger';

    let html = `
    <div class="row g-3">
        <div class="col-md-6">
            <h6>Signal Info</h6>
            <table class="table table-sm table-dark">
                <tr><td class="text-muted">Pair</td><td><strong>${s.pair}</strong></td></tr>
                <tr><td class="text-muted">Direction</td><td class="${dirClass} fw-bold">${s.direction}</td></tr>
                <tr><td class="text-muted">Type</td><td>${s.signal_type || '—'}</td></tr>
                <tr><td class="text-muted">Entry Price</td><td>${s.entry_price}</td></tr>
                <tr><td class="text-muted">Stop Loss</td><td>${s.stop_loss}</td></tr>
                <tr><td class="text-muted">Take Profit</td><td>${s.take_profit}</td></tr>
                <tr><td class="text-muted">SL Pips</td><td>${s.sl_distance_pips || '—'}</td></tr>
                <tr><td class="text-muted">TP Pips</td><td>${s.tp_distance_pips || '—'}</td></tr>
                <tr><td class="text-muted">Target R:R</td><td>${s.target_rr || '—'}</td></tr>
                <tr><td class="text-muted">Signal Status</td><td>${statusBadge}</td></tr>
                <tr><td class="text-muted">Trade Status</td><td>${tradeBadge}</td></tr>
            </table>
        </div>
        <div class="col-md-6">
            <h6>SMC Analysis</h6>
            <table class="table table-sm table-dark">
                <tr><td class="text-muted">POI Score</td><td>${s.poi_score != null ? s.poi_score + '/7' : '—'}</td></tr>
                <tr><td class="text-muted">Structure</td><td>${s.structure || '—'}</td></tr>
                <tr><td class="text-muted">Zone</td><td>${s.zone || '—'}</td></tr>
                <tr><td class="text-muted">Kill Zone</td><td>${s.kill_zone || '—'}</td></tr>
                <tr><td class="text-muted">Entry Model</td><td>${s.entry_model || '—'}</td></tr>
                <tr><td class="text-muted">AMD Phase</td><td>${s.amd_phase || '—'}</td></tr>
                <tr><td class="text-muted">Fib Zone</td><td>${s.fib_zone || '—'}</td></tr>
                <tr><td class="text-muted">Reversal Risk</td><td>${s.reversal_risk || '—'}</td></tr>
                <tr><td class="text-muted">Session</td><td>${s.session || '—'}</td></tr>
            </table>
        </div>
    </div>`;

    // Trade tracking details
    if (s.trade_status === 'taken') {
        html += `
        <h6 class="mt-3"><i class="bi bi-graph-up me-1"></i> Trade Details</h6>
        <table class="table table-sm table-dark">
            <tr><td class="text-muted">Actual Entry</td><td>${s.actual_entry_price || '—'}</td></tr>
            <tr><td class="text-muted">Actual Exit</td><td>${s.actual_exit_price || '—'}</td></tr>
            <tr><td class="text-muted">Entry Time</td><td>${s.actual_entry_time || '—'}</td></tr>
            <tr><td class="text-muted">Exit Time</td><td>${s.actual_exit_time || '—'}</td></tr>
            <tr><td class="text-muted">Actual P&L</td><td class="fw-bold ${(s.actual_pnl || 0) >= 0 ? 'text-success' : 'text-danger'}">${s.actual_pnl != null ? (s.actual_pnl >= 0 ? '+' : '') + s.actual_pnl.toFixed(1) + ' pips' : '—'}</td></tr>
            <tr><td class="text-muted">Notes</td><td>${s.trade_notes || '—'}</td></tr>
        </table>`;
    }

    if (s.actual_rr != null || s.pips_gained != null) {
        html += `
        <h6 class="mt-3">Theoretical Outcome</h6>
        <table class="table table-sm table-dark">
            <tr><td class="text-muted">Actual R:R</td><td class="fw-bold ${(s.actual_rr || 0) >= 0 ? 'text-success' : 'text-danger'}">${s.actual_rr != null ? s.actual_rr.toFixed(2) + 'R' : '—'}</td></tr>
            <tr><td class="text-muted">Pips Gained</td><td>${s.pips_gained != null ? s.pips_gained.toFixed(1) : '—'}</td></tr>
            <tr><td class="text-muted">MFE</td><td>${s.mfe_pips != null ? s.mfe_pips.toFixed(1) + ' pips (' + (s.mfe_rr || 0).toFixed(2) + 'R)' : '—'}</td></tr>
            <tr><td class="text-muted">MAE</td><td>${s.mae_pips != null ? s.mae_pips.toFixed(1) + ' pips (' + (s.mae_rr || 0).toFixed(2) + 'R)' : '—'}</td></tr>
            <tr><td class="text-muted">Bars to Outcome</td><td>${s.bars_to_outcome || '—'}</td></tr>
            <tr><td class="text-muted">Time (min)</td><td>${s.time_to_outcome_min || '—'}</td></tr>
        </table>`;
    }

    if (s.events && s.events.length > 0) {
        html += '<h6 class="mt-3">Events</h6><table class="table table-sm table-dark"><thead><tr><th>Time</th><th>Type</th><th>Price</th></tr></thead><tbody>';
        s.events.forEach(e => {
            html += `<tr><td class="small">${e.event_timestamp}</td><td><span class="badge bg-secondary">${e.event_type}</span></td><td>${e.price_at_event || '—'}</td></tr>`;
        });
        html += '</tbody></table>';
    }

    document.getElementById('modal-body').innerHTML = html;
}

function getStatusBadge(status) {
    const map = {
        'ACTIVE': '<span class="badge badge-active">ACTIVE</span>',
        'WON': '<span class="badge badge-won">WON</span>',
        'LOST': '<span class="badge badge-lost">LOST</span>',
        'TIMEOUT': '<span class="badge badge-timeout">TIMEOUT</span>',
        'GET_OUT': '<span class="badge badge-getout">GET OUT</span>',
    };
    return map[status] || `<span class="badge bg-secondary">${status}</span>`;
}
