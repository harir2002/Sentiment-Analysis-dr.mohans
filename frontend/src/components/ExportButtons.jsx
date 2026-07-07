import { downloadExport } from '../services/api';
import { Card, CardHeader, Button } from './ui';

export default function ExportSection({ jobId, compact = false }) {
  if (!jobId) return null;

  const handleExport = () => downloadExport(jobId, 'docx');

  if (compact) {
    return (
      <Button variant="secondary" size="sm" onClick={handleExport}>
        Download Word Report
      </Button>
    );
  }

  return (
    <Card className="export-card">
      <CardHeader
        title="Export Word Report"
        subtitle="Download a client-ready comparison report (.docx) with all four solutions"
      />
      <div className="export-actions">
        <Button variant="primary" size="sm" onClick={handleExport}>
          Export Word Report
        </Button>
      </div>
    </Card>
  );
}
