import ComparisonTable from './ComparisonTable';
import WinnerCard from './WinnerCard';
import CanonicalResultBanner from './CanonicalResultBanner';
import SolutionTab from './SolutionTab';
import { Card, CardHeader, ResultField, SentimentBadge } from './ui';
import { StatusBadge } from './SolutionTab';
import { orderSolutionResults } from '../constants/solutions';

function SolutionOverviewCard({ result, isWinner }) {
  const completed = result.status === 'completed' && result.analysis;
  const confidencePct = completed
    ? Math.round((result.analysis.confidence || 0) * 100)
    : null;

  return (
    <div className={`solution-overview-card ${isWinner ? 'solution-overview-winner' : ''}`}>
      <div className="solution-overview-header">
        <h4 className="solution-overview-title">{result.label}</h4>
        {isWinner && <span className="solution-winner-badge">Top score</span>}
      </div>

      <div className="solution-overview-fields">
        <ResultField label="Status" value={<StatusBadge status={result.status} />} />
        <ResultField
          label="Sentiment"
          value={
            completed ? (
              <SentimentBadge sentiment={result.analysis.sentiment} />
            ) : (
              <span className="result-empty-value">—</span>
            )
          }
        />
        <ResultField
          label="Confidence"
          value={confidencePct != null ? `${confidencePct}%` : '—'}
        />
        <ResultField
          label="Score"
          value={result.overall_score != null ? result.overall_score.toFixed(2) : '—'}
        />
      </div>

      <p className="solution-overview-summary">
        {completed
          ? result.analysis.summary || 'No summary available.'
          : result.error || result.status_message || 'Awaiting or unavailable.'}
      </p>

      {completed && result.analysis.recommended_action && (
        <div className="solution-overview-action">
          <span className="ui-result-field-label">Next Step</span>
          <p className="solution-overview-action-text">{result.analysis.recommended_action}</p>
        </div>
      )}
    </div>
  );
}
export default function SolutionComparison({ results, ranking, audioFilename, jobMeta }) {
  const ordered = orderSolutionResults(results);
  const winnerId = ranking?.winner?.solution_id;

  return (
    <div className="comparison-layout">
      <div className="results-banner">
        <div className="results-banner-text">
          <strong>4-solution comparison ready</strong>
          <span>Side-by-side results across all STT + LLM pipelines.</span>
        </div>
        <div className="results-banner-meta">
          {audioFilename && <span className="results-ref">Audio: {audioFilename}</span>}
        </div>
      </div>

      <CanonicalResultBanner results={results} ranking={ranking} jobMeta={jobMeta} />

      <WinnerCard ranking={ranking} />

      <section className="solution-grid-section">
        <h3 className="section-heading">Pipeline overview</h3>
        <div className="solution-grid">
          {ordered.map((result) => (
            <SolutionOverviewCard
              key={result.solution_id}
              result={result}
              isWinner={result.solution_id === winnerId}
            />
          ))}
        </div>
      </section>

      <ComparisonTable results={ordered} winnerId={winnerId} />

      <Card className="solution-details-card">
        <CardHeader
          title="Per-solution observations"
          subtitle="Full transcript, sentiment, issues, and notes for each pipeline"
        />
        <div className="solution-details-stack">
          {ordered.map((result) => (
            <div key={result.solution_id} className="solution-detail-block">
              <h4 className="solution-detail-title">
                {result.label}
                {result.solution_id === winnerId && <span className="winner-star"> ★</span>}
              </h4>
              <SolutionTab result={result} />
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
