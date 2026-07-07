import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts';
import { SOLUTION_ORDER } from '../constants/solutions';
import { getCanonicalResult, normalizeSentiment } from '../utils/canonicalResult';
import chartStyles from './DashboardCharts.module.css';
import styles from './SentimentDashboard.module.css';
import tableStyles from './DashboardSolutionComparison.module.css';
import { DarkTooltip } from './DashboardSentimentStory';

const SHORT_LABELS = {
  sarvam_stt_sarvam_llm: 'Sarvam + Sarvam',
  sarvam_stt_groq_gemma: 'Sarvam + Gemma',
  groq_whisper_sarvam_llm: 'Whisper + Sarvam',
  groq_whisper_groq_gemma: 'Whisper + Gemma',
};

const CHART_THEME = {
  grid: 'rgba(255, 255, 255, 0.06)',
  axis: 'rgba(255, 255, 255, 0.45)',
};

/**
 * Per-solution stats across all recordings.
 * Comparison layer only — never feeds executive KPI totals.
 */
function buildSolutionStats(records) {
  const stats = Object.fromEntries(
    SOLUTION_ORDER.map(({ id, label }) => [
      id,
      {
        id,
        label,
        shortLabel: SHORT_LABELS[id] || label,
        completedCount: 0,
        failedCount: 0,
        wins: 0,
        scoreSum: 0,
        confidenceSum: 0,
        runtimeSum: 0,
        runtimeCount: 0,
        positive: 0,
        neutral: 0,
        negative: 0,
      },
    ])
  );

  records.forEach((record) => {
    const canonical = getCanonicalResult(record);
    if (canonical && stats[canonical.solution_id]) {
      stats[canonical.solution_id].wins++;
    }

    (record.results || []).forEach((result) => {
      const entry = stats[result.solution_id];
      if (!entry) return;

      if (result.status === 'completed' && result.analysis) {
        entry.completedCount++;
        entry.scoreSum += result.overall_score || 0;
        entry.confidenceSum += result.analysis.confidence || 0;

        const sentiment = normalizeSentiment(result.analysis.sentiment);
        if (sentiment) entry[sentiment]++;

        if (result.total_runtime_seconds > 0) {
          entry.runtimeSum += result.total_runtime_seconds;
          entry.runtimeCount++;
        }
      } else if (result.status === 'failed' || result.status === 'rate_limited') {
        entry.failedCount++;
      }
    });
  });

  return SOLUTION_ORDER.map(({ id }) => {
    const entry = stats[id];
    const n = entry.completedCount;
    return {
      ...entry,
      avgScore: n > 0 ? entry.scoreSum / n : null,
      avgConfidence: n > 0 ? entry.confidenceSum / n : null,
      avgRuntime: entry.runtimeCount > 0 ? entry.runtimeSum / entry.runtimeCount : null,
    };
  });
}

function ChartCard({ title, question, children }) {
  return (
    <div className={`${chartStyles['hero-chart-card']} hero-chart-card`}>
      <div className={chartStyles['hero-chart-header']}>
        <h4 className={chartStyles['hero-chart-title']}>{title}</h4>
        <p className={chartStyles['hero-chart-question']}>{question}</p>
      </div>
      <div className={chartStyles['hero-chart-body']} style={{ minHeight: 260 }}>
        {children}
      </div>
    </div>
  );
}

export default function DashboardSolutionStory({ records }) {
  const stats = buildSolutionStats(records);
  const hasData = stats.some((s) => s.completedCount > 0);

  const topWinner = [...stats].sort((a, b) => b.wins - a.wins)[0];
  const insight = topWinner?.wins > 0
    ? `${topWinner.shortLabel} is the canonical winner most often (${topWinner.wins} recording${topWinner.wins !== 1 ? 's' : ''}).`
    : null;

  const scoreConfidenceData = stats.map((s) => ({
    name: s.shortLabel,
    'Avg Score': s.avgScore != null ? Number((s.avgScore * 100).toFixed(1)) : 0,
    'Avg Confidence': s.avgConfidence != null ? Number((s.avgConfidence * 100).toFixed(1)) : 0,
  }));

  const winsData = stats.map((s) => ({
    name: s.shortLabel,
    Wins: s.wins,
  }));

  return (
    <section className={styles['dashboard-story-section']} aria-label="Solution performance">
      <div className={styles['section-intro']}>
        <h3 className={styles['section-heading']}>AI Solution Performance</h3>
        <p className={styles['section-subheading']}>
          How each of the four STT + LLM pipelines performs — comparison data only, not executive KPI totals.
        </p>
        {insight && <p className={styles['section-insight']}>{insight}</p>}
      </div>

      {!hasData ? (
        <div className={chartStyles['hero-chart-empty']}>
          <p>Solution comparison appears once recordings finish processing.</p>
        </div>
      ) : (
        <>
          <div className={chartStyles['story-charts-grid']}>
            <ChartCard
              title="Quality by Solution"
              question="Which AI pipeline delivers the highest scores and confidence?"
            >
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={scoreConfidenceData} margin={{ top: 4, right: 8, left: -12, bottom: 4 }}>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} vertical={false} />
                  <XAxis dataKey="name" tick={{ fill: CHART_THEME.axis, fontSize: 10 }} interval={0} />
                  <YAxis domain={[0, 100]} tick={{ fill: CHART_THEME.axis, fontSize: 11 }} />
                  <Tooltip content={<DarkTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                  <Legend wrapperStyle={{ fontSize: 11, color: CHART_THEME.axis }} />
                  <Bar dataKey="Avg Score" fill="#8b5cf6" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="Avg Confidence" fill="#3b82f6" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </ChartCard>

            <ChartCard
              title="Canonical Wins"
              question="Which pipeline is selected as the final winner most often?"
            >
              <div className={chartStyles['canonical-wins-layout']}>
                <div className={chartStyles['canonical-wins-chart']}>
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={winsData} layout="vertical" margin={{ top: 4, right: 16, left: 4, bottom: 4 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke={CHART_THEME.grid} horizontal={false} />
                      <XAxis type="number" allowDecimals={false} tick={{ fill: CHART_THEME.axis, fontSize: 11 }} />
                      <YAxis dataKey="name" type="category" width={118} tick={{ fill: CHART_THEME.axis, fontSize: 10 }} />
                      <Tooltip content={<DarkTooltip />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                      <Bar dataKey="Wins" fill="#e7000b" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                </div>

                <div className={chartStyles['canonical-explainer']}>
                  <h5 className={chartStyles['canonical-explainer-title']}>How this is calculated</h5>
                  <div className={chartStyles['canonical-explainer-body']}>
                    <p>Each call is evaluated across the compared AI pipelines.</p>
                    <p>The canonical winner is the solution selected as the final best result for that call.</p>
                    <p>This chart reflects total wins across all processed calls.</p>
                    <p>Quality score, confidence, and the final comparison selection logic are used to determine the winner.</p>
                  </div>
                </div>
              </div>
            </ChartCard>
          </div>

          <div className={`${tableStyles['stats-table-wrap']} dash-stats-table-wrap`}>
            <table className={`${tableStyles['stats-table']} dash-stats-table`}>
              <thead>
                <tr>
                  <th>Solution</th>
                  <th>Completed</th>
                  <th>Failed</th>
                  <th>Canonical Wins</th>
                  <th>Avg Score</th>
                  <th>Avg Conf.</th>
                  <th>Avg Runtime</th>
                </tr>
              </thead>
              <tbody>
                {stats.map((s) => (
                  <tr key={s.id}>
                    <td className={tableStyles['solution-name']} title={s.label}>{s.shortLabel}</td>
                    <td>{s.completedCount}</td>
                    <td>{s.failedCount}</td>
                    <td>{s.wins}</td>
                    <td>{s.avgScore != null ? s.avgScore.toFixed(2) : '—'}</td>
                    <td>{s.avgConfidence != null ? `${Math.round(s.avgConfidence * 100)}%` : '—'}</td>
                    <td>{s.avgRuntime != null ? `${s.avgRuntime.toFixed(1)}s` : '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </section>
  );
}
