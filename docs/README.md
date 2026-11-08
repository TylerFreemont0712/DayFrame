# DayFrame documentation

This folder holds everything about DayFrame that is not code. Start here to find the right document, and follow the rules below when you add or change one.

## Layout

| Folder | Holds | Documents |
|---|---|---|
| (repository root) | Entry points every contributor reads first | [README.md](../README.md), [SPEC.md](../SPEC.md), [CHANGELOG.md](../CHANGELOG.md), [CONTRIBUTING.md](../CONTRIBUTING.md), [AGENTS.md](../AGENTS.md), [CLAUDE.md](../CLAUDE.md) |
| [product/](product/) | What the app does and why: owner decisions, interaction rules, visual design | [DECISIONS.md](product/DECISIONS.md), [DESIGN_SYSTEM.md](product/DESIGN_SYSTEM.md), [CALENDAR_AND_MAP.md](product/CALENDAR_AND_MAP.md), [QUICK_ADD_AND_LABELS.md](product/QUICK_ADD_AND_LABELS.md) |
| [engineering/](engineering/) | How the code is built: boundaries, module map, data model, sync design | [ARCHITECTURE.md](engineering/ARCHITECTURE.md), [CODE_MAP.md](engineering/CODE_MAP.md), [DATA_MODEL.md](engineering/DATA_MODEL.md), [ACCOUNTS_AND_SYNC.md](engineering/ACCOUNTS_AND_SYNC.md) |
| [operations/](operations/) | Running, packaging and releasing; stable identifiers; third-party notices | [OPERATIONS.md](operations/OPERATIONS.md), [RELEASES.md](operations/RELEASES.md), [BRANDING.md](operations/BRANDING.md), [THIRD_PARTY.md](operations/THIRD_PARTY.md) |
| [status/](status/) | Where the project stands and where it could go | [CURRENT_STATUS.md](status/CURRENT_STATUS.md), [IDEAS.md](status/IDEAS.md) |
| [screenshots/current/](screenshots/current/) | Reference screenshots of the current native UI | PNG files only |

### Which document answers what

| Question | Look in |
|---|---|
| What must the app do? | SPEC.md |
| Why was it decided this way? Did the owner change it? | product/DECISIONS.md |
| How should a screen look or behave in detail? | product/DESIGN_SYSTEM.md and the area documents in product/ |
| Where is the code for X, and what calls it? | engineering/CODE_MAP.md |
| Why are the layers split this way? Which threads exist? | engineering/ARCHITECTURE.md, engineering/CODE_MAP.md |
| What is stored, and how does sync merge it? | engineering/DATA_MODEL.md, engineering/ACCOUNTS_AND_SYNC.md |
| How do I run, back up, pair a device or build a package? | operations/OPERATIONS.md, CONTRIBUTING.md |
| Can I ship? What was last packaged? | operations/RELEASES.md |
| What actually works and on which platforms was it tested? | status/CURRENT_STATUS.md |
| What might we build next? | status/IDEAS.md |

When two sources disagree, the latest direct owner decision wins, then SPEC.md, then the area documents, then screenshots (see "Source precedence" in DECISIONS.md). Fix the disagreement rather than leaving it.

## Documentation rules

### Where things go

1. **One topic, one home.** Each fact has one authoritative document. Elsewhere, link to it instead of repeating it. Short summaries in README.md are fine when they link to the details.
2. **Pick the folder by audience.** Behavior and decisions go in product/, implementation in engineering/, running and shipping in operations/, progress and plans in status/. Root-level files stay limited to the entry points listed above.
3. **Future ideas go in status/IDEAS.md**, not scattered as "planned" notes. Area documents may say a behavior is planned, but the list of what could come next lives in IDEAS.md.
4. **Decisions are logged, not overwritten.** Add new owner decisions to DECISIONS.md with the next D-number or a dated section. When a decision supersedes an older one, mark the old entry "(updated by D-xxx)" rather than deleting it, then update SPEC.md and the affected area documents.
5. **Screenshots** in screenshots/current/ show only the current UI. Replace outdated images instead of keeping versions; do not commit mockups or archives.

### Keeping docs true

6. **Update docs in the same commit as the change.** A behavior change updates SPEC.md or the area document; a new, moved or renamed module updates engineering/CODE_MAP.md; a user-visible change adds a line to the Unreleased section of CHANGELOG.md.
7. **Be honest about status.** Never describe a feature as available until it is implemented and tested. Say which platforms were verified; a Windows pass does not verify Linux Mint, and source tests do not verify a package.
8. **Release facts live in RELEASES.md and CURRENT_STATUS.md.** Version numbers elsewhere change only in an explicitly requested release.
9. **Remove what is superseded.** Delete obsolete documents and sections rather than marking them "old". Git keeps the history.

### Writing style

10. Plain, natural language. Describe what the app does and why, without promotional wording or process narration (see "Writing and commit history" in AGENTS.md).
11. Start each document with a single `#` title and one or two sentences saying what it covers. Use `##` sections, tables for reference lists, and fenced code blocks with a language for commands.
12. Use relative Markdown links (`[CODE_MAP.md](engineering/CODE_MAP.md)`), and write code paths relative to the repository root (`dayframe/ui/window/main.py`).
13. File names are UPPER_SNAKE_CASE.md inside topic folders, except README.md indexes.
14. Never include passwords, tokens, private certificates, real profile data or personal ticket content in documentation or screenshots.

### Adding a document

- Check the layout table first; extend an existing document if the topic fits.
- Otherwise create it in the right folder, add it to the layout table above, and link it from wherever readers will look for it.
- If it changes how contributors work, mention it in CONTRIBUTING.md or CLAUDE.md as well.
