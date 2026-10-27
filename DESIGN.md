---
name: MedEdge AI
description: A two-role clinical administration tool. Dark zinc by default, light on request.
colors:
  bg: "#09090b"
  fg: "#fafafa"
  muted: "#d4d4d8"
  line: "#3f3f46"
  surface: "#18181b"
  pii: "#fda4af"
  ok: "#86efac"
  review: "#fcd34d"
  bg-light: "#f4f4f5"
  fg-light: "#18181b"
  muted-light: "#3f3f46"
  pii-light: "#9f1239"
  ok-light: "#166534"
  review-light: "#92400e"
typography:
  display:
    fontFamily: "Geist, Segoe UI, sans-serif"
    fontSize: "clamp(2.5rem, 5vw, 4.5rem)"
    fontWeight: 500
    lineHeight: 0.95
    letterSpacing: "-0.03em"
  body:
    fontFamily: "Geist, Segoe UI, sans-serif"
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
    letterSpacing: "-0.01em"
  mono:
    fontFamily: "Geist Mono, ui-monospace, monospace"
    fontSize: "12px"
    fontWeight: 400
    lineHeight: 1.45
    letterSpacing: "0"
rounded:
  sm: "12px"
  md: "16px"
  pill: "999px"
spacing:
  sm: "8px"
  md: "16px"
  lg: "24px"
  xl: "48px"
components:
  button-primary:
    backgroundColor: "{colors.fg}"
    textColor: "{colors.bg}"
    rounded: "{rounded.pill}"
    padding: "10px 18px"
    height: "44px"
  button-secondary:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.fg}"
    rounded: "{rounded.pill}"
    padding: "10px 18px"
    height: "44px"
  pane:
    backgroundColor: "{colors.bg}"
    textColor: "{colors.fg}"
    padding: "20px"
---

## Overview

MedEdge is an instrument, not a brochure. The first screen is two choices. After that, one primary action. Color is reserved for hidden personal data, a verified result, and something that still needs a look.

## Colors

Dark is the default because the review happens on a laptop in a dim room. Light mode is one toggle. Zinc carries the chrome. Rose is only for hidden identifiers and errors. Green is only for a verified code. Amber is only for a recorded reading, a fallback assembly, or a dose kept as written.

## Typography

Geist for the interface, Geist Mono for the share code, LOINC badges, and the FHIR document. Headings use a tight tracking of -0.03em and a weight of 500. Body stays at 16px.

## Layout

The start screen is a vertical split, full height, with the action in the lower part of each half. The patient flow is a single column, at most 720px. The doctor workbench is three panes: source, trace, result. Below 1280px the trace becomes a drawer. Below 800px the panes stack.

## Elevation & Depth

One shadow, offset downward, used on the page image and the trace drawer. Panes themselves are separated by a 1px line, not by a second shadow.

## Shapes

The page image and the drawer use 16px corners. Banners use 12px. Buttons and badges are pills.

## Components

Primary buttons are filled with the foreground color. Secondary buttons are outlined. The share code is large mono type. A LOINC badge is green. A medication kept as written is amber. The compliance sentence sits in the footer on every screen.

## Do's and Don'ts

- Do keep one primary action on a step.
- Do say when a value came from a recorded sample or the fallback assembler.
- Don't explain what a lab value means.
- Don't use color for decoration.
- Don't put a diagnosis, a recommendation, or a computed high/low flag on the screen.
