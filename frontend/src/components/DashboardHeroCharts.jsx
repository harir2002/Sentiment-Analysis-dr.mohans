import {
  BarChart,
  Bar,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import {
  computeSentimentByDay,
  computeSentimentTrend,
  getTrendInsight,
} from '../utils/dashboardAnalytics';
import styles from './DashboardCharts.module.css';

const SENTIMENT_COLORS = {
  positive: '#22c55e',
  neutral: '#f59e0b',
  negative: '#ef4444',
};

const CHART_THEME = {
  grid: 'rgba(255, 255, 255, 0.06)',
  axis: 'rgba(255, 255, 255, 0.45)',
  tooltipBg: '#141414',
  tooltipBorder: 'rgba(255, 255, 255, 0.1)',
};

function DarkTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className={styles['dark-tooltip']}>
      <p className={styles['dark-tooltip-label']}>{label}</p>
      {payload.map((entry) => (
        <p key={entry.name} className={styles['dark-tooltip-row']} style={{ color: entry.color }}>
          {entry.name}: <strong>{entry.value}</strong>
        </p>
      ))}
    </div>
  );
}

function ChartShell({ title, subtitle, children, footer }) {
  return (
    <div className={styles['hero-chart-card']}>
      <div className={styles['hero-chart-header']}>
        <h3 className={styles['hero-chart-title']}>{title}</h3>
        {subtitle && <p className={styles['hero-chart-subtitle']}>{subtitle}</p>}
      </div>
      <div className={styles['hero-chart-body']}>{children}</div>
      {footer && <p className={styles['hero-chart-footer']}>{footer}</p>}
    </div>
  );
}

function EmptyChart({ title, message }) {
  return (
    <ChartShell title={title}>
      <div className={styles['hero-chart-empty']}>
        <span className={styles['hero-chart-empty-icon']} aria-hidden="true">📊</span>
        <p>{message}</p>
      </div>
    </ChartShell>
  );
}

export function SentimentByDayChart({ records }) {
  const data = computeSentimentByDay(records);

  if (data.length === 0) {
    return (
      <EmptyChart
        title="Sentiment by Day"
        message="No analysed recordings yet. Sentiment breakdown will appear once calls are processed."
      />
    );
  }

  return (
    <ChartShell title="Sentiment by Day" subtitle="Stacked daily sentiment distribution">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 12, left: -8, bottom: 4 }} barCategoryGap="28%">
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fill: CHART_THEME.axis, fontSize: 12 }}
            axisLine={{ stroke: CHART_THEME.grid }}
            tickLine={false}
            interval={0}
          />
          <YAxis
            allowDecimals={false}
            tick={{ fill: CHART_THEME.axis, fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <Tooltip content={<DarkTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
          <Legend
            verticalAlign="bottom"
            height={36}
            iconType="circle"
            iconSize={8}
            wrapperStyle={{ fontSize: 12, color: CHART_THEME.axis, paddingTop: 12 }}
          />
          <Bar
            dataKey="positive"
            name="Positive"
            stackId="sentiment"
            fill={SENTIMENT_COLORS.positive}
            radius={[0, 0, 0, 0]}
          />
          <Bar
            dataKey="neutral"
            name="Neutral"
            stackId="sentiment"
            fill={SENTIMENT_COLORS.neutral}
          />
          <Bar
            dataKey="negative"
            name="Negative"
            stackId="sentiment"
            fill={SENTIMENT_COLORS.negative}
            radius={[4, 4, 0, 0]}
          />
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  );
}

export function SentimentScoreTrendChart({ records }) {
  const data = computeSentimentTrend(records);
  const insight = getTrendInsight(data);

  if (data.length === 0) {
    return (
      <EmptyChart
        title="Sentiment Trend"
        message="Trend data will appear once recordings with sentiment results are available."
      />
    );
  }

  return (
    <ChartShell title="Sentiment Trend" subtitle="Average sentiment score over time" footer={insight}>
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, left: -8, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} vertical={false} />
          <XAxis
            dataKey="name"
            tick={{ fill: CHART_THEME.axis, fontSize: 12 }}
            axisLine={{ stroke: CHART_THEME.grid }}
            tickLine={false}
            interval={0}
          />
          <YAxis
            domain={[0, 100]}
            tick={{ fill: CHART_THEME.axis, fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            tickFormatter={(v) => `${v}%`}
          />
          <Tooltip
            content={({ active, payload, label }) => {
              if (!active || !payload?.length) return null;
              return (
                <div className={styles['dark-tooltip']}>
                  <p className={styles['dark-tooltip-label']}>{label}</p>
                  <p className={styles['dark-tooltip-row']} style={{ color: SENTIMENT_COLORS.positive }}>
                    Avg score: <strong>{payload[0].value}%</strong>
                  </p>
                  {payload[0].payload?.count != null && (
                    <p className={styles['dark-tooltip-meta']}>
                      {payload[0].payload.count} recording{payload[0].payload.count !== 1 ? 's' : ''}
                    </p>
                  )}
                </div>
              );
            }}
          />
          <Line
            type="monotone"
            dataKey="score"
            name="Avg Sentiment"
            stroke={SENTIMENT_COLORS.positive}
            strokeWidth={2.5}
            dot={{ fill: SENTIMENT_COLORS.positive, strokeWidth: 0, r: 4 }}
            activeDot={{ r: 6, fill: SENTIMENT_COLORS.positive }}
          />
        </LineChart>
      </ResponsiveContainer>
    </ChartShell>
  );
}

export default function DashboardHeroCharts({ records }) {
  return (
    <div className={styles['hero-charts-grid']}>
      <SentimentByDayChart records={records} />
      <SentimentScoreTrendChart records={records} />
    </div>
  );
}
