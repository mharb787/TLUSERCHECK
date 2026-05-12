/* ── State ── */
let activeTf = '1h';

/* ── DOM refs ── */
const coinSelect       = document.getElementById('coinSelect');
const analyzeBtn       = document.getElementById('analyzeBtn');
const loader           = document.getElementById('loader');
const statsRow         = document.getElementById('statsRow');
const predictedSection = document.getElementById('predictedSection');
const chartDiv         = document.getElementById('chartDiv');
const chartPlaceholder = document.getElementById('chartPlaceholder');
const coinGrid         = document.getElementById('coinGrid');

/* ── Timeframe buttons ── */
document.getElementById('tfButtons').addEventListener('click', e => {
  if (!e.target.matches('.tf-btn')) return;
  document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
  e.target.classList.add('active');
  activeTf = e.target.dataset.tf;
});

/* ── Analyze button ── */
analyzeBtn.addEventListener('click', () => runAnalysis(coinSelect.value, activeTf));

/* ── Click coin card → auto analyze ── */
coinGrid.addEventListener('click', e => {
  const chip = e.target.closest('.coin-chip');
  if (!chip) return;
  const sym = chip.dataset.symbol;
  coinSelect.value = sym;
  runAnalysis(sym, activeTf);
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

/* ── Dashboard refresh ── */
document.getElementById('refreshDash').addEventListener('click', loadDashboard);

/* ══════════════════════════════════════════════════
   MAIN ANALYSIS
══════════════════════════════════════════════════ */
async function runAnalysis(symbol, tf) {
  showLoader(true);
  try {
    const res  = await fetch(`/api/analyze?symbol=${symbol}&tf=${tf}`);
    const data = await res.json();

    if (data.error) { alert('خطأ: ' + data.error); return; }

    renderStats(data);
    renderPredicted(data.predicted);
    renderChart(data.chart);
  } catch (err) {
    alert('تعذّر الاتصال بالخادم: ' + err.message);
  } finally {
    showLoader(false);
  }
}

function renderStats(data) {
  const { signal, backtest } = data;

  const sigEl = document.getElementById('valSignal');
  sigEl.textContent       = signal.label;
  sigEl.style.color       = signal.color;

  document.getElementById('valStrength').textContent = signal.strength + '%';
  document.getElementById('valAcc').textContent      = backtest.accuracy + '%';

  const buyEl  = document.getElementById('valBuyAcc');
  const sellEl = document.getElementById('valSellAcc');
  buyEl.textContent  = backtest.buy_acc  + '%';
  sellEl.textContent = backtest.sell_acc + '%';
  document.getElementById('valSigs').textContent = backtest.signals;

  statsRow.style.display = 'flex';
}

function renderPredicted(candles) {
  const container = document.getElementById('candleCards');
  container.innerHTML = candles.map(c => `
    <div class="candle-card" style="border-top: 3px solid ${c.color}">
      <div class="cc-title" style="color:${c.color}">شمعة #${c.candle_index}</div>
      <div class="cc-row"><span>افتتاح</span><span>${fmt(c.open)}</span></div>
      <div class="cc-row"><span>أعلى</span>  <span>${fmt(c.high)}</span></div>
      <div class="cc-row"><span>أدنى</span>  <span>${fmt(c.low)}</span></div>
      <div class="cc-row"><span>إغلاق</span><span>${fmt(c.close)}</span></div>
    </div>
  `).join('');
  predictedSection.style.display = 'block';
}

function renderChart(chartJson) {
  const parsed = JSON.parse(chartJson);
  chartPlaceholder.style.display = 'none';
  chartDiv.style.display = 'block';
  Plotly.react(chartDiv, parsed.data, parsed.layout, { responsive: true });
}

/* ══════════════════════════════════════════════════
   DASHBOARD
══════════════════════════════════════════════════ */
async function loadDashboard() {
  coinGrid.innerHTML = '<div class="loading-msg">جارٍ تحميل الإشارات…</div>';
  try {
    const res   = await fetch(`/api/coins?tf=${activeTf}`);
    const coins = await res.json();

    coinGrid.innerHTML = coins.map(c => {
      const cls   = c.rec === 'BUY' ? 'buy' : c.rec === 'SELL' ? 'sell' : 'neutral';
      const label = c.rec === 'BUY' ? 'شراء 📈' : c.rec === 'SELL' ? 'بيع 📉' : 'محايد ↔';
      return `
        <div class="coin-chip" data-symbol="${c.symbol}">
          <div class="chip-symbol">${c.symbol}</div>
          <div class="chip-name">${c.name}</div>
          <span class="chip-badge ${cls}">${label}</span>
          <div class="chip-strength">قوة: ${c.strength}%</div>
        </div>`;
    }).join('');
  } catch {
    coinGrid.innerHTML = '<div class="loading-msg">تعذّر تحميل البيانات</div>';
  }
}

/* ── Helpers ── */
function showLoader(v) { loader.style.display = v ? 'flex' : 'none'; }

function fmt(n) {
  if (n >= 1000) return n.toLocaleString('en', { maximumFractionDigits: 2 });
  if (n >= 1)    return n.toFixed(4);
  return n.toFixed(6);
}

/* ── Init ── */
loadDashboard();
