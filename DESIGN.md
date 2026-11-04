---
name: MedEdge AI
description: Readable clinical workspaces with pixel task marks and dated visits.
colors:
  bg: "#f4f4f5"
  fg: "#18181b"
  muted: "#3f3f46"
  line: "#d4d4d8"
  surface: "#ffffff"
  accent: "#2159c2"
  accent-soft: "#eaf0ff"
  pii: "#9f1239"
  ok: "#166534"
  review: "#92400e"
  dark-bg: "#09090b"
  dark-fg: "#fafafa"
  dark-muted: "#d4d4d8"
  dark-line: "#3f3f46"
  dark-surface: "#18181b"
  dark-accent: "#9abbff"
  dark-accent-soft: "#1a2944"
  dark-pii: "#fda4af"
  dark-ok: "#86efac"
  dark-review: "#fcd34d"
typography:
  headline:
    fontFamily: 'Geist, "Noto Sans Bengali", "Segoe UI", sans-serif'
    fontSize: "28px"
    lineHeight: 1.25
    letterSpacing: "-0.025em"
  title:
    fontFamily: 'Geist, "Noto Sans Bengali", "Segoe UI", sans-serif'
    fontSize: "19px"
    fontWeight: 600
  body:
    fontFamily: 'Geist, "Noto Sans Bengali", "Segoe UI", sans-serif'
    fontSize: "16px"
    fontWeight: 400
    lineHeight: 1.5
  label:
    fontFamily: 'Geist, "Noto Sans Bengali", "Segoe UI", sans-serif'
    fontSize: "14px"
  code:
    fontFamily: '"Geist Mono", ui-monospace, monospace'
    fontSize: "2rem"
    letterSpacing: "0.12em"
rounded:
  control: "7px"
  field: "8px"
  panel: "10px"
  status: "5px"
spacing:
  small: "8px"
  control-gap: "12px"
  medium: "16px"
  section: "24px"
  large: "28px"
  main-inset: "32px"
components:
  button-primary:
    backgroundColor: "{colors.fg}"
    textColor: "{colors.bg}"
    rounded: "{rounded.control}"
    padding: "10px 18px"
  button-secondary:
    backgroundColor: "transparent"
    textColor: "{colors.fg}"
    rounded: "{rounded.control}"
    padding: "10px 18px"
  input:
    backgroundColor: "{colors.surface}"
    textColor: "{colors.fg}"
    rounded: "{rounded.field}"
    padding: "10px 12px"
  status:
    rounded: "{rounded.status}"
    padding: "4px 7px"
---

# Design System: MedEdge AI

## Overview

**Creative North Star: "One consultation, one place"**

MedEdge uses restrained clinical typography, zinc surfaces and supplied pixel illustrations. Pixel heart, stethoscope and category marks identify workspaces and tasks; conventional text and forms carry clinical evidence. The care shell gives desktop navigation its own narrow rail and keeps the active task in one main column.

The hierarchy follows a short patient overview into dated visits and then into one report, prescription or note. Rules and whitespace separate content. Review detail expands where needed; the overview stays concise. Preserve the footer, account controls and both themes.

**Key Characteristics:**

- Pixel identity with readable English and Bengali clinical text.
- Flat zinc surfaces, restrained blue selection and semantic review colors.
- One patient or visit heading and a clear next action.
- Source evidence close to editable clinical content.

## Colors

The palette is neutral first. Frontmatter records light and dark values; CSS custom properties switch together with the theme.

### Primary

- **Clinical Blue** (`accent`, `dark-accent`): source links and selected document controls; the soft companion supplies selected backgrounds.

### Secondary

- **Review Amber** (`review`, `dark-review`): unfinished review and open visits.
- **Verified Green** (`ok`, `dark-ok`): completed visits and successful review.
- **Privacy Rose** (`pii`, `dark-pii`): hidden identifiers, errors and destructive links.

### Neutral

- **Zinc Canvas** (`bg`, `dark-bg`): application background.
- **Clinical Ink** (`fg`, `dark-fg`): main text and primary action fill; primary labels use canvas color.
- **Supporting Ink** (`muted`, `dark-muted`): descriptions, dates and help text.
- **Zinc Rule** (`line`, `dark-line`): borders and separators.
- **Paper Surface** (`surface`, `dark-surface`): fields, current navigation and notices.

**The Semantic Color Rule.** Status color accompanies explicit text; preserve the same meaning in both themes.

## Typography

**Body and heading font:** Geist with self-hosted Noto Sans Bengali for Bengali glyphs. **Code font:** Geist Mono for connection codes. Pixel imagery supplies the identity; clinical typography stays conventional.

### Hierarchy

- **Headline:** care titles use the frontmatter role, reducing to (25px) on phones. Document titles use (28px) in the care app.
- **Title:** care sections use the frontmatter role; document modules use (20px), with the note module heading at (22px).
- **Body:** clinical narrative uses (16px), leading (1.75), and maximum width (68ch). General body text uses the frontmatter body role.
- **Label:** forms and row metadata use (14px); supporting details use (13px); status markers use (12px).
- **Entry display:** landing choices retain a larger responsive heading (`clamp(2.5rem, 5vw, 4.5rem)`, weight 500). Authentication titles use (32px), weight 600.

**The Clinical Text Rule.** Keep medicine names, doses and authored evidence in readable text; pixel marks identify categories rather than replacing text.

## Layout

The centered care shell is at most (1280px) wide with (24px) exterior gutters. Desktop navigation occupies (208px); the main column starts with a (32px) inset. Patient selection is a searchable list page followed by a focused overview and dated visit rows. The rail holds workspace navigation rather than a persistent patient directory.

At (760px) and below, navigation becomes a horizontal row of equal icon-and-label choices with (16px) exterior gutters and (64px) minimum navigation targets. The role banner and signed-in name disappear. Patients have four choices: Home, Visits, Reports and Doctors. Doctors retain their own workspace choices. Preserve content order on phones.

Sections use a (24px–28px) rhythm; related actions use (8px–12px) gaps. Patient and artifact rows use separators instead of individual cards. Report and recording inputs use two columns, collapsing at (760px). Clinical document workspaces retain up to (1200px); existing report review can use its wider document canvas.

When a prescription source exists, source and medication review are adjacent at (1000px) and above with a (24px) gutter and a wider editor column. The source can scroll and zoom. Below (1000px), Source and Review controls switch panes. Medicine fields reflow to two columns on phones; name, instructions and three dose slots span the row. English and Bangla assessment editors sit beside each other on desktop and stack on phones.

## Elevation & Depth

Care navigation, summaries and visit rows are flat. Rules, spacing and background changes express grouping and selection. Existing document sheets and menus use the theme shadow; those shadows do not belong on every content section. The sidecar carries exact values.

**The Flat Visit Rule.** Use separators and spacing for patient and visit lists; reserve contained surfaces for fields, notices or document tools that need them.

## Shapes

Care action and navigation corners are gently squared (7px). Document workspace controls and fields use (8px), existing panels (10px), and visit status markers (5px). Borders are single-pixel zinc rules. Keep supplied SVG pixel artwork crisp. Existing circular account/theme icon controls and rounded document sheets remain local patterns.

## Components

### Buttons

Primary actions use foreground fill and canvas text. Secondary care actions remain transparent; document workspace secondary actions use the surface and line border. Care controls have minimum height (44px). Document controls use compact padding (9px 15px). Global focus uses a foreground outline (2px) offset (3px). Disabled actions retain their label with opacity (0.45).

Base care buttons can lift by (1px) over (180ms); document controls remain in place and change brightness. Reduced motion disables base movement. Do not animate button background colors across a theme switch.

### Status markers

Use a small outlined label with explicit Open or Completed text. Amber and green reinforce the words. On phones, the marker may wrap instead of forcing overflow.

### Cards / Containers

The health narrative is an open text section with a bottom rule. Notices use a surface, line border, (8px) corners and (14px 16px) padding. Existing connection and document panels retain their treatment; embedded chart connections flatten into divided sections.

### Inputs / Fields

Use persistent labels, surface fill, line borders and the field radius. Textareas use comfortable leading (1.7) and vertical resizing. File fields use a dashed boundary. Errors, upload preparation, processing, saved/unsaved status and retries remain visible in their task context.

### Navigation

Desktop rail items use pixel icons, muted text and a transparent background. The current page adds a surface, line border and stronger text; hover adds a surface. Mobile navigation centers the icon above its label. Back links preserve patient or visit context. The patient language control stays near the heading.

### Visit rows and review workspace

Visit rows pair a pixel mark, title, doctor or patient, date and status. Contribution controls and completion checks live inside the consultation. Artifacts use the same divided row treatment; earlier report references are explicitly labeled.

Medication review keeps editable name, strength, form, dose slots, timing and duration. Evidence and registry lookup use disclosures. Confirmed rows can be collapsed and reopened; editing invalidates confirmation. Linked outstanding checks lead to unfinished fields, alongside explicit draft saving and publication. Printed publications retain a bilingual medication table and patient/author/date context.

## Do's and Don'ts

### Do:

- **Do** preserve pixel task marks, Geist, Bengali glyph coverage and both themes.
- **Do** give a patient or visit one main heading and a clear next action.
- **Do** keep source evidence accessible beside or behind the review pane.
- **Do** show status in words with visible focus, processing feedback and retries.
- **Do** keep the short health narrative separate from detailed sources and patient-reported medicines.

### Don't:

- **Don't** restore the old persistent patient directory or Summary/History/Add report tab structure in the care shell.
- **Don't** turn every visit row or narrative into a nested card.
- **Don't** expose raw FHIR bundles or model trace panels in either portal.
- **Don't** replace clinical labels with decorative pixel text or color-only status.
- **Don't** hide the reason publication or visit completion is unavailable.
