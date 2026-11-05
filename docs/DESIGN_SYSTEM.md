# DayFrame native design system — 0.5.2

The app identity is DayFrame; the image-generated open-frame D icon and wordmark are defined in BRANDING.md. Current UI references are in screenshots/current/.

Graphite/Cyan is the default theme.

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

Kanban displays a translucent, dashed ghost card in the destination lane as soon as a ticket enters it. The ghost reserves the ticket's resulting position in the current board order; it is temporary and cannot be selected. Drop saves the status immediately with Undo. Leaving, cancellation and same-column drops do not write. Kanban does not use the Map's hold timer or relationship confirmation.

Project colors appear on the project prefix in Kanban ticket keys and matching project folder icons. A lightly tinted prefix chip and colored text identify the project without tinting the ticket body or its identifier suffix. Stable project UUIDs determine hue; Paper uses a darker shade for readable contrast. Names, ticket status and project list order do not affect the color.

Keep lanes at least 180px wide, increasing that minimum to fit headers and a six-character project key/identifier at the current font size. Scroll horizontally in narrow windows. Titles show complete lines within their reserved area and elide the last line; full text stays available on hover.

Calendar clicks edit actual records. Map changes require a 1.5-second target hold, ghost/progress and release confirmation. Line patterns distinguish parentage, dependencies and sequence. Context menus and inspector fields offer alternatives.

Preserve drafts through refresh; navigation uses Save/Discard/Cancel. Timer stays live. Theme changes must not duplicate status widgets.

Appearance/geometry/density/text scale/panel widths are device-local. Project/account entities sync; future repository paths stay device-local. Exact interactions are in CALENDAR_AND_MAP.md.

Settings uses a 168px category menu beside one scrollable page: View, Theme, Local data, Sync or Account. Forms stop at 820px wide. View and Theme have separate Apply actions; switching categories keeps field entries. The selected section survives appearance changes and navigation during the session. Sync shows its unresolved conflict count in the menu. Keep section controls reachable at the minimum window size and 125% text scale.


## Controls and labels

Combo/calendar/spin subcontrols use bundled SVG chevrons and transparent embedded editors. Tab bases must not draw a bright native separator. Fixed-width identifiers and project badges reserve their layout space and elide with full hover text.

Quick Add has title-first capture, preset/context controls, optional detail tabs and a fixed footer with batch capture. Label inputs commit on Enter without submitting the form; removable colored chips wrap in narrow layouts. Bug is red, Feature teal, with stable colors for other presets/custom names. Color accompanies visible text.

Windows captions/text/borders use supported native theme attributes; unsupported platforms retain OS decoration. See QUICK_ADD_AND_LABELS.md.
