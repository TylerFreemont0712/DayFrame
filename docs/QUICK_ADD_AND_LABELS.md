# Quick Add, labels and native chrome — 0.4.1

## Screenshot fixes

The rounded themes now explicitly style dropdown arrows, date/time controls and numeric steppers. Bundled SVG chevrons replace mismatched native subcontrols. Embedded editors have transparent, unframed backgrounds. Semantic palette roles also cover bevel/shadow colors.

Tab bars suppress the native base line that produced a bright separator. Long project badges and ticket identifiers use width-aware elision and full hover/accessibility text. Fixed-width row fields keep their own layout space. Component / milestone avoids mnemonic rendering artifacts.

## Quick Add

The native modal has a title-first layout, Ticket/Event switches and a fixed action footer. A new ticket can choose project, preset, initial status, priority, optional deadline and Pin to Today.

Ticket presets are Blank, Task, Bug, Feature and Maintenance. They set the corresponding label and initial priority/status; Bug starts at High priority. Switching preset replaces its previous preset label while retaining other labels. Presets remain ordinary labels, not a separate ticket type.

More ticket details contains Description/Estimate, Organization and Checklist tabs. Organization includes component, milestone, parent ticket and map destination. The preview explains inherited fields and section rules. Checklist accepts one step per line.

Explicit map placement applies ancestor rules. A selected parent contributes tags and fills empty component/milestone values. Ticket creation, inheritance, classification, placement and outbox writes commit in one transaction; a failed destination leaves no partial ticket.

Add + another saves and keeps the modal open. Project, status, priority, labels and organization remain selected; per-item title, descriptions and checklist clear. Newly saved tickets become available as parent choices. Errors retain the draft. Ctrl+Enter saves; Enter in the label input adds a label.

Events retain dates/times, type, multi-day spans, details/location/color, repeat and countdown controls. Today/Tomorrow shortcuts set dates. Editing an existing event saves changed fields.

## Shared labels

Quick Add and the ticket inspector use the same chip editor. Enter, a comma or the Add button commits typed labels. The Labels menu offers colored presets and previously used names; autocomplete also offers saved labels. Each selected chip has an accessible remove button.

| Preset | Color |
|---|---|
| bug | Red |
| feature | Teal / light green |
| task | Slate blue |
| improvement | Purple |
| documentation | Blue |
| maintenance | Amber |

Custom names have a stable muted color derived from their name. Saved custom labels are discovered from this account's tickets and offered in later editors. Cancelling an unsaved ticket does not create global label records. There is no separate label-management database or per-label custom-color editor in this release.

Chips wrap inside narrow inspectors and bounded modals. Kanban cards show a compact label row, prioritizing common presets; map cards show labels when room permits and list them in hover details. Label text remains visible alongside color.

## Window frames

On supported Windows versions, the main window and Qt dialogs apply the theme's caption, text and border colors through native DWM attributes, retaining standard resize, snap and caption controls. The application uses Microsoft's documented [frame attributes](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/ne-dwmapi-dwmwindowattribute) and [DwmSetWindowAttribute](https://learn.microsoft.com/en-us/windows/win32/api/dwmapi/nf-dwmapi-dwmsetwindowattribute).

Windows can decline unsupported attributes; the application continues using available OS decoration. Linux decoration remains controlled by the desktop/window manager.

The native Windows check creates hidden HWNDs for a main window and dialog, applies all four themes, and verifies successful attribute-setting results plus dark-mode readback. Caption/text/border color attributes are set-only on the tested DWM build; the check does not claim color readback. Run manually on Windows:

    .venv\Scripts\python.exe tests\check_native_frame.py

Regular UI tests run offscreen with isolated profiles and cover chip input/removal, custom-label reuse, row bounds, control rendering, batch capture, failure retention and atomic rollback.

## Compatibility

No database migration is needed: schema 4 and the 0.4 sync protocol remain unchanged. Labels use existing synchronized ticket fields. A 0.4 hub remains compatible. The older binary/source is preserved separately during local deployment; no live profile is used as a test fixture.
