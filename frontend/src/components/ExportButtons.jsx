import { downloadExport } from '../services/api';
import { Button } from './ui';

export default function ExportSection({ jobId }) {
  if (!jobId) return null;

  const handleExport = () => downloadExport(jobId, 'docx');

  return (
    <Button variant="secondary" size="sm" onClick={handleExport}>
      Download Word Report
    </Button>
  );
}
