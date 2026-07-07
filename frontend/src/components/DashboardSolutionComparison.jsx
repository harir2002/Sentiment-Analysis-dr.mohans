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
import { Card, CardHeader } from './ui';
import { SOLUTION_ORDER } from '../constants/solutions';
import { getCanonicalResult, normalizeSentiment } from '../utils/canonicalResult';
import chartStyles from './DashboardCharts.module.css';
import styles from './DashboardSolutionComparison.module.css';

// Short labels so 4 solutions fit on chart axes
const SHORT_LABELS = {
  sarvam_stt_sarvam_llm: 'Sarvam + Sarvam',
  sarvam_stt_groq_gemma: 'Sarvam + Gemma',
  groq_whisper_sarvam_llm: 'Whisper + Sarvam',
  groq_whisper_groq_gemma: 'Whisper + Gemma',
};

/**
 * Aggregate per-solution statistics across all recordings.
 * This is comparison-layer data only: it deliberately spans all 4 raw
 * outputs per recording and must never feed the top KPI cards.
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

export default function DashboardSolutionComparison({ records }) {
  const stats = buildSolutionStats(records);
  const hasData = stats.some((s) => s.completedCount > 0);

  if (!hasData) {
    return (
      <Card>
        <CardHeader
          title="Solution Comparison"
          subtitle="Per-solution performance across all recordings"
        />
        <p className={chartStyles['empty-chart']}>
          No completed analyses yet — comparison data appears once recordings finish processing.
        </p>
      </Card>
    );
  }

  const scoreConfidenceData = stats.map((s) => ({
    name: s.shortLabel,
    'Avg Score': s.avgScore != null ? Number((s.avgScore * 100).toFixed(1)) : 0,
    'Avg Confidence': s.avgConfidence != null ? Number((s.avgConfidence * 100).toFixed(1)) : 0,
  }));

  const sentimentData = stats.map((s) => ({
    name: s.shortLabel,
    Positive: s.positive,
    Neutral: s.neutral,
    Negative: s.negative,
  }));

  const winsData = stats.map((s) => ({
    name: s.shortLabel,
    'Best-Performing Count': s.wins,
  }));

  return (
    <div className={styles['solution-comparison']}>
      <div className={chartStyles['chart-grid']}>
        <Card>
          <CardHeader
            title="Average Score & Confidence by Solution"
            subtitle="Across all completed analyses (%)"
          />
          <div style={{ width: '100%', height: '300px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={scoreConfidenceData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} />
                <YAxis domain={[0, 100]} />
                <Tooltip formatter={(value) => `${value}%`} />
                <Legend />
                <Bar dataKey="Avg Score" fill="#8b5cf6" />
                <Bar dataKey="Avg Confidence" fill="#3b82f6" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Sentiment Distribution by Solution"
            subtitle="How each pipeline classified the recordings"
          />
          <div style={{ width: '100%', height: '300px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sentimentData}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" tick={{ fontSize: 11 }} interval={0} />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Legend />
                <Bar dataKey="Positive" stackId="sentiment" fill="#10b981" />
                <Bar dataKey="Neutral" stackId="sentiment" fill="#6b7280" />
                <Bar dataKey="Negative" stackId="sentiment" fill="#ef4444" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Best-Performing Solution Frequency"
            subtitle="How often each solution was the canonical winner"
          />
          <div style={{ width: '100%', height: '300px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={winsData} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis type="number" allowDecimals={false} />
                <YAxis dataKey="name" type="category" width={130} tick={{ fontSize: 11 }} />
                <Tooltip />
                <Bar dataKey="Best-Performing Count" fill="#f59e0b" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </Card>

        <Card>
          <CardHeader
            title="Solution Summary"
            subtitle="Completion, quality, and runtime per pipeline"
          />
          <div className={styles['stats-table-wrap']}>
            <table className={styles['stats-table']}>
              <thead>
                <tr>
                  <th>Solution</th>
                  <th>Completed</th>
                  <th>Failed</th>
                  <th>Wins</th>
                  <th>Avg Score</th>
                  <th>Avg Conf.</th>
                  <th>Avg Runtime</th>
                </tr>
              </thead>
              <tbody>
                {stats.map((s) => (
                  <tr key={s.id}>
                    <td className={styles['solution-name']} title={s.label}>
                      {s.shortLabel}
                    </td>
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
        </Card>
      </div>
    </div>
  );
}
