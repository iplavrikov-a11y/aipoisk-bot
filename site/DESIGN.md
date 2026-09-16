# TenderLex Design System & Visual Specification (DESIGN.md)

## Aesthetic Identity & Tone
- **Archetype**: Refined B2B SaaS Luxury & High-Tech Utility
- **Primary Objective**: Establish immediate authority for procurement managers and B2B suppliers. Avoid generic "AI slop" or template aesthetics.
- **Key Characteristics**: Distinctive display typography, atmospheric teal/navy depth, glassmorphism header & cards, crisp micro-interactions, bold numerical proofs.

## Typography System
- **Display / Heading**: `Plus Jakarta Sans` (Google Fonts: `font-family: var(--font-heading)`). Used for `h1-h6`, brand logo, hero stats, and price badges.
- **Body & Controls**: `Inter` (Google Fonts: `font-family: var(--font-body)`). Used for paragraph copy, forms, table data, and footer links.

## Color Palette (HSL & Theme Tokens)
- **Background**: `#f6f8f7` (Crisp neutral light)
- **Paper / Cards**: `#ffffff` (Pure white surface)
- **Surface Soft**: `#eef3f2` (Light teal tint)
- **Accent Primary**: `#075b63` (Deep Teal B2B Authority)
- **Accent Soft**: `#e5f4f3` (Subtle teal highlight)
- **Navy Depth**: `#07343a` (Rich dark contrast)
- **Success / Badge**: `#5b8f13` (Muted emerald green)

## Components & Spatial Composition
- **Glassmorphism Header**: `background: rgba(255, 255, 255, 0.88)`, `backdrop-filter: blur(16px)`, `border-bottom: 1px solid rgba(216, 227, 225, 0.8)`.
- **Hero Badge**: Floating pill with glowing pulse dot (`bg-teal-50 border-teal-200 text-teal-800`).
- **Feature & Scenario Cards**: Rounded corners `12px`, subtle border `1px solid var(--line)`, shadow `0 12px 32px -4px rgba(7, 91, 99, 0.08)`.
- **Card Micro-interactions**: Hover scale `translateY(-3px)`, transition `200ms ease`, shadow glow `0 24px 60px rgba(7, 91, 99, 0.14)`.

## Micro-animations & Motion
- **Pulse Indicator**: `animate-pulse` on active live badges.
- **Accordion FAQ**: Smooth `rotate-180` transform on summary toggle.
- **Button Hover**: Soft opacity shift with arrow translateX(3px) on hover.
