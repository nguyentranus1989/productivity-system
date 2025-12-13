# Frontend Architecture

## Current State (Dec 2025)

### Stack
- **Framework**: Vanilla HTML/JS (no build step)
- **CSS**: Bootstrap 5 + custom styles
- **Charts**: Chart.js
- **Backend**: Python Flask API

### File Sizes
| File | Size | Lines | Functions |
|------|------|-------|-----------|
| manager.html | 321KB | 5,814 | ~80 |
| employee.html | ~50KB | - | - |
| shop-floor-display.html | ~30KB | - | - |
| intelligent-schedule.html | ~40KB | - | - |

### Known Issues
- **Monolithic files**: manager.html too large to navigate
- **Duplicate code**: `removeEmployeeFromSchedule()` copied 8 times
- **Global state**: 5+ globals (`dashboardData`, `costData`, etc.)
- **No component reuse**: Same patterns repeated across pages
- **Inline HTML**: Template strings for generation (XSS risk)
- **Inline handlers**: `onclick` everywhere instead of `addEventListener`

---

## Decision: Keep Vanilla HTML/JS

### Why NOT React
| Factor | Assessment |
|--------|------------|
| Team skillset | Backend-focused, learning curve is real cost |
| Migration risk | HIGH - production manufacturing system |
| Build complexity | Adds Node.js, Vite/Webpack, npm dependencies |
| Parallel maintenance | 6+ weeks of two codebases |
| Real-time needs | Polling-based, no WebSocket requirement |
| Bundle size | +40KB gzipped for React alone |
| ROI | Low - current code works, just needs structure |

### When to Reconsider React
1. Team grows with dedicated frontend developers
2. Mobile app with React Native code sharing planned
3. Real-time collaboration features require WebSocket

---

## Modularization Plan

### Phase 1: Extract Shared Utilities
Create `frontend/js/` directory:
```
frontend/js/
├── utils.js          # formatTime, downloadCSV, notifications
├── api-client.js     # Enhanced ProductivityAPI class
└── constants.js      # API endpoints, config
```

### Phase 2: Extract Component Modules
```
frontend/js/components/
├── dashboard.js      # Main dashboard cards
├── bottleneck.js     # Bottleneck analysis
├── cost-analysis.js  # Cost Analysis tab
├── leaderboard.js    # Leaderboard component
└── schedule.js       # Scheduling functions
```

### Phase 3: Template Cleanup
- Move inline HTML to `<template>` tags in HTML
- Replace `onclick` with `addEventListener`
- Extract repeated CSS to `manager.css`

---

## Best Practices Going Forward

1. **New features**: Create separate JS modules
2. **Shared code**: Extract to `frontend/js/utils.js`
3. **Large components**: Max 200 lines per function
4. **State**: Use single state object pattern, not scattered globals
5. **Templates**: Use `<template>` tags, not string concatenation

## File Navigation Tips

### manager.html Key Sections
- Lines 1-100: HTML structure, head
- Lines 100-500: CSS styles
- Lines 500-1000: Main layout HTML
- Lines 1000+: JavaScript functions

### Finding Functions
```bash
# Search for function definitions
grep -n "function " frontend/manager.html | head -50

# Search for specific feature
grep -n "loadCostAnalysis\|costAnalysis" frontend/manager.html
```
