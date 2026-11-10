# Calendar and project-map behavior

## Calendar and Home

Calendar has three areas: an event-marked month above Upcoming with a resizable divider on the left, and a Sunday–Saturday week timeline on the right. The normal window defaults to 1280×800 and supports 980×640.

Month dates are upper right. Marks are 3px high, ordered all-day first then by start time. Timed lengths scale with duration; all-day marks fill the available width and tint the cell. Work blocks and deadlines also appear. Overflow has a count and hover details. Select a date to change week; double-click to add an all-day event.

The weekly timeline has a sticky header, a 48–96px all-day band, and all 24 hours in a scroll area initially near 08:00. Simultaneous timed items use separate lanes. All-day end dates are inclusive; midnight endings do not create zero-length blocks on the next day.

Click events in Home, Upcoming, Day Agenda or Week to edit the same record. Fields include title, start/end dates, optional times, type, location, description, color, yearly repeat, major-event and pin choices. Archive preserves the record and supports Undo.

Drag single-day timed events/work blocks to move; drag the bottom edge to resize. Scheduling uses 15-minute steps and Ctrl+Z Undo. Double-click blank timeline time to create an event. Multi-day and yearly events use the editor; yearly edits affect the whole series.

Presets include Appointment, Meeting, Birthday, Trip, Personal plan, Routine, Holiday, Work session and Other event. Birthdays default to all day/yearly; trips and holidays default to all day. February 29 yearly events are observed February 28 in non-leap years. Other recurrence rules, exceptions and reminders remain future work.

Work blocks reference tickets, so titles/details stay current. Moving work never changes the ticket deadline. Click a deadline to open its ticket. Recorded time remains separate and editable in Time.

Home shares the same calendar projection. It includes priorities, due/overdue, in-progress and up to five recent ungrouped tickets, three major countdowns (pinned first) drawn as tiles, ordinary upcoming events, all-day items and Day Agenda. A week strip of seven day cards (Sunday first) shows each day filled in with its all-day chips and a small timeline; clicking a card points the Day Agenda at that day and double-clicking adds an event there. Events shown as countdown tiles are not repeated in Upcoming. Every event type has a symbol. Focus shows the current timer's ticket/duration/pause control, including while an unrelated inspector draft is open.

## Nested map and inherited rules

Sections have optional parents, rendered as containers such as Frontend > Calendar > Ticket. Section context menu → Add subsection and the editor's Inside section field offer alternatives to dragging. Manual coordinates remain relative to the owning section.

Label rules add labels without removing existing ones. Rules inherit along the section path; innermost scalar rules win. Automatic placement chooses the deepest matching rule-bearing section, then sort order and stable ID. Rule-free sections accept manual placement.

Reparenting a section previews inherited changes for contained tickets. Manual placement remains manual. Undo restores hierarchy, ticket fields and placements.

## Deliberate gestures

Hold in one target zone for 1.5 seconds. A ghost shows progress and the proposed action. Changing zones resets the hold. The hold arms the operation; release opens a confirmation. Early release, Cancel, or leaving a target changes no classification/link data. Ctrl+Z reverses a confirmed operation.

| Dragged item | Target | Confirmed result |
|---|---|---|
| Ticket | Section center | Place inside; apply ancestor/section rules |
| Section | Section center | Nest inside target |
| Section | Target right edge | Dragged section comes after target |
| Section | Target left edge | Dragged section comes before target |
| Ticket | Target ticket right edge | Dragged ticket becomes target's child |
| Ticket | Target ticket left edge | Dragged ticket becomes target's parent |

Position changes within the same section save manual coordinates without a classification hold and support Undo.

Parentage is separate from dependencies and does not change status/blocking. The child inherits parent tags and fills empty component/milestone values; confirmation explains this. An unsorted child may be placed beside its parent so the connection is visible.

Solid accent lines show parent → child; dashed amber lines show prerequisites; dotted purple lines show section sequence. A link starts at a dot on its source and ends in an arrowhead on its target, meeting both at a right angle; links that share a side of a card are spread along it. Routes are smooth curves where the way is clear and rounded steps along the channels between columns and rows where a card is in the way. Borders show containment. Parent and sequence cycles/cross-project links are rejected locally and on the Python hub.

Ticket context actions: Open, Start timer, Schedule, Create child, Complete, Remove parent. Section context actions: Edit, Add subsection, Move to root, Clear sequence. The inspector exposes parent and child navigation.

## Unsorted and compatibility

Unsorted is a collapsible 220px project tray. Its button has a red nonzero count, otherwise muted (0). Select tickets or drag them onto the map using the same guarded gesture.

Schema 3 adds event metadata; schema 4 adds ticket parent_id and section parent_id/predecessor_ids. Versions 1–3 migrate, and import migrates only a read-only source's copy. Notes UI is hidden while stored notes remain in SQLite, backups and sync.

Update all clients and the Python hub to 0.4 for new fields. Older binaries reject newer databases; preserve earlier backups independently. UI Undo is session-local.
