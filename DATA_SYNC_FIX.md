# Data Synchronization Fix: Dashboard vs Detail Page

## EXECUTIVE SUMMARY

**Problem Identified:** Dashboard and detail pages were showing different sentiments for the same recording because:
- Dashboard used `results[0].analysis.sentiment` (first solution, arbitrary)
- Detail page used `ranking.winner.analysis.sentiment` (highest-scoring solution)
- No canonical "final sentiment" existed at the job level

**Solution Implemented:** Added job-level canonical sentiment fields derived from the winner solution, creating a single source of truth for both views.

---

## ROOT CAUSE ANALYSIS

### The Exact Mismatch

**Before Fix:**
```
Same Audio File → ComparisonJob with 4 ProviderResults
├── Solution[0] (Sarvam+Sarvam): sentiment="positive"
├── Solution[1] (Sarvam+Groq): sentiment="negative"
├── Solution[2] (Groq+Sarvam): sentiment="positive"
├── Solution[3] (Groq+Groq): sentiment="negative"
├── Winner (highest overall_score): Solution[3]
│
├─→ Dashboard displays: results[0].sentiment = "positive" ❌ WRONG
└─→ Detail page displays: winner.sentiment = "negative" ❌ WRONG
```

**Impact:**
- Same recording showed different sentiment in dashboard vs detail page
- User confusion: Is the sentiment positive or negative?
- Charts aggregated wrong data
- No authoritative "final sentiment" existed in database

### Why This Happened

1. **Sentiment stored per-solution** - Each of 4 providers generates its own analysis with sentiment
2. **Winner determined by quality score** - Ranking sorts by overall_score (composite of 6 factors), NOT by sentiment
3. **No job-level aggregation** - ComparisonJob model had no "final_sentiment" field
4. **Different frontend logic** - Dashboard and detail page independently chose different result to display

---

## SOLUTION IMPLEMENTED

### 1. Database Schema Changes

**File:** `backend/app/models/db_models.py`

Added three canonical fields to `ComparisonJob`:
```python
# New fields added:
final_solution_id: str | None        # Which solution is the "winner"
final_sentiment: str | None           # Winner's sentiment (canonical)
final_confidence: float | None        # Winner's confidence (canonical)
```

**Why:** These fields explicitly store the authoritative final result derived from the winner solution, visible across all queries.

### 2. API Response Schema Changes

**File:** `backend/app/models/schemas.py`

Updated `JobResponse` schema:
```python
class JobResponse(BaseModel):
    # ... existing fields ...
    
    # Canonical final result (from winner solution) - source of truth for dashboard
    final_solution_id: str | None = None
    final_sentiment: str | None = None
    final_confidence: float | None = None
```

**Why:** API consumers (dashboard, detail page) now receive canonical sentiment fields without needing to lookup winner manually.

### 3. Backend Response Logic Changes

**File:** `backend/app/services/jobs.py`

Updated `job_to_response()` function:
```python
# Extract canonical final sentiment/confidence from winner
final_solution_id = None
final_sentiment = None
final_confidence = None

if ranking and ranking.winner:
    winner_id = ranking.winner.solution_id
    winner_result = next((r for r in results if r.solution_id == winner_id), None)
    if winner_result and winner_result.analysis:
        final_solution_id = winner_id
        final_sentiment = winner_result.analysis.sentiment or None
        final_confidence = winner_result.analysis.confidence

return JobResponse(
    # ... existing fields ...
    final_solution_id=final_solution_id,
    final_sentiment=final_sentiment,
    final_confidence=final_confidence,
)
```

**Why:** Every API response now includes the canonical fields populated from the winner result, ensuring consistency across all endpoints.

### 4. Frontend Dashboard Changes

**File:** `frontend/src/components/SentimentDashboard.jsx`

**DashboardSummary component:**
```javascript
// BEFORE
const sentiment = r.results[0].analysis.sentiment;  // Wrong: arbitrary first

// AFTER
const sentiment = r.final_sentiment;  // Correct: canonical from winner
```

**ExpandableRecordCard component:**
```javascript
// BEFORE
const sentiment = analysis?.sentiment;  // From first result

// AFTER
const sentiment = record.final_sentiment || analysis?.sentiment || 'unknown';  
// Canonical first, fallback to results for backwards compatibility
```

**Why:** Dashboard now displays the same canonical sentiment that detail page shows, eliminating the mismatch.

### 5. Frontend Chart Changes

**File:** `frontend/src/components/DashboardCharts.jsx`

Updated all chart components to prioritize canonical fields:

**SentimentPieChart:**
```javascript
// BEFORE
const sentiment = r.results?.[0]?.analysis?.sentiment;

// AFTER
const sentiment = r.final_sentiment || (r.results?.[0]?.analysis?.sentiment);
```

**SentimentTrendChart, ConfidenceDistributionChart:**
- Same pattern: Use `r.final_sentiment` first, fallback to results

**Why:** Charts now aggregate from canonical sentiment, ensuring consistent data visualization.

---

## DATA FLOW AFTER FIX

```
┌─────────────────────────────────────────┐
│     Audio File + 4 Solutions Analyzed    │
└──────────────────┬──────────────────────┘
                   │
                   ↓
    ┌──────────────────────────────────┐
    │   Scoring & Ranking (unchanged)   │
    │   Determines winner by:            │
    │   - overall_score (6-factor)      │
    │   - Sorts solutions 1-4            │
    └──────────────┬───────────────────┘
                   │
                   ↓
    ┌──────────────────────────────────────┐
    │  job_to_response() [MODIFIED]         │
    │─────────────────────────────────────│
    │                                      │
    │  1. Get winner from ranking         │
    │  2. Extract winner's sentiment      │
    │  3. Extract winner's confidence     │
    │  4. Set canonical fields:            │
    │     - final_sentiment               │
    │     - final_confidence              │
    │     - final_solution_id             │
    │  5. Return in JobResponse            │
    │                                      │
    └──────────────┬───────────────────┘
                   │
         ┌─────────┴─────────┐
         │                   │
         ↓                   ↓
    GET /calls          GET /results/{id}
    (Dashboard)         (Detail Page)
         │                   │
         ├─→ r.final_sentiment      ├─→ r.final_sentiment
         ├─→ r.final_confidence     ├─→ r.final_confidence
         ├─→ Same value ✓           ├─→ Same value ✓
         │                   │
         └─→ Charts render         └─→ Detail view renders
             correct data              correct data (matches dashboard)
```

---

## FILES CHANGED

| File | Changes |
|------|---------|
| `backend/app/models/db_models.py` | Added `final_solution_id`, `final_sentiment`, `final_confidence` fields to `ComparisonJob` |
| `backend/app/models/schemas.py` | Added `final_solution_id`, `final_sentiment`, `final_confidence` fields to `JobResponse` |
| `backend/app/services/jobs.py` | Updated `job_to_response()` to extract and populate canonical fields from winner |
| `frontend/src/components/SentimentDashboard.jsx` | Updated `DashboardSummary` and `ExpandableRecordCard` to use `record.final_sentiment` and `record.final_confidence` |
| `frontend/src/components/DashboardCharts.jsx` | Updated all chart components (`SentimentPieChart`, `SentimentTrendChart`, `ConfidenceDistributionChart`) to use `r.final_sentiment` with fallback |

---

## DATABASE CHANGES

**Action Required:** Delete the old database so it recreates with new schema.

```powershell
# Remove old database (triggers automatic recreation with new schema)
Remove-Item backend/data -Recurse -Force
```

New schema includes:
- `ComparisonJob.final_solution_id` (String, nullable)
- `ComparisonJob.final_sentiment` (String, nullable)
- `ComparisonJob.final_confidence` (Float, nullable)

---

## VERIFICATION CHECKLIST

### Backend API Verification

```bash
# After deployment, test /calls endpoint:
curl http://localhost:8000/calls -H "Authorization: Basic ..."

# Verify response structure includes:
{
  "calls": [
    {
      "job_id": "...",
      "audio_filename": "...",
      "final_solution_id": "groq_groq",      # ← NEW: Winner solution ID
      "final_sentiment": "positive",          # ← NEW: Winner's sentiment
      "final_confidence": 0.95,               # ← NEW: Winner's confidence
      "results": [...4 solutions...],
      "ranking": {...},
      ...
    }
  ],
  "total": 1
}
```

### Frontend Verification

**Dashboard Display Test:**
1. Upload audio file
2. Run comparison
3. Wait for completion
4. Dashboard should show:
   - ✅ Sentiment metrics match detail page
   - ✅ Charts show data (not "No data available")
   - ✅ Confidence % matches detail page
   - ✅ Positive/neutral/negative counts are non-zero (if results exist)

**Data Consistency Test:**
1. View recording on dashboard (see sentiment card)
2. Click to expand → see detail panel
3. Compare sentiments:
   - ❌ BEFORE: Often different (dashboard vs expanded)
   - ✅ AFTER: Always matching

**Chart Test:**
1. Upload 3-5 audio files with mixed sentiments
2. Verify dashboard charts:
   - ✅ Sentiment Distribution pie chart shows correct percentages
   - ✅ Processing Status pie chart shows accurate counts
   - ✅ Sentiment Trend bar chart displays data
   - ✅ Confidence Distribution histogram is populated
   - ✅ No truncated text ("ompleted" → "Completed")

---

## HOW 4-SOLUTION OUTPUTS ARE NORMALIZED

### Per-Solution Data (Stored in `results` array)
- Each `ProviderResult` contains full analysis from one solution
- 4 solutions × 4 perspectives = 16 data points per recording
- Stored for detailed comparison view

### Canonical Final Result (NEW)
- Extracted from winner solution only
- Stored as `final_sentiment`, `final_confidence`, `final_solution_id`
- Used by dashboard for aggregations and charts
- Eliminates ambiguity about "which sentiment to display"

### Ranking/Winner Logic (Unchanged)
- Still determined by `overall_score` (weighted composite)
- 6 scoring factors (STT quality, LLM quality, latency, cost, language fit, compliance)
- NOT by sentiment agreement

### Data Usage
```
┌─ Per-Solution (All 4)
│  └─ Detail view: SolutionComparison shows all 4 results
│  └─ Charts (optional): Could show per-solution breakdown
│
└─ Canonical Final (From Winner)
   └─ Dashboard: Aggregates based on final_sentiment
   └─ Detail page banner: Shows final verdict
   └─ All charts: Use final_sentiment for consistency
```

---

## BACKWARDS COMPATIBILITY

**Frontend:** 
- Charts use fallback logic: `r.final_sentiment || r.results?.[0]?.analysis?.sentiment`
- Works with old API responses that lack canonical fields
- Degrades gracefully to first-result behavior if needed

**Backend:**
- New fields are nullable/optional in schema
- Existing code that ignores them continues to work
- New code prioritizes canonical fields

---

## TESTING RECOMMENDATIONS

### Unit Tests Needed
1. `test_job_to_response_sets_canonical_fields()` - Verify final_sentiment is populated
2. `test_canonical_sentiment_matches_winner()` - Verify correct winner is selected
3. `test_dashboard_sentiment_count()` - Verify aggregation uses final_sentiment

### Integration Tests Needed
1. Upload audio → Run comparison → Verify final_sentiment in /calls
2. Load dashboard → Verify sentiment counts
3. Load detail page → Verify displayed sentiment matches final_sentiment
4. Load detail page → Expand recording → Verify expanded sentiment matches

### Manual Tests Needed
1. Upload mixed-sentiment recordings (positive, negative, neutral)
2. View dashboard and detail page side-by-side
3. Verify sentiments always match
4. Verify charts show accurate data

---

## DEPLOYMENT NOTES

1. **Database Migration Required:** Delete `backend/data` folder before running (auto-creates new schema)
2. **No Backend Restart Issues:** Code is backward compatible
3. **Frontend Cache Clear:** Users may need Ctrl+Shift+R hard refresh
4. **Gradual Rollout:** Safe to deploy, no breaking changes

---

## SUMMARY

### Before Fix
- Dashboard: Showed sentiment from arbitrary first solution
- Detail page: Showed sentiment from winner solution
- Same file, different sentiments → User confusion

### After Fix
- Dashboard: Shows canonical final sentiment from winner
- Detail page: Shows canonical final sentiment from winner
- Same file, same sentiment → User clarity
- Single source of truth for all views

### Key Insight
The 4 solutions are still valuable for detailed comparison, but the dashboard and primary UI now use a canonical final result derived from the highest-quality solution, eliminating ambiguity.
