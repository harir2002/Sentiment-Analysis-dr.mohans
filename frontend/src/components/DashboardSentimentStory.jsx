import {
  BarChart,
  Bar,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import {
  computeSentimentMix,
  computeSentimentByDay,
  computeSentimentTrend,
  computeWeeklyVolume,
  getTrendInsight,
} from '../utils/dashboardAnalytics';
import styles from './DashboardCharts.module.css';
import sectionStyles from './SentimentDashboard.module.css';

const SENTIMENT_COLORS = {
  positive: '#22c55e',
  neutral: '#f59e0b',
  negative: '#ef4444',
  invalid: '#94a3b8',
};

const CHART_THEME = {
  grid: 'rgba(255, 255, 255, 0.06)',
  axis: 'rgba(255, 255, 255, 0.45)',
};

function DarkTooltip({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className={styles['dark-tooltip']}>
      <p className={styles['dark-tooltip-label']}>{label}</p>
      {payload.map((entry) => (
        <p key={entry.name} className={styles['dark-tooltip-row']} style={{ color: entry.color || entry.fill }}>
          {entry.name}: <strong>{entry.value}</strong>
        </p>
      ))}
    </div>
  );
}

export { DarkTooltip };

function ChartShell({ title, question, insight, children, className = '' }) {
  return (
    <div className={`${styles['hero-chart-card']} hero-chart-card ${className}`}>
      <div className={styles['hero-chart-header']}>
        <h4 className={styles['hero-chart-title']}>{title}</h4>
        {question && <p className={styles['hero-chart-question']}>{question}</p>}
      </div>
      <div className={styles['hero-chart-body']}>{children}</div>
      {insight && <p className={styles['hero-chart-footer']}>{insight}</p>}
    </div>
  );
}

function EmptyChart({ title, question, message }) {
  return (
    <ChartShell title={title} question={question}>
      <div className={styles['hero-chart-empty']}>
        <span className={styles['hero-chart-empty-icon']} aria-hidden="true">📊</span>
        <p>{message}</p>
      </div>
    </ChartShell>
  );
}

function SentimentMixChart({ records }) {
  const data = computeSentimentMix(records);
  const total = data.reduce((sum, d) => sum + d.value, 0);

  if (total === 0) {
    return (
      <EmptyChart
        title="Sentiment Mix"
        question="What is the overall customer sentiment across all calls?"
        message="Sentiment distribution appears once calls are classified."
      />
    );
  }

  const dominant = [...data].sort((a, b) => b.value - a.value)[0];
  const insight = `${dominant.name} calls represent ${Math.round((dominant.value / total) * 100)}% of the portfolio.`;

  return (
    <ChartShell
      title="Sentiment Mix"
      question="What is the overall customer sentiment across all calls?"
      insight={insight}
    >
      <ResponsiveContainer width="100%" height="100%">
        <PieChart>
          <Pie
            data={data}
            dataKey="value"
            nameKey="name"
            cx="50%"
            cy="50%"
            innerRadius={58}
            outerRadius={88}
            paddingAngle={2}
          >
            {data.map((entry) => (
              <Cell key={entry.name} fill={entry.color} />
            ))}
          </Pie>
          <Tooltip content={<DarkTooltip />} />
          <Legend
            verticalAlign="bottom"
            iconType="circle"
            iconSize={8}
            wrapperStyle={{ fontSize: 12, color: CHART_THEME.axis, paddingTop: 8 }}
          />
        </PieChart>
      </ResponsiveContainer>
    </ChartShell>
  );
}

function SentimentByDayChart({ records }) {
  const data = computeSentimentByDay(records);

  if (data.length === 0) {
    return (
      <EmptyChart
        title="Daily Sentiment Volume"
        question="How is sentiment distributed day by day?"
        message="Daily breakdown appears as recordings are analysed."
      />
    );
  }

  return (
    <ChartShell
      title="Daily Sentiment Volume"
      question="How is sentiment distributed day by day?"
      insight="Stacked bars show whether negative volume is concentrated on specific days."
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 12, left: -8, bottom: 4 }} barCategoryGap="28%">
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} vertical={false} />
          <XAxis dataKey="name" tick={{ fill: CHART_THEME.axis, fontSize: 11 }} axisLine={{ stroke: CHART_THEME.grid }} tickLine={false} interval={0} />
          <YAxis allowDecimals={false} tick={{ fill: CHART_THEME.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip content={<DarkTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
          <Legend verticalAlign="bottom" height={36} iconType="circle" iconSize={8} wrapperStyle={{ fontSize: 11, color: CHART_THEME.axis }} />
          <Bar dataKey="positive" name="Positive" stackId="s" fill={SENTIMENT_COLORS.positive} />
          <Bar dataKey="neutral" name="Neutral" stackId="s" fill={SENTIMENT_COLORS.neutral} />
          <Bar dataKey="negative" name="Negative" stackId="s" fill={SENTIMENT_COLORS.negative} radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  );
}

function SentimentTrendChart({ records }) {
  const data = computeSentimentTrend(records);
  const insight = getTrendInsight(data);

  if (data.length === 0) {
    return (
      <EmptyChart
        title="Sentiment Trend"
        question="Are customer interactions improving or worsening?"
        message="Trend line builds as more classified calls are added."
      />
    );
  }

  return (
    <ChartShell
      title="Sentiment Trend"
      question="Are customer interactions improving or worsening?"
      insight={insight || undefined}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 8, right: 12, left: -8, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} vertical={false} />
          <XAxis dataKey="name" tick={{ fill: CHART_THEME.axis, fontSize: 11 }} axisLine={{ stroke: CHART_THEME.grid }} tickLine={false} />
          <YAxis domain={[0, 100]} tick={{ fill: CHART_THEME.axis, fontSize: 11 }} axisLine={false} tickLine={false} tickFormatter={(v) => `${v}%`} />
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
                      {payload[0].payload.count} call{payload[0].payload.count !== 1 ? 's' : ''}
                    </p>
                  )}
                </div>
              );
            }}
          />
          <Line type="monotone" dataKey="score" name="Avg Sentiment" stroke={SENTIMENT_COLORS.positive} strokeWidth={2.5} dot={{ fill: SENTIMENT_COLORS.positive, strokeWidth: 0, r: 4 }} />
        </LineChart>
      </ResponsiveContainer>
    </ChartShell>
  );
}

function WeeklyVolumeChart({ records }) {
  const data = computeWeeklyVolume(records);

  if (data.length === 0) {
    return (
      <EmptyChart
        title="Weekly Call Volume"
        question="How many calls are we analysing each week?"
        message="Weekly volume appears once recordings span multiple days."
      />
    );
  }

  const peak = [...data].sort((a, b) => b.total - a.total)[0];

  return (
    <ChartShell
      title="Weekly Call Volume"
      question="How many calls are we analysing each week?"
      insight={peak ? `Peak week: ${peak.name} (${peak.total} calls).` : undefined}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 12, left: -8, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} vertical={false} />
          <XAxis dataKey="name" tick={{ fill: CHART_THEME.axis, fontSize: 10 }} axisLine={{ stroke: CHART_THEME.grid }} tickLine={false} />
          <YAxis allowDecimals={false} tick={{ fill: CHART_THEME.axis, fontSize: 11 }} axisLine={false} tickLine={false} />
          <Tooltip content={<DarkTooltip />} />
          <Bar dataKey="total" name="Total calls" fill="#6366f1" radius={[4, 4, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </ChartShell>
  );
}

export default function DashboardSentimentStory({ records }) {
  return (
    <section className={sectionStyles['dashboard-story-section']}>
      <div className={sectionStyles['section-intro']}>
        <h3 className={sectionStyles['section-heading']}>Sentiment Story</h3>
        <p className={sectionStyles['section-subheading']}>
          How customers feel across your call portfolio — one analysed call per recording.
        </p>
      </div>
      <div className={styles['story-charts-grid']}>
        <SentimentMixChart records={records} />
        <SentimentTrendChart records={records} />
        <SentimentByDayChart records={records} />
        <WeeklyVolumeChart records={records} />
      </div>
    </section>
  );
}
