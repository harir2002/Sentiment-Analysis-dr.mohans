import TranscriptPanel from './TranscriptPanel';
import { Card, CardHeader, Alert, SentimentBadge } from './ui';
import { getPrimaryResult } from '../constants/solutions';

function nextStepsFromAnalysis(analysis) {
  if (!analysis) return [];
  const steps = [];
  if (analysis.recommended_action?.trim()) {
    steps.push(analysis.recommended_action.trim());
  }
  (analysis.action_items || []).forEach((item) => {
    const text = String(item || '').trim();
    if (text && !steps.includes(text)) steps.push(text);
  });
  return steps;
}

export default function SolutionComparison({ results, ranking, audioFilename, jobMeta }) {
  const result = getPrimaryResult(results, ranking);
  const completed = result?.status === 'completed' && result?.analysis;
  const pending = result && ['queued', 'running', 'timed_out'].includes(result.status);
  const failed = result && (result.status === 'failed' || result.status === 'rate_limited');

  if (!result) {
    return (
      <Alert variant="info" title="No results yet">
        Analysis has not produced output for this recording.
      </Alert>
    );
  }

  if (pending) {
    return (
      <Alert variant="info" title="Analysis in progress">
        Your call is being transcribed and reviewed. Results will appear here when ready.
      </Alert>
    );
  }

  if (failed) {
    return (
      <Alert variant="danger" title="Analysis could not be completed">
        {result.error || 'Please try again with a clearer recording.'}
      </Alert>
    );
  }

  if (!completed) return null;

  const { analysis, transcript } = result;
  const nextSteps = nextStepsFromAnalysis(analysis);

  return (
    <div className="comparison-layout simple-results-layout">
      <div className="results-banner">
        <div className="results-banner-text">
          <strong>Analysis complete</strong>
          <span>Sentiment, summary, and next steps for this call.</span>
        </div>
        {audioFilename && (
          <div className="results-banner-meta">
            <span className="results-ref">Audio: {audioFilename}</span>
          </div>
        )}
      </div>

      <Card>
        <CardHeader title="Sentiment" subtitle="Overall tone of the call" />
        <SentimentBadge sentiment={analysis.sentiment} />
      </Card>

      <Card>
        <CardHeader title="Summary" subtitle="What happened on the call" />
        <p className="results-body-text">{analysis.summary || 'No summary available.'}</p>
      </Card>

      <Card>
        <CardHeader title="Next Steps" subtitle="Recommended follow-up actions" />
        {nextSteps.length > 0 ? (
          <ul className="results-list">
            {nextSteps.map((step, i) => (
              <li key={i}>{step}</li>
            ))}
          </ul>
        ) : (
          <p className="results-muted">No next steps identified.</p>
        )}
      </Card>

      <Card>
        <TranscriptPanel transcript={transcript} title="Transcript" expanded />
      </Card>
    </div>
  );
}
