<template>
  <div class="tiers-page">
    <div class="page-hdr">
      <h2>模拟账户 — 4 个 Tier 视觉模板</h2>
      <p class="muted">同一份 mock 数据，每个 tier 展示该层"新增专业指标"的视觉摆放，挑你喜欢的 1-2 个。</p>
    </div>

    <!-- ============================================== -->
    <!-- TIER 1：当前数据立即派生 (0 后端工作) -->
    <!-- ============================================== -->
    <section class="tier-section">
      <div class="tier-tag tier-tag-1">Tier 1 · 0 后端改动</div>
      <div class="tier-desc">基础布局 + 当前 API 直接派生：持仓集中度 / 盈亏分布 / 浮盈王 / 浮亏王 / 平均涨幅</div>
      <div class="panel account-panel">
        <div class="panel-hdr">
          <div class="sec-title">
            <span>🇨🇳 A 股模拟账户</span>
            <span class="position-chip num">3 持仓</span>
          </div>
          <span class="sec-link">详情 →</span>
        </div>
        <div class="account-body has-positions">
          <div class="account-money-col">
            <div class="account-hero">
              <div class="hero-label">账户总资产 (¥)</div>
              <div class="hero-val num accent">231,528.53</div>
              <div class="hero-pnl num up">
                <span class="pnl-amount">+¥33,732.00</span>
                <span class="pnl-rate">(+17.05%)</span>
              </div>
              <!-- ⭐ Tier 1 新增：派生 chip 行 -->
              <div class="derive-row">
                <span class="derive-chip"><span class="dim">集中度</span> <span class="num strong">56%</span></span>
                <span class="derive-chip"><span class="up">盈 2</span> <span class="dim">/</span> <span class="down">亏 1</span></span>
                <span class="derive-chip"><span class="dim">均涨</span> <span class="num up">+10.7%</span></span>
              </div>
            </div>
            <div class="account-kpis">
              <div class="kpi-cell">
                <div class="kpi-label">可用现金</div>
                <div class="kpi-val num">¥129,408.53</div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">持仓市值</div>
                <div class="kpi-val num">¥102,120.00</div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">已实现盈亏</div>
                <div class="kpi-val num">+¥0.00</div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">浮动盈亏</div>
                <div class="kpi-val num up">+¥33,732.00</div>
              </div>
              <!-- ⭐ Tier 1 新增：浮盈王 / 浮亏王 -->
              <div class="kpi-cell">
                <div class="kpi-label">浮盈王</div>
                <div class="kpi-val num up">+¥27,300 <span class="kpi-tag">002428</span></div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">浮亏王</div>
                <div class="kpi-val num down">−¥592 <span class="kpi-tag">603009</span></div>
              </div>
            </div>
            <div class="account-progress">
              <div class="progress-label"><span>持仓比例</span><span class="num">44.1%</span></div>
              <div class="progress-bar"><div class="progress-fill" style="width: 44.1%"></div></div>
            </div>
            <button class="primary-btn">开始模拟交易</button>
          </div>
          <div class="account-positions-col">
            <div class="positions-header"><span>持仓明细</span><span class="muted-small">3 只</span></div>
            <div class="positions-list">
              <div v-for="p in mockPositions" :key="p.code" class="position-item">
                <div class="pos-row pos-row-main">
                  <span class="pos-code num">{{ p.code }}</span>
                  <span class="pos-pnl num" :class="p.pnl >= 0 ? 'up' : 'down'">
                    {{ p.pnl >= 0 ? '+' : '−' }}¥{{ formatN(Math.abs(p.pnl)) }}
                  </span>
                </div>
                <div class="pos-row pos-row-meta">
                  <span class="pos-meta">{{ p.qty }} 股 @ ¥{{ p.avg }} <span class="pos-arrow">→</span> ¥{{ p.last }}</span>
                  <span class="pos-pnl-rate" :class="p.rate >= 0 ? 'up' : 'down'">
                    {{ p.rate >= 0 ? '+' : '' }}{{ p.rate }}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================== -->
    <!-- TIER 2：调一个新 API 即可（轻量后端） -->
    <!-- ============================================== -->
    <section class="tier-section">
      <div class="tier-tag tier-tag-2">Tier 2 · 调 getOrders API</div>
      <div class="tier-desc">Tier 1 + 交易行为：累计笔数 / 胜率 / 盈亏比 / 最近交易 / 持仓时长</div>
      <div class="panel account-panel">
        <div class="panel-hdr">
          <div class="sec-title">
            <span>🇨🇳 A 股模拟账户</span>
            <span class="position-chip num">3 持仓</span>
            <span class="position-chip num secondary">23 笔</span>
          </div>
          <span class="sec-link">详情 →</span>
        </div>
        <div class="account-body has-positions">
          <div class="account-money-col">
            <div class="account-hero">
              <div class="hero-label">账户总资产 (¥)</div>
              <div class="hero-val num accent">231,528.53</div>
              <div class="hero-pnl num up">
                <span class="pnl-amount">+¥33,732.00</span>
                <span class="pnl-rate">(+17.05%)</span>
              </div>
              <div class="derive-row">
                <span class="derive-chip"><span class="dim">集中度</span> <span class="num strong">56%</span></span>
                <span class="derive-chip"><span class="dim">胜率</span> <span class="num up strong">67%</span></span>
                <span class="derive-chip"><span class="dim">盈亏比</span> <span class="num strong">1.8</span></span>
              </div>
            </div>
            <div class="account-kpis">
              <div class="kpi-cell">
                <div class="kpi-label">可用现金</div>
                <div class="kpi-val num">¥129,408.53</div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">持仓市值</div>
                <div class="kpi-val num">¥102,120.00</div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">浮动盈亏</div>
                <div class="kpi-val num up">+¥33,732.00</div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">本周交易</div>
                <div class="kpi-val num">5 <span class="kpi-tag">笔</span></div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">浮盈王</div>
                <div class="kpi-val num up">+¥27,300 <span class="kpi-tag">002428</span></div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">累计成交</div>
                <div class="kpi-val num">¥876,432</div>
              </div>
            </div>
            <div class="recent-trade">
              <span class="rt-icon">⏱</span>
              <span class="rt-text"><span class="dim">最近：</span>5h 前 <span class="up">买入</span> 000776 · 1000 股 @ ¥18.25</span>
            </div>
            <div class="account-progress">
              <div class="progress-label"><span>持仓比例</span><span class="num">44.1%</span></div>
              <div class="progress-bar"><div class="progress-fill" style="width: 44.1%"></div></div>
            </div>
            <button class="primary-btn">开始模拟交易</button>
          </div>
          <div class="account-positions-col">
            <div class="positions-header"><span>持仓明细</span><span class="muted-small">3 只 · 平均持有 8 天</span></div>
            <div class="positions-list">
              <div v-for="p in mockPositions" :key="p.code" class="position-item">
                <div class="pos-row pos-row-main">
                  <span class="pos-code num">{{ p.code }}</span>
                  <span class="pos-pnl num" :class="p.pnl >= 0 ? 'up' : 'down'">
                    {{ p.pnl >= 0 ? '+' : '−' }}¥{{ formatN(Math.abs(p.pnl)) }}
                  </span>
                </div>
                <div class="pos-row pos-row-meta">
                  <span class="pos-meta">{{ p.qty }} 股 @ ¥{{ p.avg }} → ¥{{ p.last }} · <span class="dim">持有 {{ p.days }} 天</span></span>
                  <span class="pos-pnl-rate" :class="p.rate >= 0 ? 'up' : 'down'">
                    {{ p.rate >= 0 ? '+' : '' }}{{ p.rate }}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================== -->
    <!-- TIER 3：每日账户快照 (重量后端) -->
    <!-- ============================================== -->
    <section class="tier-section">
      <div class="tier-tag tier-tag-3">Tier 3 · 后端每日快照表</div>
      <div class="tier-desc">资产曲线 / 当前回撤 / 最大回撤 / TWRR / Sharpe / 月度柱图</div>
      <div class="panel account-panel">
        <div class="panel-hdr">
          <div class="sec-title">
            <span>🇨🇳 A 股模拟账户</span>
            <span class="position-chip num">3 持仓</span>
          </div>
          <span class="sec-link">详情 →</span>
        </div>
        <div class="account-body has-positions">
          <div class="account-money-col">
            <div class="account-hero hero-with-chart">
              <div class="hero-info">
                <div class="hero-label">账户总资产 (¥)</div>
                <div class="hero-val num accent">231,528.53</div>
                <div class="hero-pnl num up">
                  <span class="pnl-amount">+¥33,732.00</span>
                  <span class="pnl-rate">(+17.05%)</span>
                </div>
              </div>
              <!-- ⭐ Tier 3 新增：mini 资产曲线 sparkline -->
              <div class="hero-spark">
                <svg viewBox="0 0 120 50" class="spark-svg">
                  <polyline
                    points="0,42 12,40 24,38 36,30 48,32 60,24 72,18 84,22 96,12 108,8 120,5"
                    fill="none"
                    stroke="var(--up)"
                    stroke-width="1.6"
                  />
                  <polyline
                    points="0,42 12,40 24,38 36,30 48,32 60,24 72,18 84,22 96,12 108,8 120,5 120,50 0,50"
                    fill="var(--up)"
                    fill-opacity="0.12"
                    stroke="none"
                  />
                </svg>
                <div class="spark-meta"><span class="dim">90 天</span> <span class="num up">+18.6%</span></div>
              </div>
            </div>
            <div class="account-kpis">
              <div class="kpi-cell">
                <div class="kpi-label">可用现金</div>
                <div class="kpi-val num">¥129,408.53</div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">持仓市值</div>
                <div class="kpi-val num">¥102,120.00</div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">TWRR</div>
                <div class="kpi-val num up">+18.6%</div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">年化收益</div>
                <div class="kpi-val num up">+75.4%</div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">最大回撤</div>
                <div class="kpi-val num down">−8.5%</div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">Sharpe</div>
                <div class="kpi-val num strong">1.42</div>
              </div>
            </div>
            <!-- ⭐ Tier 3 新增：月度收益柱图 -->
            <div class="month-bars">
              <div class="month-bars-label">月度收益</div>
              <div class="month-bars-row">
                <div v-for="m in monthBars" :key="m.month" class="month-bar-cell">
                  <div class="month-bar-track">
                    <div
                      class="month-bar-fill"
                      :class="m.value >= 0 ? 'up' : 'down'"
                      :style="{ height: Math.abs(m.value) * 4 + 'px', bottom: m.value >= 0 ? '50%' : 'auto', top: m.value < 0 ? '50%' : 'auto' }"
                    ></div>
                    <div class="month-bar-axis"></div>
                  </div>
                  <div class="month-bar-label">{{ m.month }}</div>
                </div>
              </div>
            </div>
            <button class="primary-btn">开始模拟交易</button>
          </div>
          <div class="account-positions-col">
            <div class="positions-header"><span>持仓明细</span><span class="muted-small">3 只</span></div>
            <div class="positions-list">
              <div v-for="p in mockPositions" :key="p.code" class="position-item">
                <div class="pos-row pos-row-main">
                  <span class="pos-code num">{{ p.code }}</span>
                  <span class="pos-pnl num" :class="p.pnl >= 0 ? 'up' : 'down'">
                    {{ p.pnl >= 0 ? '+' : '−' }}¥{{ formatN(Math.abs(p.pnl)) }}
                  </span>
                </div>
                <div class="pos-row pos-row-meta">
                  <span class="pos-meta">{{ p.qty }} 股 @ ¥{{ p.avg }} → ¥{{ p.last }}</span>
                  <span class="pos-pnl-rate" :class="p.rate >= 0 ? 'up' : 'down'">
                    {{ p.rate >= 0 ? '+' : '' }}{{ p.rate }}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <!-- ============================================== -->
    <!-- TIER 4：外部数据接口（最重） -->
    <!-- ============================================== -->
    <section class="tier-section">
      <div class="tier-tag tier-tag-4">Tier 4 · 外部行情/基本面联动</div>
      <div class="tier-desc">Beta / 跑赢大盘 / 板块敞口 / VaR / 持仓加权 PE/PB / 大中小盘结构</div>
      <div class="panel account-panel">
        <div class="panel-hdr">
          <div class="sec-title">
            <span>🇨🇳 A 股模拟账户</span>
            <span class="position-chip num">3 持仓</span>
          </div>
          <span class="sec-link">详情 →</span>
        </div>
        <div class="account-body has-positions">
          <div class="account-money-col">
            <div class="account-hero">
              <div class="hero-label">账户总资产 (¥)</div>
              <div class="hero-val num accent">231,528.53</div>
              <div class="hero-pnl num up">
                <span class="pnl-amount">+¥33,732.00</span>
                <span class="pnl-rate">(+17.05%)</span>
              </div>
              <!-- ⭐ Tier 4 新增：vs 大盘对比 -->
              <div class="vs-bench">
                <div class="vs-row">
                  <span class="vs-label">vs 沪深 300</span>
                  <span class="vs-bar">
                    <span class="vs-bar-bg"></span>
                    <span class="vs-bar-mine" style="width: 75%"></span>
                  </span>
                  <span class="vs-val num up">+5.3%</span>
                </div>
              </div>
            </div>
            <div class="account-kpis">
              <div class="kpi-cell">
                <div class="kpi-label">Beta</div>
                <div class="kpi-val num">1.12 <span class="kpi-tag">中高弹性</span></div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">VaR (1d, 95%)</div>
                <div class="kpi-val num down">−¥4,820</div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">加权 PE</div>
                <div class="kpi-val num">18.4×</div>
              </div>
              <div class="kpi-cell">
                <div class="kpi-label">加权 PB</div>
                <div class="kpi-val num">2.1×</div>
              </div>
            </div>
            <!-- ⭐ Tier 4 新增：板块敞口 -->
            <div class="sector-section">
              <div class="sector-label">板块敞口</div>
              <div class="sector-bars">
                <div class="sector-bar">
                  <span class="sector-name">电子</span>
                  <span class="sector-bar-track"><span class="sector-bar-fill" style="width: 47%"></span></span>
                  <span class="sector-pct num">47%</span>
                </div>
                <div class="sector-bar">
                  <span class="sector-name">医药生物</span>
                  <span class="sector-bar-track"><span class="sector-bar-fill" style="width: 35%"></span></span>
                  <span class="sector-pct num">35%</span>
                </div>
                <div class="sector-bar">
                  <span class="sector-name">食品饮料</span>
                  <span class="sector-bar-track"><span class="sector-bar-fill" style="width: 18%"></span></span>
                  <span class="sector-pct num">18%</span>
                </div>
              </div>
            </div>
            <button class="primary-btn">开始模拟交易</button>
          </div>
          <div class="account-positions-col">
            <div class="positions-header"><span>持仓明细</span><span class="muted-small">3 只 · 大盘 65% / 中盘 35%</span></div>
            <div class="positions-list">
              <div v-for="p in mockPositions" :key="p.code" class="position-item">
                <div class="pos-row pos-row-main">
                  <span class="pos-code num">
                    {{ p.code }} <span class="cap-tag">{{ p.cap }}</span>
                  </span>
                  <span class="pos-pnl num" :class="p.pnl >= 0 ? 'up' : 'down'">
                    {{ p.pnl >= 0 ? '+' : '−' }}¥{{ formatN(Math.abs(p.pnl)) }}
                  </span>
                </div>
                <div class="pos-row pos-row-meta">
                  <span class="pos-meta">PE {{ p.pe }}× · PB {{ p.pb }}× · β {{ p.beta }}</span>
                  <span class="pos-pnl-rate" :class="p.rate >= 0 ? 'up' : 'down'">
                    {{ p.rate >= 0 ? '+' : '' }}{{ p.rate }}%
                  </span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>

    <div class="page-footer muted">
      挑完告诉我对应 Tier 编号（可多选），我把对应模块集成到真实 Dashboard 卡片。
    </div>
  </div>
</template>

<script setup lang="ts">
const mockPositions = [
  { code: '002428', qty: 500, avg: '25.60', last: '80.20', pnl: 27300, rate: 213.28, days: 12, cap: '中盘', pe: 22.4, pb: 3.2, beta: 1.18 },
  { code: '000776', qty: 2000, avg: '18.25', last: '21.17', pnl: 5840, rate: 16.00, days: 5, cap: '大盘', pe: 14.6, pb: 1.8, beta: 1.05 },
  { code: '603009', qty: 400, avg: '47.72', last: '49.20', pnl: -592, rate: -3.10, days: 8, cap: '中盘', pe: 28.1, pb: 2.5, beta: 1.22 },
]

const monthBars = [
  { month: '2月', value: 2.1 },
  { month: '3月', value: -1.5 },
  { month: '4月', value: 4.8 },
  { month: '5月', value: 6.2 },
  { month: '6月', value: -2.3 },
  { month: '7月', value: 3.5 },
  { month: '8月', value: 5.1 },
]

const formatN = (n: number) => n.toLocaleString('en-US', { maximumFractionDigits: 2, minimumFractionDigits: 2 })
</script>

<style lang="scss" scoped>
.tiers-page {
  padding: 24px 32px;
  background: var(--bg-base);
  min-height: 100vh;
  color: var(--fg-primary);
}

.page-hdr {
  margin-bottom: 28px;

  h2 {
    font-size: 22px;
    font-weight: 700;
    margin: 0 0 6px;
  }

  .muted {
    color: var(--fg-muted);
    font-size: 13px;
  }
}

.tier-section {
  margin-bottom: 36px;
}

.tier-tag {
  display: inline-block;
  font-size: 11px;
  font-weight: 600;
  padding: 4px 10px;
  border-radius: 4px;
  letter-spacing: 0.04em;
  margin-bottom: 6px;
  text-transform: uppercase;
}

.tier-tag-1 { background: rgba(76, 175, 80, 0.12); color: #4caf50; }
.tier-tag-2 { background: rgba(33, 150, 243, 0.14); color: #2196f3; }
.tier-tag-3 { background: rgba(212, 168, 67, 0.14); color: var(--accent); }
.tier-tag-4 { background: rgba(244, 67, 54, 0.12); color: #f44336; }

.tier-desc {
  font-size: 12.5px;
  color: var(--fg-muted);
  margin-bottom: 12px;
}

// =================================================================
// 复用 Dashboard 风格的 panel
// =================================================================
.panel {
  background: var(--bg-elevated);
  border: 1px solid var(--border-default);
  border-radius: 8px;
  overflow: hidden;
}

.panel-hdr {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 16px;
  border-bottom: 1px solid var(--border-default);
}

.sec-title {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
}

.sec-link {
  font-size: 12px;
  color: var(--accent);
  cursor: pointer;
}

.position-chip {
  font-size: 10px;
  font-weight: 500;
  letter-spacing: 0.02em;
  color: var(--fg-secondary);
  background: var(--border-default);
  padding: 2px 6px;
  border-radius: 8px;
  line-height: 1;

  &.secondary {
    background: rgba(33, 150, 243, 0.14);
    color: #2196f3;
  }
}

.account-body {
  padding: 16px 18px 14px;

  &.has-positions {
    display: grid;
    grid-template-columns: minmax(0, 1fr) minmax(0, 1.1fr);
    gap: 18px;
    align-items: start;
  }
}

.account-money-col, .account-positions-col { min-width: 0; }

.account-positions-col {
  border-left: 1px solid var(--border-default);
  padding-left: 18px;
}

.account-hero {
  margin-bottom: 18px;
  padding-bottom: 16px;
  border-bottom: 1px solid var(--border-default);

  &.hero-with-chart {
    display: flex;
    justify-content: space-between;
    align-items: flex-end;
    gap: 16px;
  }
}

.hero-info { flex: 1; min-width: 0; }

.hero-label {
  font-size: 11px;
  color: var(--fg-muted);
  margin-bottom: 4px;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.hero-val {
  font-size: 36px;
  font-weight: 700;
  line-height: 1.05;
  letter-spacing: -0.025em;
  display: block;

  &.accent { color: var(--accent); }
}

.hero-pnl {
  margin-top: 8px;
  font-size: 16px;
  font-weight: 600;
  display: flex;
  align-items: baseline;
  gap: 8px;

  &.up { color: var(--up); }
  &.down { color: var(--down); }
}

.pnl-amount { font-weight: 700; }
.pnl-rate { font-size: 13px; font-weight: 500; opacity: 0.85; }

// Tier 1 派生 chip 行
.derive-row {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 14px;
}

.derive-chip {
  font-size: 11.5px;
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 9px;
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border-default);
  border-radius: 4px;

  .dim { color: var(--fg-muted); }
  .strong { font-weight: 600; }
  .up { color: var(--up); }
  .down { color: var(--down); }
}

.account-kpis {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px 24px;
  margin-bottom: 18px;
}

.kpi-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
  min-width: 0;
}

.kpi-label {
  font-size: 11px;
  color: var(--fg-muted);
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.kpi-val {
  font-size: 17px;
  font-weight: 600;
  color: var(--fg-primary);
  letter-spacing: -0.01em;
  display: flex;
  align-items: baseline;
  gap: 6px;
  flex-wrap: wrap;

  &.up { color: var(--up); }
  &.down { color: var(--down); }
  &.strong { font-weight: 700; }

  .kpi-tag {
    font-size: 10px;
    font-weight: 500;
    color: var(--fg-muted);
    background: var(--border-default);
    padding: 2px 5px;
    border-radius: 3px;
  }
}

.account-progress { margin-bottom: 14px; }

.progress-label {
  display: flex;
  justify-content: space-between;
  font-size: 11px;
  color: var(--fg-muted);
  margin-bottom: 4px;
}

.progress-bar {
  height: 4px;
  background: var(--border-default);
  border-radius: 4px;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: var(--accent);
  border-radius: 4px;
}

.primary-btn {
  width: 100%;
  margin-top: 4px;
  padding: 10px;
  background: var(--accent);
  color: #000;
  border: none;
  border-radius: 4px;
  font-weight: 600;
  font-size: 13px;
  cursor: pointer;
  letter-spacing: 0.02em;

  &:hover { opacity: 0.9; }
}

// =================================================================
// 持仓 list
// =================================================================
.positions-header {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  font-size: 11px;
  color: var(--fg-muted);
  margin-bottom: 10px;
  letter-spacing: 0.04em;
  text-transform: uppercase;

  .muted-small {
    font-size: 11px;
    text-transform: none;
    letter-spacing: 0;
  }
}

.position-item {
  padding: 10px 0;
  border-bottom: 1px solid var(--border-default);

  &:first-child { padding-top: 0; }
  &:last-child { border-bottom: none; padding-bottom: 0; }
}

.pos-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
}

.pos-row-main { margin-bottom: 4px; }

.pos-code {
  font-size: 14px;
  font-weight: 600;
  color: var(--fg-primary);
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.cap-tag {
  font-size: 9.5px;
  font-weight: 500;
  color: var(--fg-muted);
  background: var(--border-default);
  padding: 1px 5px;
  border-radius: 3px;
  text-transform: none;
  letter-spacing: 0;
}

.pos-pnl {
  font-size: 14px;
  font-weight: 600;
  &.up { color: var(--up); }
  &.down { color: var(--down); }
}

.pos-row-meta { font-size: 11.5px; color: var(--fg-muted); }
.pos-meta .dim { color: var(--fg-muted); opacity: 0.8; }
.pos-arrow { margin: 0 3px; opacity: 0.6; }
.pos-pnl-rate {
  font-weight: 500;
  &.up { color: var(--up); opacity: 0.85; }
  &.down { color: var(--down); opacity: 0.85; }
}

// =================================================================
// Tier 2 — 最近交易行
// =================================================================
.recent-trade {
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11.5px;
  padding: 8px 12px;
  background: rgba(255, 255, 255, 0.03);
  border-radius: 4px;
  margin-bottom: 14px;

  .rt-icon { opacity: 0.6; }
  .rt-text { flex: 1; }
  .dim { color: var(--fg-muted); }
  .up { color: var(--up); font-weight: 600; }
}

// =================================================================
// Tier 3 — Sparkline / 月度柱图
// =================================================================
.hero-spark {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 6px;
  flex-shrink: 0;
}

.spark-svg {
  width: 130px;
  height: 50px;
  display: block;
}

.spark-meta {
  font-size: 11px;
  display: flex;
  gap: 6px;
  align-items: baseline;

  .dim { color: var(--fg-muted); }
  .up { color: var(--up); font-weight: 600; }
}

.month-bars {
  margin-bottom: 14px;
}

.month-bars-label {
  font-size: 11px;
  color: var(--fg-muted);
  margin-bottom: 8px;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.month-bars-row {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
}

.month-bar-cell {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
}

.month-bar-track {
  position: relative;
  width: 100%;
  height: 50px;
}

.month-bar-axis {
  position: absolute;
  left: 0;
  right: 0;
  top: 50%;
  height: 1px;
  background: var(--border-default);
}

.month-bar-fill {
  position: absolute;
  left: 15%;
  width: 70%;
  border-radius: 2px;

  &.up { background: var(--up); }
  &.down { background: var(--down); }
}

.month-bar-label {
  font-size: 10px;
  color: var(--fg-muted);
}

// =================================================================
// Tier 4 — vs 大盘 / 板块敞口
// =================================================================
.vs-bench { margin-top: 14px; }

.vs-row {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 11.5px;
}

.vs-label {
  color: var(--fg-muted);
  font-size: 11px;
  flex-shrink: 0;
  text-transform: uppercase;
  letter-spacing: 0.02em;
}

.vs-bar {
  flex: 1;
  position: relative;
  height: 6px;
  border-radius: 3px;
  overflow: hidden;
}

.vs-bar-bg {
  position: absolute;
  inset: 0;
  background: var(--border-default);
}

.vs-bar-mine {
  position: absolute;
  left: 0;
  top: 0;
  bottom: 0;
  background: var(--up);
  border-radius: 3px;
}

.vs-val { font-weight: 600; }

.sector-section { margin-bottom: 14px; }

.sector-label {
  font-size: 11px;
  color: var(--fg-muted);
  margin-bottom: 8px;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}

.sector-bars { display: flex; flex-direction: column; gap: 6px; }

.sector-bar {
  display: grid;
  grid-template-columns: 70px 1fr 36px;
  gap: 8px;
  align-items: center;
  font-size: 11.5px;
}

.sector-name { color: var(--fg-secondary); }

.sector-bar-track {
  position: relative;
  height: 6px;
  background: var(--border-default);
  border-radius: 3px;
  overflow: hidden;
}

.sector-bar-fill {
  position: absolute;
  inset: 0;
  background: var(--accent);
  border-radius: 3px;
}

.sector-pct {
  text-align: right;
  font-weight: 600;
  color: var(--fg-primary);
}

.page-footer {
  margin-top: 32px;
  padding: 16px;
  text-align: center;
  font-size: 12px;
  color: var(--fg-muted);
  border-top: 1px solid var(--border-default);
}

.muted, .muted-small { color: var(--fg-muted); }

// 数字字体
.num {
  font-variant-numeric: tabular-nums;
  font-feature-settings: 'tnum';
}
</style>
