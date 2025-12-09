# Changelog

All notable changes to the Productivity Tracker system.

## [2.1.0] - 2025-12-09

### Added
- **Link to Connecteam Feature**: Smart employee mapping between PodFactory and Connecteam
  - Name similarity algorithm using Dice coefficient on bigrams
  - Three confidence levels with visual indicators:
    - HIGH CONFIDENCE (green): ≥50% similarity
    - POSSIBLE MATCH (yellow): 20-50% similarity
    - BEST AVAILABLE (gray): <20% similarity
  - Always shows best available match even for low-similarity names
  - Manual verification workflow for employee linking

### Changed
- Employee mapping now always displays recommendation regardless of similarity score
- Improved UX with color-coded confidence badges

### Fixed
- `showNotification is not defined` error in `saveSmartMappingConnecteam()` function
  - Replaced with `alert()` for browser compatibility

### Technical Details
- **Modified Files**:
  - `frontend/manager.html`:
    - Lines 3845-3880: Updated `openSmartMapping()` with confidence level logic
    - Lines 3937-3948: Fixed notification calls in `saveSmartMappingConnecteam()`

---

## [2.0.0] - Previous

### Core Features
- Real-time productivity tracking
- Idle detection system
- Gamification (achievements, leaderboards)
- Team metrics aggregation
- Intelligent scheduling
- Connecteam integration (time clock sync)
- PodFactory integration (production data)

### API Endpoints
- `/api/activities` - Activity management
- `/api/dashboard` - Dashboard aggregation
- `/api/connecteam` - Connecteam integration
- `/api/gamification` - Achievements/badges
- `/api/idle` - Idle detection
- `/api/team-metrics` - Team performance
- `/api/trends` - Historical trends
- `/api/schedule` - Scheduling
- `/api/system` - System controls

### Scheduler Jobs
- Activity processing every 10 minutes
- Idle check every 5 minutes
- Daily score finalization at 6 PM Central
- Daily reports at 6:30 PM Central
- Real-time score updates every 5 minutes
- Daily data reset at midnight
