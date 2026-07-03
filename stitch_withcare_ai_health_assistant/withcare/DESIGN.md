---
name: WithCare
colors:
  surface: '#f9f9ff'
  surface-dim: '#d8d9e3'
  surface-bright: '#f9f9ff'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f2f3fd'
  surface-container: '#ecedf7'
  surface-container-high: '#e6e8f2'
  surface-container-highest: '#e0e2ec'
  on-surface: '#191c23'
  on-surface-variant: '#414754'
  inverse-surface: '#2d3038'
  inverse-on-surface: '#eff0fa'
  outline: '#727785'
  outline-variant: '#c1c6d6'
  surface-tint: '#005bc0'
  primary: '#005bbf'
  on-primary: '#ffffff'
  primary-container: '#1a73e8'
  on-primary-container: '#ffffff'
  inverse-primary: '#adc7ff'
  secondary: '#575f6b'
  on-secondary: '#ffffff'
  secondary-container: '#dbe3f1'
  on-secondary-container: '#5d6571'
  tertiary: '#9e4300'
  on-tertiary: '#ffffff'
  tertiary-container: '#c55500'
  on-tertiary-container: '#0e0200'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#adc7ff'
  on-primary-fixed: '#001a41'
  on-primary-fixed-variant: '#004493'
  secondary-fixed: '#dbe3f1'
  secondary-fixed-dim: '#bfc7d4'
  on-secondary-fixed: '#141c26'
  on-secondary-fixed-variant: '#3f4752'
  tertiary-fixed: '#ffdbcb'
  tertiary-fixed-dim: '#ffb691'
  on-tertiary-fixed: '#341100'
  on-tertiary-fixed-variant: '#783100'
  background: '#f9f9ff'
  on-background: '#191c23'
  surface-variant: '#e0e2ec'
  google-blue: '#4285F4'
  google-red: '#EA4335'
  google-yellow: '#FBBC04'
  google-green: '#34A853'
  gemini-gradient: 'linear-gradient(90deg, #4285F4 0%, #9B72CB 50%, #D96570 100%)'
  surface-light: '#FFFFFF'
  background-light: '#F8F9FA'
  outline-light: '#DADCE0'
  surface-dark: '#2D2E30'
  background-dark: '#202124'
  outline-dark: '#3C4043'
typography:
  headline-sm:
    fontFamily: Plus Jakarta Sans
    fontSize: 24px
    fontWeight: '500'
    lineHeight: 32px
  title-md:
    fontFamily: Roboto Flex
    fontSize: 16px
    fontWeight: '500'
    lineHeight: 24px
  body-md:
    fontFamily: Roboto Flex
    fontSize: 14px
    fontWeight: '400'
    lineHeight: 20px
  label-lg:
    fontFamily: Plus Jakarta Sans
    fontSize: 14px
    fontWeight: '500'
    lineHeight: 20px
  label-sm:
    fontFamily: Roboto Flex
    fontSize: 12px
    fontWeight: '400'
    lineHeight: 16px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  base: 8px
  card-padding: 1.5rem
  gutter: 2rem
  margin-mobile: 1rem
  sidebar-width: 260px
  sidebar-rail: 80px
  max-content-width: 1440px
---

# Design System: WithCare (Google Material 3)
**Product:** WithCare — an AI healthcare-navigation assistant for India.
**Theme:** Google Material Design 3 (Material You) with a light Gemini touch. Light + Dark.

---

## 1. Visual Theme & Atmosphere

WithCare is a **calm, trustworthy, first-party-Google product** — Material Design 3 (Material You)
with a restrained touch of Gemini. It should feel like Gmail or Google Calendar: spacious, clean,
softly rounded, and confidence-inspiring for people managing family health.

**Key characteristics:**
- Expansive whitespace; a persistent left navigation; white cards on a light-grey canvas.
- Google's four brand colors used **functionally** (status, categories), not decoratively.
- One **Gemini gradient** reserved for the AI identity only (the logo mark + the "spark" star).
- Gentle, purposeful motion — nothing flashy; every animation communicates state or hierarchy.
- Photography/data-forward result cards (facilities, coverage, plans) that feel scannable.

---

## 2. Color Palette & Roles → mapped to M3 color roles

Reference: **M3 Color roles** — https://m3.material.io/styles/color/roles ·
**Color system** — https://m3.material.io/styles/color/system/overview

### Brand / accent
- **Google Blue #1A73E8** → `primary` (buttons, active nav, links). Brand blue **#4285F4** for the logo/icon.
- **Google Red #EA4335** → destructive actions/alerts + the Tasks & Reminders section icon.
- **Google Yellow #FBBC04** → rating stars + the Profiles section icon.
- **Google Green #34A853** → success / "Connected" / "Upcoming" + the Workout & Diet section icon.
- **Light blue tint #E8F0FE** → `secondaryContainer` (selected/active pill states).
- **Gemini gradient** `#4285F4 → #9B72CB → #D96570` → **only** the logo mark and the AI spark/star.

### Neutrals — Light theme
- Page background `#F8F9FA` · `surface`/cards `#FFFFFF` · `surfaceContainer` (hover/tint) `#F1F3F4`
- `outline`/dividers `#DADCE0` · text `#202124` (`onSurface`) · secondary text `#5F6368` (`onSurfaceVariant`)

### Neutrals — Dark theme
- Page background `#202124` · cards/`surface` `#2D2E30` · container `#35363A`
- `outline` `#3C4043` · text `#E8EAED` · secondary text `#9AA0A6`

### Functional states
- Success/positive → Google Green `#34A853`
- Error/destructive → Google Red `#EA4335`
- Informational → Google Blue `#1A73E8`

---

## 3. Typography Rules → M3 type scale

Reference: **M3 Typography** — https://m3.material.io/styles/typography/overview ·
**Type scale tokens** — https://m3.material.io/styles/typography/type-scale-tokens

- **Google Sans / Product Sans** → `Display` & `Headline` (page titles, empty-state greeting) and `Label` (buttons, chips).
- **Roboto / Google Sans Text** → `Title` (card headers) and `Body` (content).

| Role | Font | Size / line-height | Use |
|---|---|---|---|
| Headline Small | Google Sans, 500 | 24 / 32 | Page titles, empty-state greeting |
| Title Medium | Google Sans Text, 500 | 16 / 24 | Card headers |
| Body Medium | Roboto, 400 | 14 / 20 | Content, descriptions |
| Label Large | Google Sans, 500 | 14 / 20 | Buttons, chips, tabs |
| Label Small | Roboto, 400 | 12 / 16 | Meta, timestamps, source chips |

---

## 4. Components (Material 3 widgets — with links + where used)

| M3 component | Link | Where in WithCare |
|---|---|---|
| **Navigation drawer** | https://m3.material.io/components/navigation-drawer/overview | Left sidebar (Chat, Tasks, Plans, Profiles, Connectors, Settings). |
| **Navigation rail** | https://m3.material.io/components/navigation-rail/overview | Collapsed sidebar on narrow widths. |
| **Top app bar** (small) | https://m3.material.io/components/top-app-bar/overview | Slim header: page context left; location + Connected chips + theme toggle right. |
| **Common buttons** | https://m3.material.io/components/buttons/overview | Filled (primary CTAs), tonal ("New conversation"), outlined ("Manage"), text. |
| **FAB / Extended FAB** | https://m3.material.io/components/floating-action-button/overview · https://m3.material.io/components/extended-fab/overview | "＋ Create plan" / "＋ New reminder". |
| **Icon buttons** | https://m3.material.io/components/icon-buttons/overview | Card overflow (⋯), edit, theme toggle, send. |
| **Cards** (elevated/filled) | https://m3.material.io/components/cards/overview | Facility, coverage, reminder, appointment, plan, profile, connector cards. |
| **Chips** (assist/filter/input) | https://m3.material.io/components/chips/overview | Suggestion chips, filter chips (Nearest/<5km/<10km), condition chips, location chip, source chips. |
| **Segmented buttons** | https://m3.material.io/components/segmented-buttons/overview | Workout·Diet; All·Appointments·Reminders; Person·Pet toggle. |
| **Tabs** (primary) | https://m3.material.io/components/tabs/overview | Alternative section switcher with a sliding active indicator. |
| **Text fields** | https://m3.material.io/components/text-fields/overview | Chat input, profile form fields. |
| **Search** | https://m3.material.io/components/search/overview | Optional search on Tasks / Profiles. |
| **Lists** | https://m3.material.io/components/lists/overview | Recent conversations; profile-detail sub-lists. Leading icon tiles. |
| **Dialogs** | https://m3.material.io/components/dialogs/overview | Add/Edit profile modal; delete confirmation. |
| **Switch** | https://m3.material.io/components/switch/overview | Pause reminder; Settings notification + AI toggles. |
| **Badges** | https://m3.material.io/components/badges/overview | Status ("Upcoming"), Calendar/Gmail delivery, "Connected". |
| **Progress indicators** | https://m3.material.io/components/progress-indicators/overview | AI "thinking" (indeterminate linear or circular). |
| **Snackbar** | https://m3.material.io/components/snackbar/overview | "Reminder set", "Appointment booked" confirmations. |
| **Menus** | https://m3.material.io/components/menus/overview | Card ⋯ overflow (Edit/Delete/Disconnect). |
| **Tooltips** | https://m3.material.io/components/tooltips/overview | Icon-only controls (collapsed rail, send, theme toggle). |

---

## 5. Motion & Animation (Material 3 — links + exactly where)

References: **Motion overview** — https://m3.material.io/styles/motion/overview ·
**Easing & duration** — https://m3.material.io/styles/motion/easing-and-duration/overview ·
**Transition patterns** — https://m3.material.io/styles/motion/transitions/transition-patterns ·
**Applying transitions** — https://m3.material.io/styles/motion/transitions/applying-transitions ·
**State layers (ripple)** — https://m3.material.io/foundations/interaction/states/overview

Tokens: **Standard easing** for most moves, **Emphasized easing** for larger/expressive ones.
Durations — short (100–200ms) hovers, medium (250–400ms) containers, long (450–500ms) page-level.

| Place | Animation (M3 pattern) | Notes |
|---|---|---|
| Switching main pages (Chat↔Tasks↔Plans…) | **Fade through** — https://m3.material.io/styles/motion/transitions/transition-patterns#fade-through | ~300ms emphasized; content fades/scales slightly. |
| Profile card → profile **detail** | **Container transform** — https://m3.material.io/styles/motion/transitions/transition-patterns#container-transform | The card morphs into the detail page — signature M3 move. |
| Add/Edit **profile modal** open/close | Dialog scale + fade (emphasized decelerate/accelerate) | ~250ms; scrim fades in. |
| **Plan card** expand/collapse (Day 1–7) | Height + fade, **emphasized** easing | Chevron rotates; content reveals. |
| **Sidebar** collapse ↔ rail | Width + label fade, standard easing | ~250ms. |
| **Card hover** (facility/plan/profile) | Elevation lift +1–2 dp + subtle translateY(-2px) | ~150ms standard. |
| Every button/chip/list press | **Ripple / state layer** | On-color overlay; visible keyboard focus ring. |
| **Tabs / segmented** selection | Sliding active **indicator** + state layer | ~200ms; indicator slides between items. |
| Assistant **message appears** | Fade-in + slide-up (short→medium) | Each message enters from ~8px below. |
| AI **thinking / streaming** | Indeterminate **progress** + Gemini-gradient shimmer on the spark; "3 specialists consulted" dots pulse | Loop until response. |
| **Send** button press | Micro press-scale (0.96) + ripple | Reinforces action. |
| Confirmations (booked/reminded) | **Snackbar** slide-up from bottom | Auto-dismiss ~4s. |
| Empty-state **spark** | Slow gradient shimmer / gentle scale-breathe | Subtle, ambient. |
| **Theme toggle** (light↔dark) | Cross-fade of surface colors (short) | Smooth, not jarring. |

---

## 6. Layout Principles

References: **M3 Layout** — https://m3.material.io/foundations/layout/understanding-layout/overview ·
**Window size classes** — https://m3.material.io/foundations/layout/applying-layout/window-size-classes

- Sidebar ~260px (rail 80px). Max content width ~1440px; content in a 12-col grid, 24–32px gutters.
- **8px base unit**; 16–24px card padding; 24–32px between cards; 48px between major sections.
- Window size classes: Compact (drawer overlay), Medium (rail), Expanded (full drawer + multi-column;
  profiles grid 3–4 cols, plans 1–2 cols).
- Touch targets ≥ 48×48px; visible focus states everywhere; WCAG AA contrast in both themes.

---

## 7. Per-Page Component & Motion Map

- **Chat** — Nav drawer + Top app bar; empty state (Headline + assist **chips** + gradient spark);
  conversation (user bubbles; assistant answers with facility/coverage/confirmation **cards**, filter
  **chips**, **progress** while thinking); bottom **text field** + filled **icon button** send.
  *Motion:* message fade-slide-up, thinking shimmer, send press-scale, snackbar on booking.
- **Tasks & Reminders** — **Segmented buttons** tabs; reminder/appointment **cards** with **badges**,
  **switch**, **menu**; **extended FAB** "New reminder".
  *Motion:* card hover-lift, switch toggle, menu fade, snackbar.
- **Workout & Diet** — **Segmented** Workout/Diet; person **chips**; expandable plan **cards** (Day 1–7).
  *Motion:* expand/collapse (emphasized), hover-lift, FAB.
- **Profiles** — profile **cards** grid + dashed "Add" card; **dialog** modal (**segmented** Person/Pet).
  *Motion:* **container transform** to detail; dialog scale-fade; card hover-lift.
- **Connectors** — connector **cards** with logos, "Connected" **badge**, scope **chips**, **menu**.
  *Motion:* connect toggles, hover-lift.
- **Settings** — **list** section nav + grouped **cards**; **switches**, outlined-red destructive **button**.
  *Motion:* section fade-through, switch toggles, confirm dialog.

---

## 8. Notes for Generation (Stitch / Claude / Figma)

- Name components by their M3 role: "a Material 3 **navigation drawer**", "an **elevated card** with a
  state-layer ripple", "a **segmented button** group", "an **extended FAB**".
- Name motion by M3 pattern: "use a **container transform** when opening a profile", "**fade through**
  between pages", "**emphasized** easing on the plan-card expand".
- Iterate one surface at a time (e.g., "refine only the Tasks page cards"), keep the Google palette +
  M3 tokens consistent, and always request **both Light and Dark**.
- Reserve the Gemini gradient strictly for the logo and the AI spark; everything else uses Google Blue
  plus the functional red/yellow/green accents.
