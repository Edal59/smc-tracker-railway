// SMC Performance Tracker — Trade Log JS

let currentOffset = 0;
const pageSize = 50;

document.addEventListener('DOMContentLoaded', () => {
    loadSignals();
});

function getFilters() {
    const pair = document.getElementById('filter-pair').value;
    const status = document.getElementById('filter-status').value;
    let params = new URLSearchParams();
    if (pair) params.set('pair', pair);
    if (status) params.set('status', status);
    return params;
}

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
        tbody.innerHTML = '<tr><td colspan="13" class="text-center text-muted py-4">No signals found</td></tr>';
        return;
    }
    tbody.innerHTML = signals.map(s => {
        const statusBadge = getStatusBadge(s.status);
        const dirClass = s.direction === 'LONG' ? 'text-success' : 'text-danger';
        const rrText = s.actual_rr != null ? (s.actual_rr >= 0 ? '+' : '') + s.actual_rr.toFixed(2) + 'R' : '—';
        const rrClass = s.actual_rr != null ? (s.actual_rr >= 0 ? 'text-success' : 'text-danger') : '';
        const pipsText = s.pips_gained != null ? (s.pips_gained >= 0 ? '+' : '') + s.pips_gained.toFixed(1) : '—';
        const ts = s.signal_timestamp ? new Date(s.signal_timestamp).toLocaleString() : '—';
        return `<tr style="cursor:pointer" onclick="showDetail('${s.signal_id}')">
            <td class="small">${ts}</td>
            <td class="small font-monospace">${(s.signal_id || '').substring(0, 20)}...</td>
            <td><strong>${s.pair}</strong></td>
            <td class="${dirClass} fw-bold">${s.direction}</td>
            <td class="small">${s.signal_type || '—'}</td>
            <td>${s.entry_price || '—'}</td>
            <td>${s.stop_loss || '—'}</td>
            <td>${s.take_profit || '—'}</td>
            <td>${s.poi_score != null ? s.poi_score + '/7' : '—'}</td>
            <td class="small">${s.kill_zone || '—'}</td>
            <td>${statusBadge}</td>
            <td class="${rrClass} fw-bold">${rrText}</td>
            <td>${pipsText}</td>
        </tr>`;
    }).join('');
}

function updatePagination(data) {
    document.getElementById('signals-info').textContent = 
        `Showing ${currentOffset + 1}-${Math.min(currentOffset + pageSize, data.total)} of ${data.total} signals`;
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
                <tr><td class="text-muted">Status</td><td>${statusBadge}</td></tr>
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
    
    if (s.actual_rr != null || s.pips_gained != null) {
        html += `
        <h6 class="mt-3">Outcome</h6>
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
