import {
  PieChart,
  Pie,
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
  Cell,
} from 'recharts';
import { Card, CardHeader } from './ui';
import {
  getCanonicalSentiment,
  getCanonicalConfidence,
  normalizeSentiment,
} from '../utils/canonicalResult';
import styles from './DashboardCharts.module.css';

// Sentiment Distribution Pie Chart — one canonical sentiment per recording
export function SentimentPieChart({ records }) {
  const sentimentCounts = { Positive: 0, Neutral: 0, Negative: 0 };

  records.forEach((r) => {
    const sentiment = normalizeSentiment(getCanonicalSentiment(r));
    if (sentiment === 'positive') sentimentCounts.Positive++;
    else if (sentiment === 'negative') sentimentCounts.Negative++;
    else if (sentiment === 'neutral') sentimentCounts.Neutral++;
  });

  const data = [
    { name: 'Positive', value: sentimentCounts.Positive, fill: '#10b981' },
    { name: 'Neutral', value: sentimentCounts.Neutral, fill: '#6b7280' },
    { name: 'Negative', value: sentimentCounts.Negative, fill: '#ef4444' },
  ].filter((item) => item.value > 0);

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader title="Sentiment Distribution" />
        <p className={styles['empty-chart']}>No data available</p>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader title="Sentiment Distribution" subtitle="Breakdown of all analyzed recordings" />
      <div style={{ width: '100%', height: '300px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="45%"
              innerRadius={0}
              outerRadius={80}
              fill="#8884d8"
              dataKey="value"
              nameKey="name"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.fill} />
              ))}
            </Pie>
            <Tooltip formatter={(value) => value} />
            <Legend verticalAlign="bottom" height={36} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className={styles['chart-legend-detail']}>
        {data.map((item) => (
          <div key={item.name} className={styles['legend-item']}>
            <span
              className={styles['legend-color']}
              style={{ backgroundColor: item.fill }}
            />
            <span className={styles['legend-text']}>
              {item.name}: {item.value} ({((item.value / data.reduce((sum, d) => sum + d.value, 0)) * 100).toFixed(0)}%)
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

// Sentiment Trend Over Time (Bar Chart)
export function SentimentTrendChart({ records }) {
  // Group records by date
  const dateMap = {};

  records.forEach((r) => {
    const sentiment = normalizeSentiment(getCanonicalSentiment(r));
    if (sentiment) {
      const date = new Date(r.created_at);
      const dateKey = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

      if (!dateMap[dateKey]) {
        dateMap[dateKey] = { date: dateKey, positive: 0, neutral: 0, negative: 0, total: 0 };
      }

      dateMap[dateKey][sentiment]++;
      dateMap[dateKey].total++;
    }
  });

  const data = Object.values(dateMap).sort((a, b) => new Date(a.date) - new Date(b.date));

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader title="Sentiment Trend" subtitle="Sentiment distribution over time" />
        <p className={styles['empty-chart']}>No data available</p>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader title="Sentiment Trend" subtitle="Sentiment distribution over time" />
      <div style={{ width: '100%', height: '300px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip />
            <Legend />
            <Bar dataKey="positive" stackId="sentiment" fill="#10b981" name="Positive" />
            <Bar dataKey="neutral" stackId="sentiment" fill="#6b7280" name="Neutral" />
            <Bar dataKey="negative" stackId="sentiment" fill="#ef4444" name="Negative" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

// Confidence Score Distribution
export function ConfidenceDistributionChart({ records }) {
  const bins = {
    '0-20%': 0,
    '20-40%': 0,
    '40-60%': 0,
    '60-80%': 0,
    '80-100%': 0,
  };

  records.forEach((r) => {
    const confidence = getCanonicalConfidence(r);
    if (confidence !== null) {
      const confidencePct = confidence * 100;
      if (confidencePct < 20) bins['0-20%']++;
      else if (confidencePct < 40) bins['20-40%']++;
      else if (confidencePct < 60) bins['40-60%']++;
      else if (confidencePct < 80) bins['60-80%']++;
      else bins['80-100%']++;
    }
  });

  const data = Object.entries(bins).map(([range, count]) => ({
    range,
    count,
  }));

  return (
    <Card>
      <CardHeader
        title="Confidence Score Distribution"
        subtitle="How confident are the analyses?"
      />
      <div style={{ width: '100%', height: '300px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="range" />
            <YAxis />
            <Tooltip />
            <Bar dataKey="count" fill="#3b82f6" name="Count" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

// Status Distribution Chart
export function StatusDistributionChart({ records }) {
  const statusMap = {
    Completed: 0,
    Processing: 0,
    Failed: 0,
  };

  records.forEach((r) => {
    const status = r.aggregate_status || r.status || 'unknown';
    if (status === 'completed') statusMap.Completed++;
    else if (status === 'running' || status === 'processing') statusMap.Processing++;
    else if (status === 'failed') statusMap.Failed++;
  });

  const data = [
    { name: 'Completed', value: statusMap.Completed, fill: '#10b981' },
    { name: 'Processing', value: statusMap.Processing, fill: '#f59e0b' },
    { name: 'Failed', value: statusMap.Failed, fill: '#ef4444' },
  ].filter((item) => item.value > 0);

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader title="Processing Status" />
        <p className={styles['empty-chart']}>No data available</p>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader title="Processing Status" subtitle="Job completion status" />
      <div style={{ width: '100%', height: '300px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              cx="50%"
              cy="45%"
              innerRadius={0}
              outerRadius={80}
              fill="#8884d8"
              dataKey="value"
              nameKey="name"
            >
              {data.map((entry, index) => (
                <Cell key={`cell-${index}`} fill={entry.fill} />
              ))}
            </Pie>
            <Tooltip formatter={(value) => value} />
            <Legend verticalAlign="bottom" height={36} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className={styles['chart-legend-detail']}>
        {data.map((item) => (
          <div key={item.name} className={styles['legend-item']}>
            <span
              className={styles['legend-color']}
              style={{ backgroundColor: item.fill }}
            />
            <span className={styles['legend-text']}>
              {item.name}: {item.value} ({((item.value / data.reduce((sum, d) => sum + d.value, 0)) * 100).toFixed(0)}%)
            </span>
          </div>
        ))}
      </div>
    </Card>
  );
}

// Model Performance Comparison
export function ModelPerformanceChart({ records }) {
  const modelStats = {};

  records.forEach((r) => {
    const hasResults = r.results?.length > 0;
    
    if (hasResults) {
      r.results.forEach((result) => {
        const model = result.llm_model || 'Unknown';
        const hasAnalysis = result.analysis?.confidence !== undefined;
        
        if (hasAnalysis) {
          if (!modelStats[model]) {
            modelStats[model] = {
              model,
              avgConfidence: 0,
              count: 0,
              totalScore: 0,
            };
          }
          modelStats[model].totalScore += result.analysis.confidence * 100;
          modelStats[model].count++;
        }
      });
    }
  });

  const data = Object.values(modelStats)
    .map((stat) => ({
      ...stat,
      avgConfidence: stat.count > 0 ? (stat.totalScore / stat.count).toFixed(1) : 0,
    }))
    .sort((a, b) => b.avgConfidence - a.avgConfidence);

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader title="Model Performance" />
        <p className={styles['empty-chart']}>No data available</p>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader title="Model Performance" subtitle="Average confidence by LLM model" />
      <div style={{ width: '100%', height: '300px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data} layout="vertical">
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis type="number" domain={[0, 100]} />
            <YAxis dataKey="model" type="category" width={120} tick={{ fontSize: 12 }} />
            <Tooltip formatter={(value) => `${value}%`} />
            <Bar dataKey="avgConfidence" fill="#8b5cf6" name="Avg Confidence (%)" />
          </BarChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}

// Average Runtime Trend
export function AverageRuntimeChart({ records }) {
  // Group by date and calculate average runtime
  const dateMap = {};

  records.forEach((r) => {
    if (r.total_runtime_seconds !== undefined && r.total_runtime_seconds > 0) {
      const date = new Date(r.created_at);
      const dateKey = date.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });

      if (!dateMap[dateKey]) {
        dateMap[dateKey] = { date: dateKey, totalTime: 0, count: 0 };
      }

      dateMap[dateKey].totalTime += r.total_runtime_seconds;
      dateMap[dateKey].count++;
    }
  });

  const data = Object.values(dateMap)
    .map((item) => ({
      date: item.date,
      avgRuntime: (item.totalTime / item.count).toFixed(2),
    }))
    .sort((a, b) => new Date(a.date) - new Date(b.date));

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader title="Processing Speed" />
        <p className={styles['empty-chart']}>No data available</p>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader title="Processing Speed" subtitle="Average runtime per analysis" />
      <div style={{ width: '100%', height: '300px' }}>
        <ResponsiveContainer width="100%" height="100%">
          <LineChart data={data}>
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis dataKey="date" />
            <YAxis />
            <Tooltip formatter={(value) => `${value}s`} />
            <Legend />
            <Line
              type="monotone"
              dataKey="avgRuntime"
              stroke="#06b6d4"
              strokeWidth={2}
              name="Avg Runtime (seconds)"
              dot={{ fill: '#06b6d4' }}
            />
          </LineChart>
        </ResponsiveContainer>
      </div>
    </Card>
  );
}
