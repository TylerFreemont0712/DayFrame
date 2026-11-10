# DayFrame native design system

The app identity is DayFrame; the image-generated open-frame D icon and wordmark are defined in [BRANDING.md](../operations/BRANDING.md). Current UI references are in [docs/screenshots/current/](../screenshots/current/).

Graphite with the Cyan scheme is the default theme.

## Geometry

Normal window 1280×800, minimum 980×640; respect Qt/OS scaling and restore bounds. The 1920×1200 monitor is not the application size.

48px rail, ~34px masthead, ~36px footer, 164px project pane, 280px inspector, 9px margins and ~6px gaps. Home has no contextual pane. From about 1090px of free width it shows tasks, the week strip with Day Agenda, and Coming up side by side; below that Day Agenda and Coming up share tabs; below about 840px it uses Tasks/Week/Coming up tabs. The week strip is 132px tall, 108px in windows shorter than 720px. Kanban uses five lanes with horizontal scrolling and 105–120px cards.

Native forms scroll content with a fixed Save/Cancel footer. Keep them inside the screen and retain fields on errors. Plain-text labels and editors.

Calendar: month/Upcoming column and flexible Sunday-first week, sticky header, 48px/hour. The all-day band sizes its rows from the current font (one text line plus padding), shows up to four rows and turns the fourth into a "+N more" marker per day when more events overlap; hovering it lists the hidden events. Hour labels and the time gutter also follow the font. Month caps at 290px and contracts; dates upper right, event marks 3px.

Map: 180×74px cards, nested containers, preserved manual coordinates, optional 220px Unsorted tray.

## Visual profiles

Base design size 8.5pt with an independent text scale of 75–140%; **90% is the default**. Heading size (80–160%) scales page and section titles separately. Density is Compact, Comfortable or Spacious, and a corner style (theme default, square, slight, rounded, soft, round) can override each theme's radius. Style-sheet font sizes scale with text size, and fixed-width labels (timer, totals, estimates, countdowns, the bottom-bar type selector) are measured from the active font so nothing clips at large sizes.

| Theme | Windows / Linux type | Shape and surface | Color schemes (first is the default) |
|---|---|---|---|
| Graphite | Segoe UI / Noto Sans | Slate, crisp 3px corners | Cyan, Azure, Mint, Orange, Rose |
| Terminal | Consolas / DejaVu Sans Mono | Near-black, square controls, ruled rows | Amber, Green, Ice, Magenta, Mono |
| Paper | Trebuchet MS + Georgia headings / Noto Sans + DejaVu Serif | Ivory, 8px corners, editorial headings | Sage, Clay, Ocean, Plum |
| Midnight | Bahnschrift / DejaVu Sans | Deep surfaces, 11px cards, pill controls | Lavender, Ocean, Forest, Wine, Ember |
| Nord | Segoe UI Variable / Noto Sans | Flat arctic surfaces, 6px corners, underlined tabs | Polar Night, Frost, Aurora, Dusk, Snow Storm (light) |
| Catppuccin | Segoe UI Variable / Cantarell | Pastel, 10px corners, pill tabs and roomy buttons | Mocha, Macchiato, Frappé, Latte (light), Mocha Blue, Mocha Peach |
| Editor | Segoe UI + Cascadia Code headings / Ubuntu + monospace headings | Code-editor tabs, gutter-lined rows, monospace badges | Dracula, Tokyo Night, One Dark, Monokai, Gruvbox Dark, Gruvbox Light, Solarized Dark, Solarized Light, Rosé Pine, Everforest |
| System | Paper for light OS scheme, Graphite for dark | Resolved when applied | Uses the Paper or Graphite choice |

A color scheme changes colors only; type, shape and surface treatment belong to the theme. Palettes and schemes are defined in palettes.py, which has no Qt dependency; every preset scheme keeps text at 4.5:1 and accents at 4:1 against its surfaces (tests/test_palettes.py). Presets that adapt published palettes keep their character but adjust secondary text, accent or danger values where the original falls below those ratios.

Every theme also has a **Custom** scheme. It starts from the scheme that was selected and lets the user pick the nine main colors (background, panels, raised surfaces, borders, text, secondary text, accent, danger, navigation rail) with a color wheel, brightness slider and hex entry. **Advanced colors** override single elements: button background, button text, button hover outline, text on accent buttons, headings and bold labels, input fields, selection, warnings and the timer/clocks. An unset advanced color follows its main color. Custom colors are saved per theme (`customColors`) and are not contrast-checked, so a live preview sits above the editor.

Fonts: interface, heading and number/clock fonts can each be left on the theme default or set to any installed family. Suggested families (for example Inter, Segoe UI Variable, Atkinson Hyperlegible, IBM Plex Sans, Cascadia Mono, JetBrains Mono, Fira Code) are listed first when installed. When a theme's preferred font is missing, the next installed fallback is used. Combo and spin chevrons are generated in the scheme's muted color on first use in the system temp folder, not shipped as per-theme files.

Use installed fonts with fallback lists, no runtime downloads or bundled font files. Theme tokens live in theme.py. Event categories/custom colors remain consistent across views.

## Interaction and scope

QtAwesome icons have names/tooltips. Personal/Team stays upper left. Future Code/Team explain their status.

Kanban displays a translucent, dashed ghost card in the destination lane as soon as a ticket enters it. The ghost reserves the ticket's resulting position in the current board order; it is temporary and cannot be selected. Drop saves the status immediately with Undo. Leaving, cancellation and same-column drops do not write. Kanban does not use the Map's hold timer or relationship confirmation.

Project colors appear on the project prefix in Kanban ticket keys and matching project folder icons. A lightly tinted prefix chip and colored text identify the project without tinting the ticket body or its identifier suffix. Stable project UUIDs determine hue; Paper uses a darker shade for readable contrast. Names, ticket status and project list order do not affect the color.

Keep lanes at least 180px wide, increasing that minimum to fit headers and a six-character project key/identifier at the current font size. Scroll horizontally in narrow windows. Titles show complete lines within their reserved area and elide the last line; full text stays available on hover.

Calendar clicks edit actual records. Map changes require a 1.5-second target hold, ghost/progress and release confirmation. Line patterns distinguish parentage, dependencies and sequence. Context menus and inspector fields offer alternatives.

Preserve drafts through refresh; navigation uses Save/Discard/Cancel. Timer stays live. Theme changes must not duplicate status widgets.

Appearance/geometry/density/text scale/panel widths/fonts/custom colors/world clocks are device-local. Project/account entities sync; future repository paths stay device-local. Exact interactions are in [CALENDAR_AND_MAP.md](CALENDAR_AND_MAP.md).

Settings uses a 168px category menu beside one scrollable page: View, Theme, Local data, Sync or Account. Forms stop at 820px wide. View and Theme have separate Apply actions; the Theme page's Colors section lists the schemes of whichever theme is selected, remembers one choice per theme, and hides its selector for System; switching categories keeps field entries. The selected section survives appearance changes and navigation during the session. Sync shows its unresolved conflict count in the menu. Keep section controls reachable at the minimum window size and 125% text scale.

View holds text size, heading size, density, the Projects pane and inspector widths, window-size presets (1280×800, 1440×900, 1600×1000, Maximize; applied immediately and limited to the screen), the planning time zone and up to three world clocks. The time zone and world clock pickers are searchable drop-downs sorted by UTC offset; each entry shows the offset, zone and its current time, and whole-hour fixed offsets (UTC−12 to UTC+14) are listed too. World clocks appear in the bottom bar after the daily total as "City HH:MM" and update every second. Theme holds the theme, corners, color scheme with the Custom editor, and fonts.


## Controls and labels

Combo/calendar/spin subcontrols use SVG chevrons generated for the active scheme and transparent embedded editors. Tab bases must not draw a bright native separator. Fixed-width identifiers and project badges reserve their layout space and elide with full hover text.

Quick Add has title-first capture, preset/context controls, optional detail tabs and a fixed footer with batch capture. Label inputs commit on Enter without submitting the form; removable colored chips wrap in narrow layouts. Bug is red, Feature teal, with stable colors for other presets/custom names. Color accompanies visible text.

Windows captions/text/borders use supported native theme attributes; unsupported platforms retain OS decoration. See [QUICK_ADD_AND_LABELS.md](QUICK_ADD_AND_LABELS.md).
