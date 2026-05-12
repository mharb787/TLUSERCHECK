/* ── State ── */
let activeTf = '1h';
let liveEnabled = true;
let liveTimer = null;
let analysisTimer = null;
let analysisInFlight = false;

/* ── DOM refs ── */
const coinSelect       = document.getElementById('coinSelect');
const analyzeBtn       = document.getElementById('analyzeBtn');
const loader           = document.getElementById('loader');
const statsRow         = document.getElementById('statsRow');
const predictedSection = document.getElementById('predictedSection');
const chartDiv         = document.getElementById('chartDiv');
const chartPlaceholder = document.getElementById('chartPlaceholder');
const coinGrid         = document.getElementById('coinGrid');
const liveToggle       = document.getElementById('liveToggle');
const livePrice        = document.getElementById('livePrice');
const liveChange       = document.getElementById('liveChange');
const liveSignal       = document.getElementById('liveSignal');
const liveUpdated      = document.getElementById('liveUpdated');

/* ── Timeframe buttons ── */
document.getElementById('tfButtons').addEventListener('click', e => {
  if (!e.target.matches('.tf-btn')) return;
  document.querySelectorAll('.tf-btn').forEach(b => b.classList.remove('active'));
  e.target.classList.add('active');
  activeTf = e.target.dataset.tf;
  refreshLive();
  runAnalysis(coinSelect.value, activeTf, { silent: true });
});

/* ── Analyze button ── */
analyzeBtn.addEventListener('click', () => runAnalysis(coinSelect.value, activeTf));

coinSelect.addEventListener('change', () => {
  refreshLive();
  runAnalysis(coinSelect.value, activeTf, { silent: true });
});

liveToggle.addEventListener('click', () => {
  liveEnabled = !liveEnabled;
  liveToggle.classList.toggle('active', liveEnabled);
  liveToggle.textContent = liveEnabled ? 'حي: يعمل' : 'حي: متوقف';
  if (liveEnabled) {
    startLiveMode();
  } else {
    stopLiveMode();
  }
});

/* ── Click coin card → auto analyze ── */
coinGrid.addEventListener('click', e => {
  const chip = e.target.closest('.coin-chip');
  if (!chip) return;
  const sym = chip.dataset.symbol;
  coinSelect.value = sym;
  runAnalysis(sym, activeTf);
  refreshLive();
  window.scrollTo({ top: 0, behavior: 'smooth' });
});

/* ── Dashboard refresh ── */
document.getElementById('refreshDash').addEventListener('click', loadDashboard);

/* ══════════════════════════════════════════════════
   MAIN ANALYSIS
══════════════════════════════════════════════════ */
async function runAnalysis(symbol, tf, options = {}) {
  if (analysisInFlight) return;
  analysisInFlight = true;
  if (!options.silent) showLoader(true);
  try {
    const res  = await fetch(`/api/analyze?symbol=${symbol}&tf=${tf}`);
    const data = await res.json();

    if (data.error) {
      if (!options.silent) alert('خطأ: ' + data.error);
      return;
    }

    renderStats(data);
    renderPredicted(data.predicted);
    renderChart(data.chart);
  } catch (err) {
    if (!options.silent) alert('تعذر الاتصال بالخادم: ' + err.message);
  } finally {
    analysisInFlight = false;
    if (!options.silent) showLoader(false);
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

async function refreshLive() {
  if (!liveEnabled) return;
  try {
    const res = await fetch(`/api/live?symbol=${coinSelect.value}&tf=${activeTf}`);
    const data = await res.json();
    if (data.error) throw new Error(data.error);

    livePrice.textContent = fmt(data.price);
    const change = Number(data.change_pct || 0);
    liveChange.textContent = `${change.toFixed(2)}%`;
    liveChange.style.color = change >= 0 ? '#00C853' : '#D50000';
    liveSignal.textContent = `${data.signal.label} ${data.signal.strength}%`;
    liveSignal.style.color = data.signal.color;
    liveUpdated.textContent = new Date().toLocaleTimeString('ar', {
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
    });
  } catch (err) {
    liveUpdated.textContent = 'فشل التحديث';
  }
}

function startLiveMode() {
  stopLiveMode();
  refreshLive();
  runAnalysis(coinSelect.value, activeTf, { silent: true });
  liveTimer = setInterval(refreshLive, 5000);
  analysisTimer = setInterval(() => {
    runAnalysis(coinSelect.value, activeTf, { silent: true });
    loadDashboard({ silent: true });
  }, 30000);
}

function stopLiveMode() {
  if (liveTimer) clearInterval(liveTimer);
  if (analysisTimer) clearInterval(analysisTimer);
  liveTimer = null;
  analysisTimer = null;
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
async function loadDashboard(options = {}) {
  if (!options.silent) {
    coinGrid.innerHTML = '<div class="loading-msg">جارٍ تحميل الإشارات...</div>';
  }
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
startLiveMode();
