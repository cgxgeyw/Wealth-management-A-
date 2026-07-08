---
name: Institutional Intelligence
colors:
  surface: '#f7f9fb'
  surface-dim: '#d8dadc'
  surface-bright: '#f7f9fb'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f4f6'
  surface-container: '#eceef0'
  surface-container-high: '#e6e8ea'
  surface-container-highest: '#e0e3e5'
  on-surface: '#191c1e'
  on-surface-variant: '#45464d'
  inverse-surface: '#2d3133'
  inverse-on-surface: '#eff1f3'
  outline: '#76777d'
  outline-variant: '#c6c6cd'
  surface-tint: '#565e74'
  primary: '#000000'
  on-primary: '#ffffff'
  primary-container: '#131b2e'
  on-primary-container: '#7c839b'
  inverse-primary: '#bec6e0'
  secondary: '#006c49'
  on-secondary: '#ffffff'
  secondary-container: '#6cf8bb'
  on-secondary-container: '#00714d'
  tertiary: '#000000'
  on-tertiary: '#ffffff'
  tertiary-container: '#410004'
  on-tertiary-container: '#ef4444'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#dae2fd'
  primary-fixed-dim: '#bec6e0'
  on-primary-fixed: '#131b2e'
  on-primary-fixed-variant: '#3f465c'
  secondary-fixed: '#6ffbbe'
  secondary-fixed-dim: '#4edea3'
  on-secondary-fixed: '#002113'
  on-secondary-fixed-variant: '#005236'
  tertiary-fixed: '#ffdad7'
  tertiary-fixed-dim: '#ffb3ad'
  on-tertiary-fixed: '#410004'
  on-tertiary-fixed-variant: '#930013'
  background: '#f7f9fb'
  on-background: '#191c1e'
  surface-variant: '#e0e3e5'
typography:
  display-sm:
    fontFamily: Inter
    fontSize: 24px
    fontWeight: '600'
    lineHeight: 32px
  headline-sm:
    fontFamily: Inter
    fontSize: 18px
    fontWeight: '600'
    lineHeight: 24px
  body-md:
    fontFamily: Inter
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  body-sm:
    fontFamily: Inter
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
  data-mono:
    fontFamily: JetBrains Mono
    fontSize: 12px
    fontWeight: '500'
    lineHeight: 16px
  label-caps:
    fontFamily: Inter
    fontSize: 11px
    fontWeight: '600'
    lineHeight: 12px
    letterSpacing: 0.05em
rounded:
  sm: 0.125rem
  DEFAULT: 0.25rem
  md: 0.375rem
  lg: 0.5rem
  xl: 0.75rem
  full: 9999px
spacing:
  unit: 4px
  container-padding: 16px
  grid-gutter: 12px
  sidebar-width-expanded: 240px
  sidebar-width-collapsed: 64px
  header-height: 56px
---

## Brand & Style
The design system is engineered for the high-velocity, high-stakes environment of A-share market analysis. The personality is institutional, precise, and authoritative. It prioritizes information density over decorative white space, catering to professional traders who require immediate access to multi-dimensional data.

The style is **Corporate / Modern** with a focus on data-heavy utility. It utilizes a restrained color palette and a structured grid to minimize cognitive load. Every pixel is intentional, favoring crisp lines and low-contrast borders over shadows to create a "terminal" feel that remains legible during extended sessions.

## Colors
The palette is rooted in institutional trust and functional clarity. 
- **Primary Backgrounds**: Use `#FFFFFF` for content areas and `#F8FAFC` for page backgrounds and sidebar surfaces to provide subtle depth.
- **Semantic Logic**: In the context of the A-share market, Emerald Green (`#10B981`) denotes positive movement/growth, while Rose Red (`#EF4444`) denotes decline. Amber Yellow (`#F59E0B`) is reserved for warnings or market volatility alerts.
- **Borders**: All structural divisions use `#E2E8F0` to maintain a sharp, technical appearance without distracting the eye.

## Typography
Typography is optimized for maximum data density and legibility of both Latin characters and CJK (Chinese, Japanese, Korean) glyphs.
- **Primary Typeface**: Inter is the default for UI elements, providing a neutral and modern tone.
- **Data Display**: JetBrains Mono is utilized for ticker symbols, price figures, and quantitative tables to ensure vertical alignment of digits.
- **Sizing**: The base body size is 13px/14px. For dense data grids, 12px is the standard to allow for more rows/columns per viewport.
- **Fallback Hierarchy**: For Chinese characters, prioritize `PingFang SC`, followed by `Microsoft YaHei`.

## Layout & Spacing
The layout follows a **Fixed Grid** philosophy to provide a stable environment for financial monitoring.
- **Structure**: A fixed left-hand navigation sidebar (collapsible) and a fixed top utility header.
- **Main Content**: Content is organized into modular "panels" or "widgets." 
- **Spacing Rhythm**: A 4px base unit is used. Standard padding within cards and panels is 12px or 16px to maintain a compact, professional look.
- **Breakpoints**: 
  - Desktop (1440px+): 12-column layout.
  - Tablet (1024px+): 8-column layout, sidebar auto-collapses.
  - Mobile: Not the primary use case; layouts reflow to a single-column scroll with simplified headers.

## Elevation & Depth
This design system avoids traditional drop shadows to maintain a flat, technical aesthetic.
- **Tonal Layers**: Depth is communicated via background color shifts. Level 0 is `#F8FAFC`, Level 1 (Cards/Panels) is `#FFFFFF`.
- **Low-Contrast Outlines**: Every interactive or distinct surface is defined by a 1px solid border (`#E2E8F0`). 
- **Active State**: Active or focused panels may use a subtle primary-colored border (`#0F172A`) or a very soft, 2px ambient glow with 5% opacity.

## Shapes
The shape language is conservative and precise. 
- **Radius**: A consistent 4px radius is applied to buttons, input fields, and panels. This "Soft" (Level 1) approach avoids the clinical harshness of 0px corners while maintaining a professional, data-driven feel.
- **Status Indicators**: Small circular pips (8px x 8px) are used for system status, while rounded-rect "tags" are used for stock labels.

## Components
- **Data Tables**: The core of the system. Use zebra striping (alternate rows with `#F8FAFC`). Headers must be sticky with a 2px bottom border. Hover states should use a subtle `#F1F5F9` highlight.
- **Buttons**: Use "Small" variants (28px - 32px height). Primary buttons are solid `#0F172A`. Secondary/Action buttons are outlined with 1px `#E2E8F0`.
- **Inputs**: Compact heights (32px). Use `JetBrains Mono` for numeric inputs. Borders turn `#0F172A` on focus.
- **Chips/Badges**: Small font-size (11px) with tight padding (2px 6px). Use semantic backgrounds with 10% opacity (e.g., Green text on 10% Green background).
- **Cards/Panels**: Must include a header area with a title and optional "Actions" (refresh, expand, settings). Panels are separated by 12px gutters.
- **Stock Tickers**: Display ticker symbol in bold, price in `data-mono`, and percentage change using semantic colors (Green/Red) with an arrow icon.