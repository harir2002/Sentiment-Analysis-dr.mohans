import TranscriptPanel from './TranscriptPanel';
import { Card, CardHeader, Alert, SentimentBadge } from './ui';
import { getNextStepsFromAnalysis } from '../utils/nextSteps';

export function pickClientResult(results, ranking) {
  if (!results?.length) return null;
  const completed = results.find((r) => r.status === 'completed' && r.analysis);
  return completed || results[0];
}

export default function AnalysisResults({ result }) {
  if (!result) return null;

  const { analysis, status, error, transcript } = result;
  const pending = ['queued', 'running', 'timed_out'].includes(status);
  const failed = status === 'failed' || status === 'rate_limited';
  const completed = status === 'completed' && analysis;

  if (pending) {
    return (
      <Alert variant="info" title="Transcription in progress">
        Your call is being transcribed and analyzed. Results will appear here when ready.
      </Alert>
    );
  }

  if (failed) {
    return (
      <Alert variant="danger" title="Analysis could not be completed">
        {error || 'Please try uploading the file again or contact support if the issue persists.'}
      </Alert>
    );
  }

  if (!completed) return null;

  const nextSteps = getNextStepsFromAnalysis(analysis);

  return (
    <div className="results-layout">
      <div className="results-banner">
        <div className="results-banner-text">
          <strong>Analysis complete</strong>
          <span>Your call has been transcribed and reviewed.</span>
        </div>
      </div>

      <Card>
        <CardHeader title="Sentiment" subtitle="Overall tone of the call" />
        <SentimentBadge sentiment={analysis.sentiment} />
      </Card>

      <Card>
        <CardHeader title="Summary" subtitle="Overview of the conversation" />
        <p className="results-body-text">{analysis.summary || 'No summary available.'}</p>
      </Card>

      <Card>
        <CardHeader title="Next Steps" subtitle="Recommended follow-up actions" />
        {nextSteps.length > 0 ? (
          <ul className="results-list">
            {nextSteps.map((item, i) => (
              <li key={i}>{item}</li>
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
