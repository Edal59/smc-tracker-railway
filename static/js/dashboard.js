// SMC Performance Tracker — Dashboard JS

let pnlChart = null;
let statusChart = null;

document.addEventListener('DOMContentLoaded', () => {
    loadDashboard();
});

function getFilters() {
    const pair = document.getElementById('filter-pair').value;
    const days = document.getElementById('filter-days').value;
    let params = new URLSearchParams();
    if (pair) params.set('pair', pair);
    if (days) params.set('days', days);
    return params.toString();
}

async function loadDashboard() {
    const qs = getFilters();
    try {
        const [metricsRes, pnlRes, signalsRes] = await Promise.all([
            fetch(`/dash/api/metrics?${qs}`),
            fetch(`/dash/api/pnl?${qs}`),
            fetch(`/dash/api/signals?limit=10`),
        ]);

        const metrics = await metricsRes.json();
        const pnl = await pnlRes.json();
        const signals = await signalsRes.json();

        updateSummaryCards(metrics);
        updatePnlChart(pnl.data);
        updateStatusChart(metrics.summary);
        updateAdvancedMetrics(metrics);
        updateBreakdowns(metrics.breakdowns);
        updateRecentSignals(signals.signals);
    } catch (err) {
        console.error('Dashboard load error:', err);
    }
}

function updateSummaryCards(metrics) {
    const s = metrics.summary || {};
    document.getElementById('stat-total').textContent = s.total_signals || 0;
    
    const wr = (s.win_rate || 0).toFixed(1);
    const wrEl = document.getElementById('stat-winrate');
    wrEl.textContent = wr + '%';
    wrEl.className = `fs-3 fw-bold ${parseFloat(wr) >= 50 ? 'text-success' : 'text-danger'}`;
    
    document.getElementById('stat-wl').textContent = `${s.wins || 0} / ${s.losses || 0}`;
    
    const exp = (s.expectancy || 0).toFixed(2);
    const expEl = document.getElementById('stat-expectancy');
    expEl.textContent = exp + 'R';
    expEl.className = `fs-3 fw-bold ${parseFloat(exp) >= 0 ? 'text-success' : 'text-danger'}`;
    
    const pf = (s.profit_factor || 0);
    document.getElementById('stat-pf').textContent = pf === Infinity ? '∞' : pf.toFixed(2);
    
    document.getElementById('stat-active').textContent = metrics.active_signals || 0;
}

function updatePnlChart(data) {
    const emptyEl = document.getElementById('pnl-empty');
    if (!data || data.length === 0) {
        emptyEl.style.display = 'block';
        return;
    }
    emptyEl.style.display = 'none';
    
    const labels = data.map((d, i) => i + 1);
    const values = data.map(d => d.cumulative_rr);
    const colors = values.map(v => v >= 0 ? 'rgba(63, 185, 80, 0.8)' : 'rgba(248, 81, 73, 0.8)');
    
    const ctx = document.getElementById('pnl-chart').getContext('2d');
    if (pnlChart) pnlChart.destroy();
    pnlChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: [{
                label: 'Cumulative R:R',
                data: values,
                borderColor: '#3fb950',
                backgroundColor: 'rgba(63, 185, 80, 0.1)',
                fill: true,
                tension: 0.3,
                pointRadius: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: (ctx) => {
                            const d = data[ctx.dataIndex];
                            return `${d.pair} ${d.direction} — ${d.status} (${d.cumulative_rr}R)`;
                        }
                    }
                }
            },
            scales: {
                x: { display: true, title: { display: true, text: 'Signal #', color: '#8b949e' }, grid: { color: '#21262d' }, ticks: { color: '#8b949e' } },
                y: { title: { display: true, text: 'Cumulative R:R', color: '#8b949e' }, grid: { color: '#21262d' }, ticks: { color: '#8b949e' } }
            }
        }
    });
}

function updateStatusChart(summary) {
    const emptyEl = document.getElementById('status-empty');
    if (!summary || summary.total_signals === 0) {
        emptyEl.style.display = 'block';
        return;
    }
    emptyEl.style.display = 'none';
    
    const ctx = document.getElementById('status-chart').getContext('2d');
    if (statusChart) statusChart.destroy();
    statusChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Won', 'Lost', 'Timeout', 'Get Out'],
            datasets: [{
                data: [summary.wins || 0, summary.losses || 0, summary.timeouts || 0, summary.get_outs || 0],
                backgroundColor: ['#238636', '#da3633', '#d29922', '#8957e5'],
                borderWidth: 0,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { position: 'bottom', labels: { color: '#8b949e', padding: 15 } }
            }
        }
    });
}

function updateAdvancedMetrics(metrics) {
    const adv = metrics.advanced || {};
    const streaks = metrics.streaks || {};
    const rows = [
        ['Sharpe Ratio', (adv.sharpe_ratio || 0).toFixed(3)],
        ['Max Drawdown', (adv.max_drawdown_rr || 0).toFixed(2) + 'R'],
        ['Recovery Factor', (adv.recovery_factor || 0).toFixed(2)],
        ['Total R:R', (adv.total_rr || 0).toFixed(2) + 'R'],
        ['Avg MFE', (adv.avg_mfe_pips || 0).toFixed(1) + ' pips'],
        ['Avg MAE', (adv.avg_mae_pips || 0).toFixed(1) + ' pips'],
        ['Current Streak', `${streaks.current_streak || 0} ${streaks.current_streak_type || ''}`],
        ['Max Win Streak', streaks.max_win_streak || 0],
        ['Max Loss Streak', streaks.max_loss_streak || 0],
    ];
    const tbody = document.getElementById('advanced-table');
    tbody.innerHTML = rows.map(([k, v]) => 
        `<tr><td class="text-muted">${k}</td><td class="text-end fw-bold">${v}</td></tr>`
    ).join('');
}

function updateBreakdowns(breakdowns) {
    if (!breakdowns) return;
    renderBreakdown('session-breakdown', breakdowns.by_session);
    renderBreakdown('direction-breakdown', breakdowns.by_direction);
}

function renderBreakdown(containerId, data) {
    const el = document.getElementById(containerId);
    if (!data || Object.keys(data).length === 0) {
        el.innerHTML = '<div class="text-muted text-center">No data</div>';
        return;
    }
    let html = '<table class="table table-sm table-dark mb-0"><thead><tr><th>Category</th><th>Wins</th><th>Total</th><th>Win Rate</th></tr></thead><tbody>';
    for (const [key, val] of Object.entries(data)) {
        const wrClass = val.win_rate >= 50 ? 'text-success' : 'text-danger';
        html += `<tr><td>${key}</td><td>${val.wins}</td><td>${val.total}</td><td class="${wrClass} fw-bold">${val.win_rate.toFixed(1)}%</td></tr>`;
    }
    html += '</tbody></table>';
    el.innerHTML = html;
}

function updateRecentSignals(signals) {
    const tbody = document.getElementById('recent-signals');
    if (!signals || signals.length === 0) {
        tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted py-4">No signals yet. Configure TradingView alerts to get started!</td></tr>';
        return;
    }
    tbody.innerHTML = signals.map(s => {
        const statusBadge = getStatusBadge(s.status);
        const dirClass = s.direction === 'LONG' ? 'text-success' : 'text-danger';
        const rrText = s.actual_rr != null ? (s.actual_rr >= 0 ? '+' : '') + s.actual_rr.toFixed(2) + 'R' : '—';
        const rrClass = s.actual_rr != null ? (s.actual_rr >= 0 ? 'text-success' : 'text-danger') : '';
        const pipsText = s.pips_gained != null ? (s.pips_gained >= 0 ? '+' : '') + s.pips_gained.toFixed(1) : '—';
        const ts = s.signal_timestamp ? new Date(s.signal_timestamp).toLocaleString() : '—';
        return `<tr>
            <td class="small">${ts}</td>
            <td><strong>${s.pair}</strong></td>
            <td class="${dirClass} fw-bold">${s.direction}</td>
            <td class="small">${s.signal_type || '—'}</td>
            <td>${s.entry_price || '—'}</td>
            <td>${s.poi_score != null ? s.poi_score + '/7' : '—'}</td>
            <td>${statusBadge}</td>
            <td class="${rrClass} fw-bold">${rrText}</td>
            <td>${pipsText}</td>
        </tr>`;
    }).join('');
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
