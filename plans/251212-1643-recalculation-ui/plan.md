# Data Recalculation System - Frontend UI Plan

**Date:** 2025-12-12
**Author:** Claude (Planning Agent)
**Status:** Draft
**Estimated Effort:** 4-6 hours

---

## 1. Executive Summary

Implement a frontend UI for triggering and monitoring data recalculation operations. Users can select a date range, initiate recalculation, and observe real-time progress through a modal with step indicators, spinner, elapsed time, and error handling.

---

## 2. Analysis of Existing Codebase

### 2.1 Current UI Patterns in manager.html

| Pattern | Location | Description |
|---------|----------|-------------|
| **Modals** | Lines 769-990 | System Control Modal - inline styled `<div>` with fixed positioning, dark overlay, rounded corners |
| **Loading Modal** | Lines 1089-1141 | `showLoadingModal()` / `hideLoadingModal()` with progress bar, ESC to cancel |
| **Confirm Modal** | Lines 1063-1082 | `showConfirmModal(title, message, onConfirm, onCancel)` |
| **Toast Notifications** | Lines 1023-1061 | `showNotification(message, type)` - bottom-right toast with animation |
| **Date Pickers** | Lines 80-84 | Native HTML5 `<input type="date">` with dark styling |
| **Button Styles** | CSS: btn-action, btn-primary, btn-secondary | Gradient purple/blue primary, semi-transparent secondary |

### 2.2 Key Styling Variables (from manager.css)

```css
/* Colors */
Primary gradient: linear-gradient(135deg, #667eea 0%, #764ba2 100%)
Background dark: #0f0f0f, #1a1a1a, #1a1a2e
Text primary: #e0e0e0
Text secondary: #808080
Success: #34d399, #22c55e, #10b981
Warning: #fbbf24, #f59e0b
Error: #ef4444
Purple accent: #a855f7

/* Border radius */
Cards: 20px, 12px
Buttons: 12px, 8px

/* Borders */
Subtle: 1px solid rgba(255, 255, 255, 0.1)
Accent: 1px solid rgba(102, 126, 234, 0.3)
```

### 2.3 API Communication Pattern

- Uses `fetch()` with `X-API-Key: dev-api-key-123` header
- Base URL: `API_BASE` variable (localhost:5000 or production)
- No existing SSE/WebSocket implementations found
- Currently uses `setInterval()` for polling status updates

---

## 3. UI Design Specification

### 3.1 Trigger Button Placement

**Recommended Location:** System Controls Modal (lines 769-990)

Add new section after "Database Control" card (~line 958):

```
Emergency Actions
    |
    +-- [NEW] Data Recalculation Section
    |
Emergency Actions (existing)
```

**Rationale:**
- System Controls modal already handles admin operations (sync, restart, clear logs)
- Keeps admin functions centralized
- Accessible via "Controls" button in system status bar (line 150)

### 3.2 Recalculation Modal Design

```
+----------------------------------------------------------+
|  [x]  Data Recalculation                                  |
+----------------------------------------------------------+
|                                                           |
|  Date Range                                               |
|  [Start Date] ---- to ---- [End Date]                    |
|  [Today] [Yesterday] [Last 7 Days] [Last 30 Days]        |
|                                                           |
|  --------------------------------------------------------|
|                                                           |
|  Progress                                    [Cancel]     |
|  +----------------------------------------------------+  |
|  |  Step 1: Fetching shift data          [========  ] |  |
|  |  Step 2: Processing activities        [          ] |  |
|  |  Step 3: Calculating scores           [          ] |  |
|  |  Step 4: Updating cache               [          ] |  |
|  +----------------------------------------------------+  |
|                                                           |
|  Current Stage: Fetching shift data from Connecteam...   |
|  Elapsed: 00:45                                          |
|  Records processed: 1,234 / 5,678                        |
|                                                           |
|  [Start Recalculation]                                   |
|                                                           |
+----------------------------------------------------------+
```

### 3.3 Step Indicators

| Step | Label | Backend Stage |
|------|-------|---------------|
| 1 | Fetching shift data | `fetch_shifts` |
| 2 | Processing activities | `process_activities` |
| 3 | Calculating scores | `calculate_scores` |
| 4 | Updating cache | `update_cache` |

**States:**
- `pending` - Gray circle, text muted
- `in_progress` - Animated spinner, text white, progress bar
- `completed` - Green checkmark, text green
- `error` - Red X, text red

### 3.4 Error Handling UI

When stuck (no progress > 30 seconds):
```
+----------------------------------------------------+
|  ! Warning: Stage appears stuck                    |
|  No progress for 35 seconds                        |
|  [Retry Stage] [Skip & Continue] [Abort]           |
+----------------------------------------------------+
```

---

## 4. Real-Time Updates Strategy

### 4.1 Recommended: Server-Sent Events (SSE)

**Why SSE over alternatives:**

| Method | Pros | Cons |
|--------|------|------|
| **SSE** | Simple, built-in reconnect, HTTP/1.1 compatible | One-way only |
| WebSocket | Bi-directional | Overkill, complex setup |
| Polling | Simple | Inefficient, delays, server load |

**SSE fits because:**
- Updates are server-to-client only
- Native browser support (`EventSource`)
- Auto-reconnect on connection drop
- Flask supports SSE easily

### 4.2 SSE Implementation Pattern

**Frontend (JavaScript):**
```javascript
function startRecalculation(startDate, endDate) {
    const eventSource = new EventSource(
        `${API_BASE}/api/recalculation/stream?start=${startDate}&end=${endDate}`
    );

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        updateProgress(data);
    };

    eventSource.onerror = (err) => {
        handleError(err);
        eventSource.close();
    };

    // Store reference for cancel
    window.recalcEventSource = eventSource;
}

function cancelRecalculation() {
    if (window.recalcEventSource) {
        window.recalcEventSource.close();
        fetch(`${API_BASE}/api/recalculation/cancel`, { method: 'POST' });
    }
}
```

**Backend event format:**
```json
{
    "stage": "calculate_scores",
    "stage_index": 3,
    "total_stages": 4,
    "progress": 45,
    "message": "Processing employee John Doe...",
    "records_processed": 1234,
    "total_records": 5678,
    "elapsed_seconds": 45,
    "status": "running"
}
```

### 4.3 Fallback: Polling (if SSE not feasible)

```javascript
let recalcPollInterval = null;
let recalcJobId = null;

async function pollProgress() {
    const response = await fetch(
        `${API_BASE}/api/recalculation/status/${recalcJobId}`
    );
    const data = await response.json();
    updateProgress(data);

    if (data.status === 'completed' || data.status === 'error') {
        clearInterval(recalcPollInterval);
    }
}

async function startRecalculation(startDate, endDate) {
    const response = await fetch(`${API_BASE}/api/recalculation/start`, {
        method: 'POST',
        body: JSON.stringify({ start_date: startDate, end_date: endDate })
    });
    const { job_id } = await response.json();
    recalcJobId = job_id;
    recalcPollInterval = setInterval(pollProgress, 1000);
}
```

---

## 5. Implementation Plan

### Phase 1: UI Components (HTML/CSS)

**File:** `frontend/manager.html`

#### 5.1.1 Add Recalculation Section to System Controls Modal

Insert after line ~958 (before Emergency Actions):

```html
<!-- Data Recalculation Section -->
<div style="
    background: rgba(255,255,255,0.03);
    border: 1px solid rgba(255,255,255,0.1);
    border-radius: 10px;
    padding: 20px;
">
    <div style="display: flex; justify-content: space-between; align-items: start;">
        <div>
            <h3 style="margin: 0 0 10px 0; color: #8b5cf6;">Data Recalculation</h3>
            <div style="color: #808080; font-size: 0.9em;">
                <div>Recalculate productivity scores for date range</div>
                <div>Use when data corrections needed</div>
            </div>
        </div>
        <button onclick="openRecalculationModal()" style="
            padding: 8px 16px;
            background: #8b5cf6;
            color: white;
            border: none;
            border-radius: 6px;
            cursor: pointer;
        ">Open Recalculation Tool</button>
    </div>
</div>
```

#### 5.1.2 Add Recalculation Modal

Insert after System Control Modal (after line ~991):

```html
<!-- Recalculation Modal -->
<div id="recalculation-modal" style="
    display: none;
    position: fixed;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    background: rgba(0,0,0,0.85);
    z-index: 10001;
">
    <div style="
        position: absolute;
        top: 50%;
        left: 50%;
        transform: translate(-50%, -50%);
        background: #1a1a1a;
        padding: 30px;
        border-radius: 16px;
        width: 90%;
        max-width: 600px;
        max-height: 85vh;
        overflow-y: auto;
        border: 1px solid rgba(139, 92, 246, 0.3);
    ">
        <!-- Header -->
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px;">
            <h2 style="margin: 0; color: #e0e0e0; display: flex; align-items: center; gap: 10px;">
                <i class="fas fa-calculator" style="color: #8b5cf6;"></i>
                Data Recalculation
            </h2>
            <button onclick="closeRecalculationModal()" style="
                background: none;
                border: none;
                color: #808080;
                font-size: 1.5em;
                cursor: pointer;
            ">&times;</button>
        </div>

        <!-- Date Range Selection -->
        <div id="recalc-date-section" style="margin-bottom: 25px;">
            <label style="display: block; color: #b0b0b0; margin-bottom: 10px; font-weight: 500;">
                Select Date Range
            </label>
            <div style="display: flex; gap: 10px; align-items: center; margin-bottom: 15px;">
                <input type="date" id="recalcStartDate" style="
                    flex: 1;
                    padding: 10px 12px;
                    background: rgba(255,255,255,0.05);
                    color: #e0e0e0;
                    border: 1px solid rgba(255,255,255,0.2);
                    border-radius: 8px;
                ">
                <span style="color: #808080;">to</span>
                <input type="date" id="recalcEndDate" style="
                    flex: 1;
                    padding: 10px 12px;
                    background: rgba(255,255,255,0.05);
                    color: #e0e0e0;
                    border: 1px solid rgba(255,255,255,0.2);
                    border-radius: 8px;
                ">
            </div>
            <div style="display: flex; gap: 8px; flex-wrap: wrap;">
                <button onclick="setRecalcRange('today')" class="btn-action btn-secondary" style="padding: 6px 14px; font-size: 0.85em;">Today</button>
                <button onclick="setRecalcRange('yesterday')" class="btn-action btn-secondary" style="padding: 6px 14px; font-size: 0.85em;">Yesterday</button>
                <button onclick="setRecalcRange('week')" class="btn-action btn-secondary" style="padding: 6px 14px; font-size: 0.85em;">Last 7 Days</button>
                <button onclick="setRecalcRange('month')" class="btn-action btn-secondary" style="padding: 6px 14px; font-size: 0.85em;">Last 30 Days</button>
            </div>
        </div>

        <!-- Progress Section (hidden initially) -->
        <div id="recalc-progress-section" style="display: none;">
            <!-- Step indicators -->
            <div id="recalc-steps" style="margin-bottom: 20px;">
                <!-- Steps populated by JavaScript -->
            </div>

            <!-- Current status -->
            <div style="
                background: rgba(255,255,255,0.03);
                border-radius: 10px;
                padding: 15px;
                margin-bottom: 15px;
            ">
                <div style="display: flex; justify-content: space-between; margin-bottom: 10px;">
                    <span id="recalc-current-stage" style="color: #e0e0e0; font-weight: 500;">
                        Initializing...
                    </span>
                    <span id="recalc-elapsed" style="color: #808080; font-size: 0.9em;">
                        00:00
                    </span>
                </div>
                <div style="
                    background: rgba(255,255,255,0.1);
                    border-radius: 8px;
                    height: 8px;
                    overflow: hidden;
                ">
                    <div id="recalc-progress-bar" style="
                        width: 0%;
                        height: 100%;
                        background: linear-gradient(90deg, #8b5cf6, #a855f7);
                        transition: width 0.3s ease;
                    "></div>
                </div>
                <div style="display: flex; justify-content: space-between; margin-top: 8px;">
                    <span id="recalc-records" style="color: #808080; font-size: 0.85em;">
                        0 records processed
                    </span>
                    <span id="recalc-percent" style="color: #a855f7; font-weight: 600;">
                        0%
                    </span>
                </div>
            </div>

            <!-- Error/Warning display -->
            <div id="recalc-alert" style="display: none; padding: 12px 15px; border-radius: 8px; margin-bottom: 15px;">
            </div>
        </div>

        <!-- Action buttons -->
        <div style="display: flex; gap: 10px; justify-content: flex-end;">
            <button id="recalc-cancel-btn" onclick="cancelRecalculation()" style="
                display: none;
                padding: 10px 20px;
                background: rgba(239, 68, 68, 0.2);
                color: #ef4444;
                border: 1px solid rgba(239, 68, 68, 0.3);
                border-radius: 8px;
                cursor: pointer;
            ">
                <i class="fas fa-stop"></i> Cancel
            </button>
            <button id="recalc-start-btn" onclick="startRecalculation()" style="
                padding: 10px 24px;
                background: linear-gradient(135deg, #8b5cf6 0%, #a855f7 100%);
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 600;
            ">
                <i class="fas fa-play"></i> Start Recalculation
            </button>
        </div>
    </div>
</div>
```

### Phase 2: JavaScript Functions

Add to `<script>` section (after line ~4545):

```javascript
// ============= DATA RECALCULATION FUNCTIONS =============
const RECALC_STAGES = [
    { id: 'fetch_shifts', label: 'Fetching shift data', icon: 'fa-clock' },
    { id: 'process_activities', label: 'Processing activities', icon: 'fa-cogs' },
    { id: 'calculate_scores', label: 'Calculating scores', icon: 'fa-calculator' },
    { id: 'update_cache', label: 'Updating cache', icon: 'fa-database' }
];

let recalcEventSource = null;
let recalcStartTime = null;
let recalcElapsedInterval = null;
let recalcStuckTimeout = null;
let lastProgressUpdate = null;

// Open/close modal
function openRecalculationModal() {
    document.getElementById('recalculation-modal').style.display = 'block';
    resetRecalculationUI();
    // Default to today
    setRecalcRange('today');
}

function closeRecalculationModal() {
    if (recalcEventSource) {
        cancelRecalculation();
    }
    document.getElementById('recalculation-modal').style.display = 'none';
}

// Date range helpers
function setRecalcRange(range) {
    const today = new Date();
    const startInput = document.getElementById('recalcStartDate');
    const endInput = document.getElementById('recalcEndDate');

    const formatDate = (d) => d.toISOString().split('T')[0];

    switch(range) {
        case 'today':
            startInput.value = formatDate(today);
            endInput.value = formatDate(today);
            break;
        case 'yesterday':
            const yesterday = new Date(today);
            yesterday.setDate(yesterday.getDate() - 1);
            startInput.value = formatDate(yesterday);
            endInput.value = formatDate(yesterday);
            break;
        case 'week':
            const weekAgo = new Date(today);
            weekAgo.setDate(weekAgo.getDate() - 7);
            startInput.value = formatDate(weekAgo);
            endInput.value = formatDate(today);
            break;
        case 'month':
            const monthAgo = new Date(today);
            monthAgo.setDate(monthAgo.getDate() - 30);
            startInput.value = formatDate(monthAgo);
            endInput.value = formatDate(today);
            break;
    }
}

// Initialize step indicators
function initStepIndicators() {
    const container = document.getElementById('recalc-steps');
    container.innerHTML = RECALC_STAGES.map((stage, idx) => `
        <div id="recalc-step-${stage.id}" style="
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 12px;
            margin-bottom: 8px;
            background: rgba(255,255,255,0.02);
            border-radius: 8px;
            border-left: 3px solid #4a4a4a;
        ">
            <div id="recalc-step-icon-${stage.id}" style="
                width: 32px;
                height: 32px;
                border-radius: 50%;
                background: rgba(255,255,255,0.1);
                display: flex;
                align-items: center;
                justify-content: center;
            ">
                <i class="fas ${stage.icon}" style="color: #808080;"></i>
            </div>
            <div style="flex: 1;">
                <div style="color: #808080; font-size: 0.95em;">${stage.label}</div>
                <div id="recalc-step-status-${stage.id}" style="font-size: 0.8em; color: #606060; margin-top: 2px;">
                    Pending
                </div>
            </div>
            <div id="recalc-step-progress-${stage.id}" style="width: 60px; text-align: right; color: #606060; font-size: 0.85em;">
                --
            </div>
        </div>
    `).join('');
}

// Update a specific step's visual state
function updateStepUI(stageId, state, progress = null, message = null) {
    const stepEl = document.getElementById(`recalc-step-${stageId}`);
    const iconEl = document.getElementById(`recalc-step-icon-${stageId}`);
    const statusEl = document.getElementById(`recalc-step-status-${stageId}`);
    const progressEl = document.getElementById(`recalc-step-progress-${stageId}`);

    if (!stepEl) return;

    switch(state) {
        case 'pending':
            stepEl.style.borderLeftColor = '#4a4a4a';
            iconEl.innerHTML = `<i class="fas ${RECALC_STAGES.find(s => s.id === stageId)?.icon || 'fa-circle'}" style="color: #808080;"></i>`;
            statusEl.textContent = 'Pending';
            statusEl.style.color = '#606060';
            progressEl.textContent = '--';
            break;
        case 'in_progress':
            stepEl.style.borderLeftColor = '#8b5cf6';
            stepEl.style.background = 'rgba(139, 92, 246, 0.1)';
            iconEl.innerHTML = `<i class="fas fa-spinner fa-spin" style="color: #8b5cf6;"></i>`;
            statusEl.textContent = message || 'Processing...';
            statusEl.style.color = '#a855f7';
            progressEl.textContent = progress !== null ? `${progress}%` : '...';
            progressEl.style.color = '#8b5cf6';
            break;
        case 'completed':
            stepEl.style.borderLeftColor = '#22c55e';
            stepEl.style.background = 'rgba(34, 197, 94, 0.05)';
            iconEl.innerHTML = `<i class="fas fa-check" style="color: #22c55e;"></i>`;
            statusEl.textContent = 'Completed';
            statusEl.style.color = '#22c55e';
            progressEl.textContent = '100%';
            progressEl.style.color = '#22c55e';
            break;
        case 'error':
            stepEl.style.borderLeftColor = '#ef4444';
            stepEl.style.background = 'rgba(239, 68, 68, 0.1)';
            iconEl.innerHTML = `<i class="fas fa-times" style="color: #ef4444;"></i>`;
            statusEl.textContent = message || 'Error';
            statusEl.style.color = '#ef4444';
            progressEl.style.color = '#ef4444';
            break;
    }
}

// Reset UI to initial state
function resetRecalculationUI() {
    document.getElementById('recalc-date-section').style.display = 'block';
    document.getElementById('recalc-progress-section').style.display = 'none';
    document.getElementById('recalc-start-btn').style.display = 'inline-flex';
    document.getElementById('recalc-cancel-btn').style.display = 'none';
    document.getElementById('recalc-alert').style.display = 'none';
    document.getElementById('recalc-progress-bar').style.width = '0%';
    document.getElementById('recalc-percent').textContent = '0%';
    document.getElementById('recalc-records').textContent = '0 records processed';
    document.getElementById('recalc-elapsed').textContent = '00:00';

    if (recalcElapsedInterval) clearInterval(recalcElapsedInterval);
    if (recalcStuckTimeout) clearTimeout(recalcStuckTimeout);
}

// Start recalculation
async function startRecalculation() {
    const startDate = document.getElementById('recalcStartDate').value;
    const endDate = document.getElementById('recalcEndDate').value;

    if (!startDate || !endDate) {
        showNotification('Please select both start and end dates', 'warning');
        return;
    }

    if (new Date(startDate) > new Date(endDate)) {
        showNotification('Start date must be before end date', 'warning');
        return;
    }

    // Confirm if large range
    const daysDiff = Math.ceil((new Date(endDate) - new Date(startDate)) / (1000 * 60 * 60 * 24));
    if (daysDiff > 7) {
        showConfirmModal(
            'Large Date Range',
            `You are about to recalculate ${daysDiff} days of data. This may take several minutes. Continue?`,
            () => executeRecalculation(startDate, endDate)
        );
    } else {
        executeRecalculation(startDate, endDate);
    }
}

function executeRecalculation(startDate, endDate) {
    // Update UI
    document.getElementById('recalc-date-section').style.display = 'none';
    document.getElementById('recalc-progress-section').style.display = 'block';
    document.getElementById('recalc-start-btn').style.display = 'none';
    document.getElementById('recalc-cancel-btn').style.display = 'inline-flex';

    initStepIndicators();

    // Start elapsed timer
    recalcStartTime = Date.now();
    recalcElapsedInterval = setInterval(updateElapsedTime, 1000);
    lastProgressUpdate = Date.now();

    // Start SSE connection
    const url = `${API_BASE}/api/recalculation/stream?start_date=${startDate}&end_date=${endDate}`;
    recalcEventSource = new EventSource(url);

    recalcEventSource.onmessage = (event) => {
        lastProgressUpdate = Date.now();
        clearStuckWarning();

        const data = JSON.parse(event.data);
        handleProgressUpdate(data);
    };

    recalcEventSource.onerror = (err) => {
        console.error('SSE Error:', err);
        recalcEventSource.close();
        recalcEventSource = null;
        showRecalcAlert('error', 'Connection lost. Please try again.');
        document.getElementById('recalc-cancel-btn').style.display = 'none';
        document.getElementById('recalc-start-btn').textContent = 'Retry';
        document.getElementById('recalc-start-btn').style.display = 'inline-flex';
    };

    // Start stuck detection
    startStuckDetection();
}

function handleProgressUpdate(data) {
    // Update overall progress
    const overallProgress = data.overall_progress || 0;
    document.getElementById('recalc-progress-bar').style.width = `${overallProgress}%`;
    document.getElementById('recalc-percent').textContent = `${Math.round(overallProgress)}%`;

    // Update current stage text
    const currentStage = RECALC_STAGES.find(s => s.id === data.stage);
    document.getElementById('recalc-current-stage').textContent =
        data.message || currentStage?.label || 'Processing...';

    // Update records count
    if (data.records_processed !== undefined) {
        const total = data.total_records ? ` / ${data.total_records.toLocaleString()}` : '';
        document.getElementById('recalc-records').textContent =
            `${data.records_processed.toLocaleString()}${total} records processed`;
    }

    // Update step indicators
    RECALC_STAGES.forEach((stage, idx) => {
        const currentIdx = RECALC_STAGES.findIndex(s => s.id === data.stage);

        if (idx < currentIdx) {
            updateStepUI(stage.id, 'completed');
        } else if (idx === currentIdx) {
            updateStepUI(stage.id, 'in_progress', data.stage_progress, data.message);
        } else {
            updateStepUI(stage.id, 'pending');
        }
    });

    // Check for completion
    if (data.status === 'completed') {
        handleRecalcComplete(data);
    } else if (data.status === 'error') {
        handleRecalcError(data);
    }
}

function handleRecalcComplete(data) {
    if (recalcEventSource) {
        recalcEventSource.close();
        recalcEventSource = null;
    }
    clearInterval(recalcElapsedInterval);
    clearTimeout(recalcStuckTimeout);

    // Mark all steps complete
    RECALC_STAGES.forEach(stage => updateStepUI(stage.id, 'completed'));

    // Update UI
    document.getElementById('recalc-progress-bar').style.width = '100%';
    document.getElementById('recalc-percent').textContent = '100%';
    document.getElementById('recalc-current-stage').textContent = 'Recalculation completed!';
    document.getElementById('recalc-cancel-btn').style.display = 'none';

    showRecalcAlert('success', `Successfully recalculated ${data.records_processed?.toLocaleString() || 'all'} records.`);
    showNotification('Recalculation completed successfully!', 'success');

    // Add close button
    document.getElementById('recalc-start-btn').innerHTML = '<i class="fas fa-check"></i> Done';
    document.getElementById('recalc-start-btn').onclick = closeRecalculationModal;
    document.getElementById('recalc-start-btn').style.display = 'inline-flex';
    document.getElementById('recalc-start-btn').style.background = 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)';
}

function handleRecalcError(data) {
    if (recalcEventSource) {
        recalcEventSource.close();
        recalcEventSource = null;
    }
    clearInterval(recalcElapsedInterval);
    clearTimeout(recalcStuckTimeout);

    // Mark current step as error
    if (data.stage) {
        updateStepUI(data.stage, 'error', null, data.error || 'Failed');
    }

    showRecalcAlert('error', data.error || 'An error occurred during recalculation.');

    document.getElementById('recalc-cancel-btn').style.display = 'none';
    document.getElementById('recalc-start-btn').innerHTML = '<i class="fas fa-redo"></i> Retry';
    document.getElementById('recalc-start-btn').onclick = () => resetRecalculationUI();
    document.getElementById('recalc-start-btn').style.display = 'inline-flex';
}

function cancelRecalculation() {
    showConfirmModal('Cancel Recalculation', 'Are you sure you want to cancel? Progress will be lost.', async () => {
        if (recalcEventSource) {
            recalcEventSource.close();
            recalcEventSource = null;
        }

        // Notify backend
        try {
            await fetch(`${API_BASE}/api/recalculation/cancel`, {
                method: 'POST',
                headers: { 'X-API-Key': 'dev-api-key-123' }
            });
        } catch (e) {
            console.warn('Cancel request failed:', e);
        }

        clearInterval(recalcElapsedInterval);
        clearTimeout(recalcStuckTimeout);

        showNotification('Recalculation cancelled', 'warning');
        resetRecalculationUI();
    });
}

// Elapsed time display
function updateElapsedTime() {
    const elapsed = Math.floor((Date.now() - recalcStartTime) / 1000);
    const mins = Math.floor(elapsed / 60).toString().padStart(2, '0');
    const secs = (elapsed % 60).toString().padStart(2, '0');
    document.getElementById('recalc-elapsed').textContent = `${mins}:${secs}`;
}

// Stuck detection
function startStuckDetection() {
    recalcStuckTimeout = setTimeout(checkIfStuck, 30000);
}

function checkIfStuck() {
    const timeSinceUpdate = Date.now() - lastProgressUpdate;
    if (timeSinceUpdate > 30000 && recalcEventSource) {
        showRecalcAlert('warning', `No progress for ${Math.floor(timeSinceUpdate/1000)} seconds. Process may be stuck.`);
    }
    // Check again in 10 seconds
    recalcStuckTimeout = setTimeout(checkIfStuck, 10000);
}

function clearStuckWarning() {
    const alert = document.getElementById('recalc-alert');
    if (alert.dataset.type === 'warning') {
        alert.style.display = 'none';
    }
}

// Alert display
function showRecalcAlert(type, message) {
    const alert = document.getElementById('recalc-alert');
    alert.dataset.type = type;

    const styles = {
        success: { bg: 'rgba(34, 197, 94, 0.15)', border: 'rgba(34, 197, 94, 0.3)', color: '#22c55e', icon: 'fa-check-circle' },
        warning: { bg: 'rgba(251, 191, 36, 0.15)', border: 'rgba(251, 191, 36, 0.3)', color: '#fbbf24', icon: 'fa-exclamation-triangle' },
        error: { bg: 'rgba(239, 68, 68, 0.15)', border: 'rgba(239, 68, 68, 0.3)', color: '#ef4444', icon: 'fa-times-circle' }
    };

    const s = styles[type] || styles.warning;

    alert.style.background = s.bg;
    alert.style.border = `1px solid ${s.border}`;
    alert.style.color = s.color;
    alert.innerHTML = `<i class="fas ${s.icon}" style="margin-right: 8px;"></i>${message}`;
    alert.style.display = 'block';
}

// Close modal when clicking outside
document.getElementById('recalculation-modal')?.addEventListener('click', function(e) {
    if (e.target === this) {
        closeRecalculationModal();
    }
});
```

### Phase 3: CSS Additions (Optional)

Add to `frontend/css/manager.css` if needed for cleaner code:

```css
/* Recalculation Modal Styles */
#recalculation-modal .step-indicator {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px;
    margin-bottom: 8px;
    background: rgba(255,255,255,0.02);
    border-radius: 8px;
    border-left: 3px solid #4a4a4a;
    transition: all 0.3s ease;
}

#recalculation-modal .step-indicator.in-progress {
    border-left-color: #8b5cf6;
    background: rgba(139, 92, 246, 0.1);
}

#recalculation-modal .step-indicator.completed {
    border-left-color: #22c55e;
    background: rgba(34, 197, 94, 0.05);
}

#recalculation-modal .step-indicator.error {
    border-left-color: #ef4444;
    background: rgba(239, 68, 68, 0.1);
}
```

---

## 6. Backend API Requirements

For frontend to work, backend must implement:

### 6.1 SSE Endpoint (Preferred)

```
GET /api/recalculation/stream?start_date=YYYY-MM-DD&end_date=YYYY-MM-DD
```

**Response:** Server-Sent Events stream

```
data: {"stage":"fetch_shifts","stage_index":0,"stage_progress":45,"overall_progress":12,"message":"Fetching shifts...","records_processed":123,"total_records":500,"status":"running"}

data: {"stage":"process_activities","stage_index":1,"stage_progress":0,"overall_progress":25,"message":"Starting activity processing...","status":"running"}

data: {"stage":"calculate_scores","stage_index":2,"stage_progress":100,"overall_progress":100,"message":"Complete!","records_processed":500,"status":"completed"}
```

### 6.2 Cancel Endpoint

```
POST /api/recalculation/cancel
```

**Response:**
```json
{"status": "cancelled", "message": "Recalculation cancelled"}
```

### 6.3 Alternative: Polling Endpoints

If SSE not feasible:

```
POST /api/recalculation/start
Body: {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}
Response: {"job_id": "uuid", "status": "started"}

GET /api/recalculation/status/{job_id}
Response: {same format as SSE event data}
```

---

## 7. Testing Checklist

- [ ] Modal opens/closes correctly
- [ ] Date pickers work with preset buttons
- [ ] Validation prevents invalid date ranges
- [ ] Confirmation shown for large ranges (>7 days)
- [ ] Progress bar animates smoothly
- [ ] Step indicators transition correctly
- [ ] Elapsed timer updates every second
- [ ] Stuck detection triggers after 30s
- [ ] Cancel button works and confirms
- [ ] Error states display properly
- [ ] Completion state shows correctly
- [ ] ESC key closes modal
- [ ] Click outside closes modal
- [ ] Toast notifications appear
- [ ] Mobile responsive (modal scrolls)

---

## 8. Unresolved Questions

1. **SSE vs Polling:** Does current Flask backend support SSE streaming? Need to verify backend capability.

2. **Concurrent Recalculations:** Should UI prevent multiple simultaneous recalculations? Recommend yes with job queue.

3. **Retry Logic:** If a stage fails, should there be a "retry this stage" option or always restart from beginning?

4. **Maximum Date Range:** Should there be a hard limit on how many days can be recalculated at once? (Suggest 90 days max)

5. **Authentication:** Current system uses `X-API-Key`. Should recalculation require elevated permissions?

---

## 9. File Summary

| File | Changes |
|------|---------|
| `frontend/manager.html` | Add recalculation section to System Controls modal (~line 958), add Recalculation Modal (~line 991), add JavaScript functions (~line 4545) |
| `frontend/css/manager.css` | Optional CSS cleanup for step indicators |
| Backend (separate plan) | SSE endpoint, cancel endpoint, recalculation logic |

---

**Plan Path:** `C:\Users\12104\Projects\Productivity_system\plans\251212-1643-recalculation-ui\plan.md`
