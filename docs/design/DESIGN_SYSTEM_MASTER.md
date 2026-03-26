# Inventory Management System (IMS) Design System — Master Structure Guide

This design system is adapted from an HMS-style UI system, but tailored for the Inventory Management System. It outlines the foundational elements, components, and patterns for building consistent, accessible, and professional business interfaces.

---

## Table of Contents

1. [Design Tokens](#design-tokens)
2. [Color System](#color-system)
3. [Typography](#typography)
4. [Spacing & Grid](#spacing--grid)
5. [Iconography](#iconography)
6. [Core Components](#core-components)
7. [Layout Patterns](#layout-patterns)
8. [Best Practices](#best-practices)

---

## Design Tokens

### Technology Stack
- **CSS Framework**: Tailwind CSS (with custom configuration)
- **Font Family**: Manrope / Inter (Google Fonts)
- **Icons**: Material Icons + Material Symbols Outlined
- **Dark Mode**: Class-based toggle

### Tailwind Configuration
```javascript
tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        "primary": "#137fec",
        "background-light": "#f6f7f8",
        "background-dark": "#101922",
        "surface": "#ffffff",
      },
      fontFamily: {
        "display": ["Manrope", "sans-serif"]
      },
      borderRadius: {
        "DEFAULT": "0.25rem",
        "lg": "0.5rem",
        "xl": "0.75rem",
        "full": "9999px"
      },
      spacing: {
        '8px': '8px',
      }
    },
  },
}
```

---

## Color System

### Primary Palette

| Color Name | Hex Code | Usage |
|------------|----------|-------|
| **Medical Blue (Primary)** | `#137fec` | Primary actions, links, active states, branding |
| **Success Green** | `#10b981` | Success states, confirmations, positive metrics |
| **Danger Red** | `#ef4444` | Errors, critical alerts, destructive actions |
| **Warning Amber** | `#f59e0b` | Warnings, pending states, cautions |

### Neutral Scale (Slate)

| Token | Light Mode | Dark Mode | Usage |
|-------|------------|-----------|-------|
| 50 | `#f8fafc` | - | Backgrounds, subtle fills |
| 100 | `#f1f5f9` | - | Card backgrounds, input backgrounds |
| 200 | `#e2e8f0` | - | Borders, dividers |
| 400 | `#94a3b8` | - | Placeholder text, icons |
| 500 | `#64748b` | - | Secondary text |
| 600 | `#475569` | - | Primary text (light) |
| 700 | `#334155` | - | Headings |
| 800 | `#1e293b` | - | Primary text (dark) |
| 900 | `#0f172a` | `#0f172a` | Background (dark mode) |

### Background Colors

| Token | Light Mode | Dark Mode |
|-------|------------|-----------|
| Background | `#f6f7f8` | `#101922` |
| Surface | `#ffffff` | `#1e293b` |

### Status Colors

| Status | Background | Text | Usage |
|--------|------------|------|-------|
| Active | `bg-green-100` | `text-green-700` | Active records, confirmed transactions |
| Pending | `bg-amber-100` | `text-amber-700` | Awaiting action, pending approval |
| Draft | `bg-slate-100` | `text-slate-600` | Draft documents |
| Cancelled | `bg-rose-500` | `text-white` | Cancelled/invalidated documents |

---

## Typography

### Font Family
- **Primary**: `Manrope` (Google Fonts)
- **Fallback**: `Inter`, sans-serif
- **Weights**: 300 (Light), 400 (Regular), 500 (Medium), 600 (Semibold), 700 (Bold)

### Type Scale

| Style | Size | Line Height | Weight | Usage |
|-------|------|-------------|--------|-------|
| **H1** | 32px (2rem) | 40px | 700 (Bold) | Page titles, major headings |
| **H2** | 24px (1.5rem) | 32px | 600 (Semibold) | Section headings |
| **H3** | 20px (1.25rem) | 28px | 600 (Semibold) | Subsection headings, card titles |
| **Body Large** | 16px (1rem) | 24px | 400 (Regular) | Long-form content |
| **Body Default** | 14px (0.875rem) | 20px | 400 (Regular) | General body text |
| **Small** | 12px (0.75rem) | 16px | 400/500 | Captions, metadata, labels |
| **XS** | 10px (0.625rem) | 14px | 500/600 | Badges, tooltips, fine print |

### Text Colors

| Context | Color | Usage |
|---------|-------|-------|
| Primary Text | `text-slate-900` / `text-white` | Headings, important content |
| Secondary Text | `text-slate-600` / `text-slate-400` | Body text, descriptions |
| Muted Text | `text-slate-500` / `text-slate-500` | Metadata, timestamps |
| Disabled Text | `text-slate-400` / `text-slate-600` | Disabled states |

---

## Spacing & Grid

### 8px Base Grid System

All spacing values are multiples of 8px. For fine adjustments, 4px half-steps are permitted.

| Token | Pixel Value | Usage |
|-------|-------------|-------|
| `1` | 4px | Icon spacing, fine adjustments |
| `2` | 8px | Tight spacing, icon padding |
| `3` | 12px | Component internal spacing |
| `4` | 16px | Standard gap between elements |
| `5` | 20px | Section spacing |
| `6` | 24px | Card padding, component gaps |
| `8` | 32px | Section margins |
| `10` | 40px | Large section gaps |
| `12` | 48px | Major layout divisions |
| `16` | 64px | Page-level spacing |

### Layout Grid

- **Desktop**: 12-column grid with 16px gutters
- **Tablet**: 8-column grid
- **Mobile**: 4-column grid
- **Max Content Width**: 1536px (6xl)

### Common Layout Patterns

```html
<!-- Standard Card Grid -->
<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">

<!-- Dashboard KPI Grid -->
<div class="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-6">

<!-- Two-Column Layout -->
<div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
  <div class="lg:col-span-2">Main Content</div>
  <div class="lg:col-span-1">Sidebar</div>
</div>
```

---

## Iconography

### Icon Libraries

1. **Material Icons** (Filled)
   - Usage: Navigation, actions, status indicators
   - Size: `text-xl` (24px), `text-lg` (20px)

2. **Material Symbols Outlined**
   - Usage: Secondary actions, decorative elements
   - Weight range: 100..700

### Icon Sizes

| Context | Size Class | Pixel Value |
|---------|------------|-------------|
| Navigation | `text-[20px]` | 20px |
| Buttons | `text-lg` | 20px |
| Inline | `text-sm` | 16px |
| Status | `text-base` | 18px |
| Hero | `text-3xl` | 48px |

### Common Icons by Category

| Category | Icons |
|----------|-------|
| **Navigation** | `dashboard`, `settings`, `menu`, `close` |
| **Masters** | `group`, `inventory_2`, `local_shipping` |
| **Actions** | `edit`, `visibility`, `delete`, `save` |
| **Status** | `check_circle`, `warning`, `error`, `info` |
| **Finance** | `payments`, `receipt_long`, `request_quote` |
| **Time** | `calendar_today`, `schedule`, `date_range` |

---

## Core Components

### Buttons

#### Primary Button
```html
<button class="bg-primary hover:bg-primary/90 text-white font-bold py-2.5 px-5 rounded-lg shadow-lg shadow-primary/20 transition-all flex items-center justify-center gap-2">
  <span class="material-icons text-lg">save</span>
  Save Changes
</button>
```

| Variant | Classes | Usage |
|---------|---------|-------|
| Primary | `bg-primary hover:bg-primary/90 text-white` | Main actions |
| Secondary | `border border-slate-200 hover:bg-slate-50 text-slate-600` | Secondary actions |
| Ghost | `text-primary hover:bg-primary/5` | Tertiary actions |
| Icon Button | `p-2 hover:bg-slate-100 rounded-full` | Icon-only actions |

#### Button Sizes

| Size | Classes | Usage |
|------|---------|-------|
| Large | `py-3.5 px-6 text-base` | Hero CTAs |
| Default | `py-2.5 px-5 text-sm` | Standard buttons |
| Small | `py-1.5 px-3 text-xs` | Inline actions |

---

### Input Fields & Forms

#### Text Input
```html
<div class="relative">
  <label class="block text-sm font-medium text-slate-700 mb-2">Email</label>
  <div class="relative">
    <span class="material-icons absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">email</span>
    <input class="w-full pl-10 pr-4 py-2.5 bg-slate-50 border border-slate-200 rounded-lg text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none" placeholder="name@company.com"/>
  </div>
</div>
```

#### Select Dropdown
```html
<select class="w-full bg-slate-50 border border-slate-200 rounded-lg px-4 py-2.5 text-sm focus:ring-2 focus:ring-primary/20 focus:border-primary outline-none appearance-none">
  <option>Option 1</option>
</select>
```

#### Form Layout
- Label above input
- 8px gap between label and input
- 16px gap between form fields
- Helper text below input (11px, muted color)

---

### Cards

#### Standard Card
```html
<div class="bg-white dark:bg-slate-900 p-6 rounded-xl border border-slate-200 dark:border-slate-800 shadow-sm">
  <h3 class="font-bold text-slate-900 mb-4">Card Title</h3>
  <p class="text-slate-600 text-sm">Card content goes here.</p>
</div>
```

#### KPI Stat Card
```html
<div class="bg-white p-5 rounded-xl border border-slate-200 shadow-sm">
  <div class="flex items-center justify-between mb-2">
    <span class="text-xs font-bold text-slate-500 uppercase tracking-wider">Today Sales</span>
    <span class="material-icons text-blue-500">receipt_long</span>
  </div>
  <div class="flex items-baseline gap-2">
    <p class="text-2xl font-bold text-slate-900">₹ 0</p>
    <span class="text-[10px] font-bold text-emerald-500">+0.0%</span>
  </div>
</div>
```

| Card Variant | Border Radius | Shadow | Usage |
|--------------|---------------|--------|-------|
| Default | `rounded-xl` | `shadow-sm` | Standard content cards |
| Elevated | `rounded-xl` | `shadow-lg` | Important content |
| Interactive | `rounded-xl` | `shadow-sm hover:shadow-md` | Clickable cards |

---

### Tables

#### Data Table
```html
<div class="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
  <table class="w-full text-left">
    <thead class="bg-slate-50 border-b border-slate-200">
      <tr>
        <th class="px-6 py-4 text-xs font-bold text-slate-500 uppercase tracking-wider">Column</th>
      </tr>
    </thead>
    <tbody class="divide-y divide-slate-100">
      <tr class="hover:bg-slate-50 transition-colors group">
        <td class="px-6 py-4 text-sm">Content</td>
        <td class="px-6 py-4 text-right">
          <div class="flex items-center justify-end gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
            <button class="p-1.5 hover:bg-primary/10 rounded-lg text-primary">
              <span class="material-icons text-lg">visibility</span>
            </button>
          </div>
        </td>
      </tr>
    </tbody>
  </table>
</div>
```

#### Table Specifications

| Element | Specification |
|---------|---------------|
| Header Background | `bg-slate-50` |
| Header Text | `text-xs font-bold text-slate-500 uppercase` |
| Row Padding | `px-6 py-4` |
| Row Hover | `hover:bg-slate-50` |
| Divider | `divide-y divide-slate-100` |
| Actions | Reveal on hover with `opacity-0 group-hover:opacity-100` |

---

### Badges & Status Indicators

#### Status Badge
```html
<span class="px-2.5 py-1 rounded-full text-[11px] font-bold bg-green-100 text-green-700 uppercase tracking-wide">
  Active
</span>
```

| Status | Classes |
|--------|---------|
| Active/Confirmed | `bg-green-100 text-green-700` |
| Pending | `bg-amber-100 text-amber-700` |
| Draft | `bg-slate-100 text-slate-600` |
| Cancelled | `bg-rose-500 text-white` |

---

### Navigation

#### Sidebar Navigation
```html
<aside class="w-64 bg-white border-r border-slate-200 fixed h-full">
  <div class="p-6">
    <!-- Logo -->
    <div class="flex items-center gap-2 mb-8">
      <div class="w-8 h-8 bg-primary rounded flex items-center justify-center">
        <span class="material-icons text-white text-sm">inventory_2</span>
      </div>
      <span class="font-bold text-lg">IMS</span>
    </div>
    
    <!-- Navigation -->
    <nav class="space-y-1">
      <a class="flex items-center gap-3 px-4 py-3 text-sm font-semibold bg-primary/10 text-primary border-r-4 border-primary" href="#">
        <span class="material-icons">dashboard</span>
        Dashboard
      </a>
      <a class="flex items-center gap-3 px-4 py-3 text-sm font-medium text-slate-500 hover:bg-slate-50 hover:text-primary transition-colors" href="#">
        <span class="material-icons">inventory_2</span>
        Products
      </a>
    </nav>
  </div>
</aside>
```

#### Navigation Specifications

| Element | Specification |
|---------|---------------|
| Sidebar Width | 256px (w-64) |
| Item Height | 44-48px |
| Icon Size | 20px |
| Active State | `bg-primary/10 text-primary border-r-4 border-primary` |
| Hover State | `hover:bg-slate-50 hover:text-primary` |

---

### Modals & Drawers

#### Side Drawer
```html
<!-- Backdrop -->
<div class="fixed inset-0 bg-black/40 backdrop-blur-sm z-40"></div>

<!-- Drawer -->
<aside class="fixed right-0 top-0 bottom-0 w-full max-w-[500px] bg-white z-50 shadow-2xl flex flex-col">
  <header class="flex items-center justify-between px-6 py-5 border-b">
    <h2 class="text-xl font-bold">Drawer Title</h2>
    <button class="p-2 hover:bg-slate-100 rounded-full">
      <span class="material-icons">close</span>
    </button>
  </header>
  <form class="flex-1 overflow-y-auto p-6">
    <!-- Content -->
  </form>
  <footer class="p-6 border-t flex gap-4">
    <button class="flex-1 border py-2.5 rounded-lg">Cancel</button>
    <button class="flex-[2] bg-primary text-white py-2.5 rounded-lg">Save</button>
  </footer>
</aside>
```

---

## Layout Patterns

### Dashboard Layout

```
┌─────────────────────────────────────────────────────┐
│  Sidebar (256px)  │  Header (64px)                  │
│                   ├─────────────────────────────────┤
│  - Logo           │  Main Content Area              │
│  - Navigation     │  - KPI Cards (5 columns)        │
│                   │  - Charts (2/3 + 1/3)           │
│                   │  - Data Tables                  │
│                   │  - Side Widgets                 │
└───────────────────┴─────────────────────────────────┘
```

### Page Header Pattern
```html
<header class="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
  <div>
    <h1 class="text-2xl font-bold text-slate-900">Page Title</h1>
    <p class="text-slate-500 text-sm">Brief description</p>
  </div>
  <button class="bg-primary text-white px-5 py-2.5 rounded-lg font-semibold flex items-center gap-2">
    <span class="material-icons">add</span>
    Primary Action
  </button>
</header>
```

### Filter Toolbar Pattern
```html
<div class="bg-white rounded-xl border border-slate-200 p-4 mb-6">
  <div class="grid grid-cols-1 lg:grid-cols-12 gap-4">
    <div class="lg:col-span-4 relative">
      <input class="w-full pl-10 pr-4 py-2 rounded-lg" placeholder="Search..."/>
    </div>
    <div class="lg:col-span-2">
      <select class="w-full py-2 rounded-lg"><option>Filter 1</option></select>
    </div>
    <div class="lg:col-span-2">
      <select class="w-full py-2 rounded-lg"><option>Filter 2</option></select>
    </div>
  </div>
</div>
```

---

## Best Practices

### Accessibility

1. **Color Contrast**: Maintain WCAG AA standards (4.5:1 for text)
2. **Focus States**: All interactive elements must have visible focus rings
3. **ARIA Labels**: Use for icon-only buttons and complex widgets
4. **Keyboard Navigation**: Ensure all components are keyboard accessible

### Responsive Design

| Breakpoint | Width | Layout Changes |
|------------|-------|----------------|
| Mobile | < 768px | Single column, collapsed navigation |
| Tablet | 768px - 1024px | 2-column grids, optional sidebar |
| Desktop | > 1024px | Full layout with sidebar |

### Performance

1. **Icon Loading**: Use Google Fonts CDN with `display=swap`
2. **Image Optimization**: Use WebP format with lazy loading
3. **CSS**: Leverage Tailwind's purge for production builds

### Dark Mode

```html
<!-- Class-based toggle -->
<body class="dark">
  <div class="bg-white dark:bg-slate-900">
    <p class="text-slate-900 dark:text-white">Content</p>
  </div>
</body>
```

### Code Organization

```
project/
├── components/
│   ├── buttons/
│   ├── forms/
│   ├── cards/
│   └── tables/
├── layouts/
│   ├── dashboard/
│   └── auth/
├── styles/
│   └── tailwind.config.js
└── tokens/
    └── colors.json
```

---

## Version Information

- **Current Version**: 1.0.0
- **Last Updated**: March 2026
- **Status**: Stable

---

*Prioritize clarity, accessibility, and efficiency in all implementations.*

