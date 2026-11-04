# DayFrame identity and compatibility

Use **DayFrame**, with capital D and F. Schema 4 is the current data format.

## Assets

- assets/dayframe-icon-master.png: original generated RGBA icon, retained unchanged.
- assets/DayFrame.png: 512px desktop export.
- assets/DayFrame.ico: 16/20/24/32/40/48/64/96/128/256px Windows export.
- dayframe/resources/dayframe-icon.png: packaged application icon.
- assets/dayframe-logo.png: horizontal logo for documentation.

The open square frames an abstract D with three agenda bars and a cyan accent. Graphite, near-white and cyan match the default interface. Keep the mark consistent across themes; it is an application identity, not a per-theme navigation glyph. UI icons remain the coherent QtAwesome vector set.

Generated with the built-in imagegen tool. The icon master has transparent pixels outside its rounded tile; the horizontal wordmark uses a graphite background. scripts/export-brand-assets.py uses Qt to resample/export native formats without changing the artwork. Generated raster assets are not editable vector originals.

## Icon prompt

```text
Use case: logo-brand
Asset type: production desktop application icon
Primary request: create a single simple, distinctive icon for DayFrame, a private desktop dashboard for planning days, project tickets, calendars and time tracking.
Subject: a geometric open square frame with an abstract capital D inside; the D's open counter subtly suggests three stacked agenda blocks, with one small cyan accent block. A unified strong silhouette, restrained and precise.
Style/medium: flat vector-like graphic, crisp edges, no texture, generous spacing, readable at 16 to 32 pixels.
Color palette: deep graphite rounded-square tile, near-white main mark, cyan accent matching a graphite/cyan desktop interface.
Composition: one centered icon, square canvas, tile occupies about 88 percent with transparent space outside the rounded corners. No typography or wordmark.
Constraints: single icon only; no mockup, no extra variants, no shadows, no glow, no gradients, no fine lines, no clock hands, no checkmarks, no watermark. Actual transparent background outside tile.
```

## Logo prompt

The approved icon was supplied as the edit reference.

```text
Use case: logo-brand
Asset type: horizontal logo for the DayFrame desktop planning application and repository README.
Input images: Image 1 is the approved DayFrame icon; preserve its exact open-frame D design and cyan agenda block.
Primary request: create a polished horizontal brand lockup: supplied icon on the left, and the exact word "DayFrame" on the right. Spell D-a-y-F-r-a-m-e with capital D and F only. Large clear modern sans-serif lettering, near-white, medium weight. No tagline.
Composition: a wide horizontal canvas, approximately 3:1 aspect ratio, generous balanced padding, centered logo group. Icon and wordmark align vertically; icon height about the capital plus lowercase ascender area, icon slightly larger than the lettering. Flat deep graphite background #151c22 throughout.
Constraints: maintain the icon's identity, only add the wordmark and compose the logo; no additional symbols, no mockups, no ornaments, no gradients, no perspective, no lighting effects, no watermark. Simple restrained professional desktop app branding.
```

## Storage and runtime identifiers

Application names, the Python package, launchers, installer, logo and icon use DayFrame. The existing checkout path is C:\Apps\TimeManager.

The following are intentionally preserved:

| Identifier | Compatibility reason |
|---|---|
| %LOCALAPPDATA%\TimeManager and $XDG_DATA_HOME/TimeManager | Open the existing native profile without moving live data |
| timemanager.db and native-desktop.lock | Preserve database identity and mutual exclusion with earlier clients |
| .local-session.json | Retain remembered local sign-in |
| TimeManager.native.sync | Reuse registered device credentials in the OS keyring |
| TM_HUB_* variables and timemanager-hub data/config paths | Existing Linux service configuration continues to work |
| application/x-timemanager-ticket | Stable internal drag format |
| Schema 4 / sync protocol 1 | Stable data and synchronization format |

These identifiers are used by the active application and its stored data. Treat changes to them as a data migration, rather than a branding edit.

The installer uses the DayFrame installation directory and uninstall entry. Uninstalling leaves runtime data intact. Only one application process may open a profile at a time.
