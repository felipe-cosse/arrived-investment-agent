---
name: Arrived Agent Identity
colors:
  primary: "#111827"
  secondary: "#4B5563"
  accent: "#2563EB"
  success: "#10B981"
  background: "#F9FAFB"
  surface: "#FFFFFF"
typography:
  h1:
    fontFamily: Inter, sans-serif
    fontSize: 2.25rem
  h2:
    fontFamily: Inter, sans-serif
    fontSize: 1.5rem
  body:
    fontFamily: Inter, sans-serif
    fontSize: 1rem
  label:
    fontFamily: Inter, sans-serif
    fontSize: 0.875rem
rounded:
  sm: 4px
  md: 8px
  lg: 12px
spacing:
  sm: 8px
  md: 16px
  lg: 24px
  xl: 32px
components:
  card:
    backgroundColor: "{colors.surface}"
    rounded: "{rounded.lg}"
    padding: "{spacing.lg}"
  button-primary:
    backgroundColor: "{colors.accent}"
    textColor: "#FFFFFF"
    rounded: "{rounded.md}"
    padding: "{spacing.sm} {spacing.md}"
---

## Overview

The Arrived Investment Agent visual identity emphasizes trust, clarity, and modern financial tooling. Modeled after premium fractional real-estate platforms, the design language uses high-contrast typography for readability of financial data, cool neutral backgrounds to make property images pop, and a strong dependable blue for primary interactions.

## Colors

- **Primary (#111827):** Deep slate for high-visibility text and main headings.
- **Secondary (#4B5563):** Mid-gray for secondary text, metadata, and labels.
- **Accent (#2563EB):** Trustworthy blue used for primary actions, active states, and links.
- **Success (#10B981):** Emerald green used to denote positive returns, dividend yields, and successful operations.
- **Background (#F9FAFB) & Surface (#FFFFFF):** Clean, spacious foundational colors that separate content panes (like the chat panel vs the data explorer).

## Typography

The application uses **Inter** (or a similar clean sans-serif) across all UI elements to ensure crisp rendering of complex financial figures and data tables.
- Use `h1` and `h2` for structural hierarchy (e.g., property titles, plan summaries).
- `body` is the standard reading size for chat messages and descriptions.
- `label` is used for metadata, data table headers, and small tags.

## Layout

The core layout is a two-pane responsive structure:
- **Chat Panel (Left):** Fixed width on desktop, containing the AI conversation.
- **Data Panel (Right):** Fluid width, housing property cards, charts, and investment plans.
- **Mobile:** Stacks below the `md` breakpoint, with the data panel accessible below the chat.

Padding uses the defined spacing scale to maintain rhythm and breathing room around complex data.

## Elevation & Depth

Surfaces like Property Cards and the Chat Panel use subtle drop shadows on the `surface` color to separate them from the `background`. This provides depth without being overly heavy.
- Use standard CSS shadows (e.g., Tailwind's `shadow-sm`, `shadow-md`) to lift interactive or focused elements.

## Shapes

Corners are softly rounded to appear friendly yet professional.
- Use `rounded.lg` (12px) for large containers like property cards and charts.
- Use `rounded.md` (8px) for buttons, inputs, and interactive elements.
- Use `rounded.sm` (4px) for small tags or badges (e.g. funding progress indicators).

## Components

- **Property Card:** The primary container for an offering. Must use the `card` token values for a clean, unified look. Includes a property image, title, and key financial metrics.
- **Primary Button:** The main call to action (e.g., "Build Plan", "Save Plan"). Uses the `button-primary` token values for high contrast and clickability.
- **Charts:** (Recharts) Should utilize the `accent` and `success` colors for data visualization to maintain theme consistency.

## Do's and Don'ts

- **Do** use the `success` color to highlight positive yields and appreciation.
- **Do** ensure high contrast for all financial numbers.
- **Don't** use overly bright or playful colors that detract from the professional financial context.
- **Don't** clutter the layout; rely on the defined spacing scale to separate distinct data points.
