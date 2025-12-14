# Intelligent Scheduling System - Professional Rebuild Plan

**Date:** December 13, 2025
**Status:** Planning
**Priority:** High

---

## Executive Summary

Current intelligent-schedule.html is a 2,532-line monolithic file with severe technical debt:
- Backend API exists but **NOT REGISTERED** in app.py
- Heavy code duplication (~20 copies of `removeEmployeeFromSchedule`)
- Falls back to static data (API never works)
- No database persistence for schedules
- Missing: skill matching, constraint handling, mobile support

**Recommendation:** Complete rebuild using modular architecture, real-time constraint validation, and manufacturing-specific features learned from market leaders (Shiftboard, Deputy, Celayix).

---

## Current State Analysis

### What Exists (Frontend - intelligent-schedule.html)

| Feature | Status | Notes |
|---------|--------|-------|
| Calendar View | Partial | Week view only, static data |
| Station Assignment Tab | Partial | Has UI, stubs for save |
| AI Proposal Tab | Skeleton | Predictions table shows but no real AI |
| Performance Tab | Partial | Rankings from static data |
| Live Monitor Tab | Skeleton | No real-time data |
| Edit Mode | Broken | Toggle exists but changes don't persist |
| Drag-and-Drop | None | Not implemented |

### What Exists (Backend - intelligent_schedule.py)

| Endpoint | Status | Notes |
|----------|--------|-------|
| `/api/schedule/weekly` | Code exists | **NOT REGISTERED** in app.py |
| `/api/schedule/staffing-needs` | Code exists | Uses predictions_enhanced table |
| Save/Update schedule | Missing | No CRUD operations |
| Employee availability | Missing | No endpoints |
| Shift swap/time-off | Missing | Separate system (employee_auth.py) |

### Database Tables

**Existing:**
- `predictions_enhanced` - Order volume predictions (working)
- `employees` - Employee data
- `activity_logs` - Productivity tracking

**Missing (Critical):**
- `schedule_master` - Schedule periods
- `schedule_details` - Individual shifts
- `employee_skills` - Skill/certification tracking
- `station_requirements` - Station skill requirements
- `shift_templates` - Reusable patterns (2-2-3, etc.)

---

## Competitive Analysis Summary

### Manufacturing-Specific Leaders

| Platform | Strength | Price |
|----------|----------|-------|
| **Shiftboard** | Skill-based scheduling, union compliance, 88% higher coverage | Enterprise |
| **Celayix** | Task-level granularity (station-based), any shift length | Enterprise |
| **Snap Schedule** | Multi-location, skill rules | Mid-tier |

### Key Differentiators to Implement

1. **Productivity-Aware Scheduling** (unique to us)
   - Use existing productivity_calculator.py data to inform staffing
   - Feedback loop: assign high performers to critical stations
   - Auto-suggest schedule changes based on actual output

2. **Station-Based Assignment**
   - Heat Press, QC, Film, Picking, Labeling stations
   - Each station has skill requirements and capacity

3. **Connecteam Integration**
   - Real clock times vs scheduled comparison
   - Attendance reliability scoring

---

## Architecture Proposal

### Backend Structure

```
backend/
├── api/
│   ├── scheduling/
│   │   ├── __init__.py
│   │   ├── schedules.py       # CRUD for schedules
│   │   ├── shifts.py          # Individual shift operations
│   │   ├── templates.py       # Shift templates (2-2-3)
│   │   ├── assignments.py     # Employee-to-shift assignments
│   │   ├── availability.py    # Employee availability
│   │   ├── conflicts.py       # Validation rules
│   │   └── recommendations.py # AI-powered suggestions
│   └── intelligent_schedule.py  # DEPRECATED (keep for reference)
├── services/
│   └── scheduling/
│       ├── constraint_engine.py    # OT, rest periods, skills
│       ├── auto_scheduler.py       # AI assignment algorithm
│       └── coverage_analyzer.py    # Gap detection
```

### Frontend Structure (Modular)

```
frontend/
├── scheduling/
│   ├── index.html              # Main page shell
│   ├── css/
│   │   ├── schedule-base.css
│   │   ├── calendar.css
│   │   └── components.css
│   └── js/
│       ├── schedule-app.js     # Main controller
│       ├── calendar-view.js    # Week/month calendar
│       ├── station-view.js     # Station-based view
│       ├── drag-drop.js        # Drag-and-drop engine
│       ├── conflict-checker.js # Client-side validation
│       ├── api-client.js       # API communication
│       └── components/
│           ├── shift-card.js
│           ├── employee-selector.js
│           └── time-picker.js
```

---

## Database Schema

### Core Tables

```sql
-- Schedule periods (e.g., "Week of Dec 16-22")
CREATE TABLE schedule_master (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    status ENUM('draft', 'published', 'locked') DEFAULT 'draft',
    published_at DATETIME,
    published_by INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE KEY (start_date, end_date)
);

-- Individual shifts
CREATE TABLE schedule_shifts (
    id INT AUTO_INCREMENT PRIMARY KEY,
    schedule_id INT NOT NULL,
    station_id INT,
    shift_date DATE NOT NULL,
    start_time TIME NOT NULL,
    end_time TIME NOT NULL,
    min_staff INT DEFAULT 1,
    max_staff INT,
    notes TEXT,
    FOREIGN KEY (schedule_id) REFERENCES schedule_master(id) ON DELETE CASCADE
);

-- Employee assignments to shifts
CREATE TABLE shift_assignments (
    id INT AUTO_INCREMENT PRIMARY KEY,
    shift_id INT NOT NULL,
    employee_id INT NOT NULL,
    assigned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    assigned_by INT,
    status ENUM('scheduled', 'confirmed', 'no_show', 'completed') DEFAULT 'scheduled',
    UNIQUE KEY (shift_id, employee_id),
    FOREIGN KEY (shift_id) REFERENCES schedule_shifts(id) ON DELETE CASCADE,
    FOREIGN KEY (employee_id) REFERENCES employees(id)
);

-- Production stations
CREATE TABLE stations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    code VARCHAR(20) NOT NULL UNIQUE,  -- 'heat_press', 'qc', etc.
    target_rate DECIMAL(6,2),  -- items per hour
    is_active BOOLEAN DEFAULT TRUE
);

-- Employee skills/certifications
CREATE TABLE employee_skills (
    id INT AUTO_INCREMENT PRIMARY KEY,
    employee_id INT NOT NULL,
    station_id INT NOT NULL,
    proficiency_level ENUM('trainee', 'competent', 'expert') DEFAULT 'competent',
    certified_date DATE,
    expires_at DATE,
    UNIQUE KEY (employee_id, station_id),
    FOREIGN KEY (employee_id) REFERENCES employees(id),
    FOREIGN KEY (station_id) REFERENCES stations(id)
);

-- Shift templates (reusable patterns)
CREATE TABLE shift_templates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,  -- "2-2-3 Panama Team A"
    pattern_type VARCHAR(50),     -- 'panama', 'dupont', 'custom'
    cycle_days INT DEFAULT 7,
    pattern_json JSON,            -- [{"day": 0, "start": "06:00", "end": "18:00"}, ...]
    is_active BOOLEAN DEFAULT TRUE
);
```

---

## Implementation Phases

### Phase 1: Foundation (Priority: Critical)
**Effort: 3-4 days**

1. **Register existing backend**
   - Add `intelligent_schedule.py` blueprint to app.py
   - Test existing endpoints work

2. **Create database tables**
   - Run migration for new schema
   - Seed stations table with Heat Press, QC, Film, Picking, Labeling

3. **Basic CRUD API**
   - POST /api/schedules - Create schedule period
   - GET /api/schedules/{id} - Get with shifts
   - PUT /api/schedules/{id}/shifts - Update shifts
   - POST /api/schedules/{id}/publish - Publish and notify

4. **Simplify frontend**
   - Strip out duplicated code
   - Connect to real API instead of fallback data
   - Week calendar with basic shift display

**Deliverable:** Working schedule that saves to database

---

### Phase 2: Station-Based Scheduling
**Effort: 2-3 days**

1. **Station management UI**
   - View stations with capacity and skill requirements
   - Assign employees to stations by skill level

2. **Coverage visualization**
   - Show staff count vs. required per station/hour
   - Color coding: green (covered), yellow (borderline), red (understaffed)

3. **Integrate predictions**
   - Pull from predictions_enhanced table
   - Auto-calculate staffing needs per station based on predicted orders

**Deliverable:** Station view showing coverage gaps

---

### Phase 3: Constraint Validation
**Effort: 2-3 days**

1. **Real-time conflict detection**
   - Overlap check (same person, overlapping times)
   - Skill mismatch (employee lacks station skill)
   - OT threshold warnings (>40 hrs/week)
   - Rest period violations (min hours between shifts)

2. **Visual feedback**
   - Inline errors when dragging to invalid slot
   - Warning badges on shifts with issues
   - Summary panel showing all conflicts

3. **Block invalid saves**
   - Backend validation matches frontend
   - Return specific error messages

**Deliverable:** Cannot assign invalid schedules

---

### Phase 4: Drag-and-Drop UI
**Effort: 3-4 days**

1. **Shift cards as draggable elements**
   - Show employee name, time, station
   - Visual feedback during drag

2. **Drop zones**
   - Day columns accept drops
   - Station rows accept drops (station view)
   - Validate on drop, reject if conflict

3. **Quick actions**
   - Double-click to edit shift details
   - Right-click context menu (copy, delete, swap)

4. **Multi-select operations**
   - Shift+click to select multiple
   - Bulk delete/move/copy

**Deliverable:** Intuitive drag-and-drop scheduling

---

### Phase 5: Auto-Scheduler (AI)
**Effort: 4-5 days**

1. **Basic auto-assign algorithm**
   - Input: Available employees, required shifts, skills
   - Output: Suggested assignments
   - Logic: Match skills, balance hours, minimize OT

2. **Productivity-aware recommendations**
   - Pull from daily_scores for each employee
   - Assign high performers to high-demand days
   - Flag underperformers for training stations

3. **One-click scheduling**
   - "Auto-fill week" button
   - Preview before applying
   - Manual override capability

4. **Optimization goals**
   - Minimize overtime costs
   - Maximize skill utilization
   - Balance workload across employees

**Deliverable:** AI suggests complete weekly schedule

---

### Phase 6: Employee Self-Service
**Effort: 2-3 days**

1. **View personal schedule**
   - Calendar in employee portal
   - Upcoming shifts list
   - Push/email notifications for changes

2. **Availability management**
   - Mark days as unavailable
   - Set recurring availability patterns
   - Request time off (already implemented)

3. **Shift swap workflow**
   - Employee initiates swap request
   - Notifies eligible coworkers
   - Manager approval for final confirmation

**Deliverable:** Employees manage own availability

---

### Phase 7: Shift Templates
**Effort: 2 days**

1. **Pre-built templates**
   - 2-2-3 Panama (4-team, 12-hour, 28-day cycle)
   - Standard 5-day (Mon-Fri, 8-hour)
   - Custom builder

2. **Apply template**
   - Select template + date range
   - Preview generated shifts
   - Assign teams to rotation groups

3. **Template management**
   - Save custom patterns
   - Clone and modify existing

**Deliverable:** One-click multi-week schedule generation

---

### Phase 8: Analytics & Reporting
**Effort: 2-3 days**

1. **Coverage reports**
   - Weekly coverage vs. demand
   - Understaffing frequency by station

2. **Cost analysis**
   - Labor cost by schedule
   - OT cost trends
   - Cost per item produced

3. **Performance correlation**
   - Productivity by schedule pattern
   - Best-performing team compositions

**Deliverable:** Management insights dashboard

---

## Technical Stack Decisions

### Frontend Framework
**Decision:** Keep vanilla JS (per architecture decision 251212-2345)
- Extract into modules using ES6 imports
- Use Web Components for reusable UI elements
- Add FullCalendar.js for professional calendar

### Drag-and-Drop Library
**Options:**
1. **SortableJS** - Lightweight, vanilla JS compatible
2. **FullCalendar** - Built-in drag-drop for scheduling
3. **Custom** - More control, more work

**Recommendation:** FullCalendar + SortableJS for non-calendar areas

### State Management
- LocalStorage for draft schedules
- Optimistic updates to API
- Conflict resolution on save

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Large rewrite scope | Phase incrementally, maintain working state |
| Performance with many employees | Pagination, virtual scrolling |
| Complex constraint logic | Comprehensive test suite |
| User adoption | Gradual rollout, training docs |

---

## Success Metrics

1. **Schedule Creation Time:** <10 min for weekly schedule (vs. current manual)
2. **Coverage Accuracy:** 95% shifts filled before week starts
3. **Conflict Rate:** <2% invalid assignments
4. **User Satisfaction:** Positive feedback from managers
5. **OT Reduction:** 20% decrease in unplanned overtime

---

## Immediate Next Steps

1. [ ] Register `intelligent_schedule.py` in app.py
2. [ ] Create database migration for new tables
3. [ ] Build minimal CRUD API for schedules
4. [ ] Refactor frontend to call real API
5. [ ] Add basic drag-and-drop with SortableJS

---

## Appendix: Market Research Source

See: `plans/reports/researcher-251213-scheduling-market-analysis.md`

Key insights:
- Shiftboard: 88% higher shift coverage, 23% OT cost reduction
- Manufacturing requires: skill-based assignment, station awareness
- Mobile-first for employee self-service
- Real-time conflict detection essential
