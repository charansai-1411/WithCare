---
name: WithCare System
colors:
  surface: '#f8f9fa'
  surface-dim: '#d9dadb'
  surface-bright: '#f8f9fa'
  surface-container-lowest: '#ffffff'
  surface-container-low: '#f3f4f5'
  surface-container: '#edeeef'
  surface-container-high: '#e7e8e9'
  surface-container-highest: '#e1e3e4'
  on-surface: '#191c1d'
  on-surface-variant: '#414754'
  inverse-surface: '#2e3132'
  inverse-on-surface: '#f0f1f2'
  outline: '#727785'
  outline-variant: '#c1c6d6'
  surface-tint: '#005bc0'
  primary: '#005bbf'
  on-primary: '#ffffff'
  primary-container: '#1a73e8'
  on-primary-container: '#ffffff'
  inverse-primary: '#adc7ff'
  secondary: '#734ba1'
  on-secondary: '#ffffff'
  secondary-container: '#cca0fe'
  on-secondary-container: '#583186'
  tertiary: '#a23b47'
  on-tertiary: '#ffffff'
  tertiary-container: '#c1535e'
  on-tertiary-container: '#ffffff'
  error: '#ba1a1a'
  on-error: '#ffffff'
  error-container: '#ffdad6'
  on-error-container: '#93000a'
  primary-fixed: '#d8e2ff'
  primary-fixed-dim: '#adc7ff'
  on-primary-fixed: '#001a41'
  on-primary-fixed-variant: '#004493'
  secondary-fixed: '#efdbff'
  secondary-fixed-dim: '#dab9ff'
  on-secondary-fixed: '#2a0053'
  on-secondary-fixed-variant: '#5a3287'
  tertiary-fixed: '#ffdadb'
  tertiary-fixed-dim: '#ffb2b6'
  on-tertiary-fixed: '#40000d'
  on-tertiary-fixed-variant: '#832331'
  background: '#f8f9fa'
  on-background: '#191c1d'
  surface-variant: '#e1e3e4'
typography:
  display-lg:
    fontFamily: plusJakartaSans
    fontSize: 44px
    fontWeight: '700'
    lineHeight: 52px
    letterSpacing: -0.02em
  headline-lg:
    fontFamily: plusJakartaSans
    fontSize: 32px
    fontWeight: '600'
    lineHeight: 40px
  headline-lg-mobile:
    fontFamily: plusJakartaSans
    fontSize: 28px
    fontWeight: '600'
    lineHeight: 36px
  title-lg:
    fontFamily: plusJakartaSans
    fontSize: 22px
    fontWeight: '500'
    lineHeight: 28px
  body-lg:
    fontFamily: inter
    fontSize: 18px
    fontWeight: '400'
    lineHeight: 28px
  body-md:
    fontFamily: inter
    fontSize: 16px
    fontWeight: '400'
    lineHeight: 24px
  label-md:
    fontFamily: inter
    fontSize: 14px
    fontWeight: '600'
    lineHeight: 20px
    letterSpacing: 0.1px
  button-text:
    fontFamily: plusJakartaSans
    fontSize: 16px
    fontWeight: '600'
    lineHeight: 20px
rounded:
  sm: 0.25rem
  DEFAULT: 0.5rem
  md: 0.75rem
  lg: 1rem
  xl: 1.5rem
  full: 9999px
spacing:
  unit: 8px
  container-margin-mobile: 16px
  container-margin-desktop: 24px
  gutter: 16px
  sidebar-width: 280px
---

## Brand & Style
The design system is a fusion of established medical reliability and cutting-edge AI assistance. It leverages the "Material You" (MD3) philosophy—prioritizing clarity, personalization, and adaptive surfaces—interwoven with the ethereal, fluid aesthetics of the Gemini AI identity. 

The visual language is **Clean, Airy, and Optimistic**. It avoids the clinical coldness of traditional healthcare apps by using soft geometry and a signature "Intelligence Gradient." The goal is to make healthcare navigation feel less like a chore and more like a supportive, high-tech conversation. The interface feels "alive" through subtle motion and the strategic use of the Gemini-inspired spectrum.

## Colors
The palette is rooted in Google’s signature palette but elevated with an AI-specific accent.

- **Foundational Surfaces**: Use `#F8F9FA` for the background canvas to create separation. Content resides on pure `#FFFFFF` cards.
- **The Intelligence Gradient**: This represents the AI assistant. Use it sparingly for high-impact moments: the "Spark" icon, primary action buttons, and active navigation indicators.
- **Functional Blue**: `#1A73E8` remains the anchor for standard interactive elements to maintain a sense of professional healthcare trust.
- **Hierarchy**: Text follows a strict grayscale to ensure legibility against the vibrant accents.

## Typography
The system uses **Plus Jakarta Sans** (as a proxy for Google Sans/Product Sans) for headings and UI controls to provide a modern, friendly, and geometric feel. **Inter** (as a proxy for Google Sans Text/Roboto) is used for body content and data-heavy layouts to ensure maximum legibility and systematic performance.

- **Line Height**: Generous spacing is applied to body text to reduce cognitive load during medical reading.
- **Optical Sizing**: Headlines utilize tighter letter spacing for a punchy, editorial look, while small labels use increased tracking for clarity.

## Layout & Spacing
The system follows an **8px grid** rhythm. 

- **App Shell**: A fixed left vertical sidebar (280px) houses the primary navigation. The main content area uses a fluid grid with a maximum content width of 1200px for readability.
- **Card Spacing**: Elements within cards should use 24px padding (`spacing.unit * 3`) to maintain the "airy" feel.
- **Responsive Behavior**: On mobile, the sidebar transitions to a bottom navigation bar or a modal drawer. Margins shrink to 16px to maximize screen real estate for chat interfaces.

## Elevation & Depth
This design system uses a **Low-Elevation** approach to maintain a modern, flat aesthetic while subtly indicating interactivity.

- **Level 0 (Canvas)**: `#F8F9FA`. No shadow.
- **Level 1 (Cards/Surface)**: `#FFFFFF` with a soft ambient shadow: `0px 1px 3px rgba(60, 64, 67, 0.15)`. 
- **Interaction**: On hover, cards may lift slightly using a `0px 4px 8px rgba(60, 64, 67, 0.10)` shadow to indicate "clickability."
- **Borders**: Use `#E8EAED` 1px solid strokes for all containers and dividers to define structure without adding visual weight.

## Shapes
The shape language is defined by high-radius curves to evoke friendliness and safety.

- **Primary Containers**: Cards and large surface areas use a 24px corner radius.
- **Interactive Elements**: Buttons, text inputs, and chips are fully **Pill-shaped** (fixed 100px or half-height radius) to align with the Gemini/MD3 aesthetic.
- **Selection States**: Active navigation indicators in the sidebar use a "stadium" shape or a pill-shaped background highlight.

## Components
- **Buttons**:
    - **Primary (AI)**: Pill-shaped with the Intelligence Gradient background and white text. Used for "Start Chat" or "Summarize."
    - **Tonal**: Light blue background with `#1A73E8` text. Used for secondary actions.
    - **Outlined**: `#E8EAED` border with `#202124` text.
- **AI Spark**: A consistent iconography element using the gradient, appearing next to AI-generated insights.
- **Chips**: Pill-shaped, used for filtering health records or selecting quick-reply suggestions in the chat.
- **Inputs**: Pill-shaped with a 1px `#E8EAED` border. On focus, the border thickens and changes to `#1A73E8`.
- **Floating Action Button (FAB)**: Large, rounded-square or pill-shaped, reserved for the core "New Chat" or "Emergency Assist" action.
- **Navigation Sidebar**: Top-aligned logo (Gradient), followed by list items with Material Symbols (Rounded) icons. The bottom of the sidebar houses the "Signed-in User" card with a circular avatar and subtle border.