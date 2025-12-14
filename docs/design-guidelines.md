# Design Guidelines - Productivity Tracker System

## Overview
Design system for the PodFactory Command Center / Productivity Tracker System. Dark cyberpunk aesthetic with neon accents.

---

## Color Palette

### Primary Colors
| Name | Value | Usage |
|------|-------|-------|
| Neon Cyan | `#00f5ff` | Primary accent, active states, links |
| Neon Pink | `#ff00ff` | Secondary accent, gradients |
| Neon Green | `#39ff14` / `#22c55e` | Success states, positive metrics |
| Neon Orange | `#ff6600` | Warnings, attention items |
| Neon Red | `#ff0044` / `#ef4444` | Errors, destructive actions |
| Neon Yellow | `#ffff00` / `#fbbf24` | Caution, pending states |

### Background Colors
| Name | Value | Usage |
|------|-------|-------|
| Cyber BG | `#0a0a0f` | Main background |
| Cyber Panel | `rgba(10, 10, 20, 0.85)` | Card backgrounds |
| Cyber Surface | `rgba(20, 20, 35, 0.7)` | Elevated surfaces |
| Panel Hover | `rgba(15, 15, 30, 0.95)` | Hover states |

### Text Colors
| Name | Value | Usage |
|------|-------|-------|
| Primary Text | `#e0e0e0` | Body text |
| Dim Text | `#606080` | Secondary text |
| Muted Text | `#404060` | Disabled/placeholder |
| Cyan Text | `#00f5ff` | Accent text |

### Glow Effects
```css
--glow-cyan: rgba(0, 245, 255, 0.5);
--glow-pink: rgba(255, 0, 255, 0.5);
--glow-green: rgba(57, 255, 20, 0.5);
--glow-orange: rgba(255, 102, 0, 0.5);
```

---

## Typography

### Font Families
- **Headers/Labels**: `'Orbitron', sans-serif` - Futuristic, geometric
- **Body/UI**: `'Rajdhani', sans-serif` - Clean, readable

### Font Sizes
| Element | Size | Weight | Tracking |
|---------|------|--------|----------|
| H1 | 1.5em+ | 700-800 | 2-3px |
| Section Title | 1.3em | 600-700 | 2px |
| Card Title | 12px | 600 | 2px |
| Body | 14px | 400-500 | 0.5px |
| Labels | 10-11px | 500-600 | 1-2px |
| Small/Meta | 0.8em | 400 | 1px |

### Text Styling
- Headers: Gradient text (`background-clip: text`)
- Labels: UPPERCASE with letter-spacing
- Numeric Values: Orbitron font with glow

---

## Spacing System

### Base Unit: 4px
| Token | Value | Usage |
|-------|-------|-------|
| xs | 4px | Tight gaps |
| sm | 8px | Inner padding |
| md | 12px | Standard padding |
| lg | 16px | Section gaps |
| xl | 20px | Card padding |
| 2xl | 30px | Section margins |

### Layout Grid
- Cards: `grid-template-columns: repeat(auto-fit, minmax(240px, 1fr))`
- Gap: 15-20px
- Max content width: 1400px

---

## Components

### Buttons

#### Primary Button
```css
.btn-action.btn-primary {
    background: var(--neon-cyan);
    color: var(--cyber-bg);
    border: 1px solid var(--neon-cyan);
    padding: 8px 16px;
    font-family: 'Orbitron', sans-serif;
    font-size: 11px;
    letter-spacing: 1px;
    border-radius: 8px;
}
/* Hover: box-shadow glow effect */
```

#### Secondary Button
```css
.btn-action.btn-secondary {
    background: rgba(255,255,255,0.1);
    color: #e0e0e0;
    border: 1px solid rgba(255,255,255,0.2);
}
/* Hover: border-color cyan, text cyan */
```

#### Destructive Button
```css
.btn-destructive {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
}
```

### Form Inputs

```css
input, select {
    background: rgba(255,255,255,0.1);
    color: #e0e0e0;
    border: 1px solid rgba(255,255,255,0.2);
    border-radius: 8px;
    padding: 10px;
    font-size: 14px;
}

input:focus, select:focus {
    border-color: var(--neon-cyan);
    box-shadow: 0 0 15px rgba(0, 245, 255, 0.3);
    outline: none;
}
```

### Cards (Metric Card)
- Background: `var(--cyber-panel)`
- Border: `1px solid var(--cyber-border)`
- Corner accents: Diagonal clip-path + corner glow
- Hover: Lift (translateY -5px) + border glow

### Modals

```css
.modal-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.85);
    backdrop-filter: blur(4px);
    z-index: 10001;
}

.modal-content {
    background: linear-gradient(180deg, rgba(20, 20, 35, 0.98) 0%, rgba(10, 10, 20, 0.98) 100%);
    border: 1px solid rgba(0, 245, 255, 0.2);
    border-radius: 12px;
    max-width: 600px;
    margin: 50px auto;
    box-shadow: 0 0 50px rgba(0, 245, 255, 0.1);
}

.modal-header {
    padding: 20px;
    border-bottom: 1px solid rgba(255,255,255,0.1);
    display: flex;
    justify-content: space-between;
    align-items: center;
}

.modal-body {
    padding: 20px;
}

.modal-footer {
    padding: 15px 20px;
    border-top: 1px solid rgba(255,255,255,0.1);
    display: flex;
    justify-content: flex-end;
    gap: 10px;
}
```

### Tables
- Header: `background: rgba(0, 245, 255, 0.05)`
- Header text: `color: var(--neon-cyan)`, UPPERCASE
- Row border: `1px solid rgba(0, 245, 255, 0.05)`
- Row hover: `background: rgba(0, 245, 255, 0.03)`

### Status Badges
```css
/* Active/Success */
.badge-success {
    background: rgba(34, 197, 94, 0.15);
    color: #22c55e;
    border: 1px solid rgba(34, 197, 94, 0.3);
}

/* Warning/Pending */
.badge-warning {
    background: rgba(251, 191, 36, 0.15);
    color: #fbbf24;
    border: 1px solid rgba(251, 191, 36, 0.3);
}

/* Error/Suspended */
.badge-error {
    background: rgba(239, 68, 68, 0.15);
    color: #ef4444;
    border: 1px solid rgba(239, 68, 68, 0.3);
}

/* Info/Archived */
.badge-info {
    background: rgba(168, 85, 247, 0.15);
    color: #a855f7;
    border: 1px solid rgba(168, 85, 247, 0.3);
}
```

---

## Animations

### Transitions
- Default: `all 0.3s ease`
- Fast: `all 0.15s ease`
- Slow: `all 0.5s ease`

### Hover Effects
1. **Scan line sweep**: Linear gradient moves left to right
2. **Glow increase**: Box-shadow intensifies
3. **Lift**: `transform: translateY(-5px)`

### Status Pulse
```css
@keyframes pulse {
    0%, 100% { opacity: 1; box-shadow: 0 0 10px currentColor; }
    50% { opacity: 0.5; box-shadow: 0 0 5px currentColor; }
}
```

---

## Responsive Breakpoints

| Name | Min Width | Usage |
|------|-----------|-------|
| Mobile | 320px | Base styles |
| Tablet | 768px | Two-column layouts |
| Desktop | 1024px | Full dashboard |
| Wide | 1400px | Max content width |

### Mobile Considerations
- Sidebar: Collapsible with hamburger menu
- Tables: Horizontal scroll
- Cards: Stack vertically
- Touch targets: Min 44x44px

---

## Accessibility

### Color Contrast
- Ensure 4.5:1 ratio for body text
- Large text (18px+): 3:1 minimum
- Use glow effects sparingly for decoration

### Focus States
```css
:focus {
    outline: 2px solid var(--neon-cyan);
    outline-offset: 2px;
}
```

### Screen Reader
- Use semantic HTML
- ARIA labels for icon-only buttons
- Role attributes for custom components

---

## Icons
- Library: Font Awesome 6.4.0
- Style: Regular/Solid
- Size: Inherit from parent or 1em
- Color: Match text or accent color

---

## Z-Index Scale
| Layer | Value | Usage |
|-------|-------|-------|
| Base | 0 | Content |
| Dropdown | 100 | Menus |
| Sticky | 500 | Headers |
| Sidebar | 1000 | Navigation |
| Modal Overlay | 10001 | Modal backdrop |
| Modal Content | 10002 | Modal body |
| Toast | 10003 | Notifications |

---

## Component Patterns

### Confirmation Dialog Pattern
Used for destructive actions (delete, suspend, archive).

Structure:
1. Warning icon (yellow/red based on severity)
2. Title stating action
3. Description with consequences
4. Checkbox for high-risk actions ("I understand")
5. Cancel (secondary) + Confirm (destructive) buttons

### Bulk Action Bar Pattern
Appears when items are selected.

Structure:
1. Selection count indicator
2. Action buttons (contextual)
3. Clear selection button
4. Sticky at bottom of viewport on mobile

---

*Last Updated: December 2025*
