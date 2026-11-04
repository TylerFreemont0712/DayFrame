# DayFrame native design system — 0.5.0

The app identity is DayFrame; the image-generated open-frame D icon and wordmark are defined in BRANDING.md. Existing concept screenshots predate the rename. Theme layouts and 0.4.1 control/label refinements remain the visual baseline.

This replaces earlier expansive-dashboard guidance. Graphite/Cyan remains the selected default.

## Geometry

Normal window 1280×800, minimum 980×640; respect Qt/OS scaling and restore bounds. The 1920×1200 monitor is not the application size.

48px rail, ~34px masthead, ~36px footer, 164px project pane, 280px inspector, 9px margins and ~6px gaps. Home has no contextual pane and uses Tasks/Agenda tabs when narrow. Kanban uses five lanes with horizontal scrolling and 105–120px cards.

Native forms scroll content with a fixed Save/Cancel footer. Keep them inside the screen and retain fields on errors. Plain-text labels and editors.

Calendar: month/Upcoming column and flexible Sunday-first week, sticky header, 48px/hour, 48–96px all-day band. Month caps at 290px and contracts; dates upper right, event marks 3px.

Map: 180×74px cards, nested containers, preserved manual coordinates, optional 220px Unsorted tray.

## Visual profiles

Base 8.5pt text, independent 90–125% scale and Compact/Comfortable padding.

| Profile | Windows / Linux type | Shape and surface |
|---|---|---|
| Graphite/Cyan | Segoe UI / Noto Sans | Slate, cyan, crisp 3px corners |
| Terminal/Amber | Consolas / DejaVu Sans Mono | Near-black olive, amber, square controls, ruled rows |
| Paper/Linen | Trebuchet MS + Georgia headings / Noto Sans + DejaVu Serif | Ivory, green, 8px corners, editorial headings |
| Midnight/Studio | Bahnschrift / DejaVu Sans | Violet, lavender, 11px cards, pill controls |
| System | Paper for light OS scheme, Graphite for dark | Resolved when applied |

Use installed fonts with Qt fallback, no runtime downloads. Theme tokens live in theme.py. Event categories/custom colors remain consistent across views.

## Interaction and scope

QtAwesome icons have names/tooltips. Personal/Team stays upper left. Future Code/Team explain their status.

Calendar clicks edit actual records. Map changes require a 1.5-second target hold, ghost/progress and release confirmation. Line patterns distinguish parentage, dependencies and sequence. Context menus and inspector fields offer alternatives.

Preserve drafts through refresh; navigation uses Save/Discard/Cancel. Timer stays live. Theme changes must not duplicate status widgets.

Appearance/geometry/density/text scale/panel widths are device-local. Project/account entities sync; future repository paths stay device-local. Exact interactions are in CALENDAR_AND_MAP.md.


## 0.4.1 control and label polish

Combo/calendar/spin subcontrols use bundled SVG chevrons and transparent embedded editors. Tab bases must not draw a bright native separator. Fixed-width identifiers and project badges reserve their layout space and elide with full hover text.

Quick Add has title-first capture, preset/context controls, optional detail tabs and a fixed footer with batch capture. Label inputs commit on Enter without submitting the form; removable colored chips wrap in narrow layouts. Bug is red, Feature teal, with stable colors for other presets/custom names. Color accompanies visible text.

Windows captions/text/borders use supported native theme attributes; unsupported platforms retain OS decoration. See QUICK_ADD_AND_LABELS.md.
