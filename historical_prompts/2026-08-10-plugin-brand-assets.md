# Plugin brand assets

Date: 2026-08-10

## Background

The VivagoAgent plugin needs consistent brand presentation in Codex and Claude Code. Product design
provided square SVG artwork for standard, dark-mode, and compact-icon use.

## User requirement

Package editable SVG sources and matching PNG assets with the plugin, and configure supported host
metadata so the brand is visible wherever the host exposes plugin or skill artwork.

## Accepted decisions

- Use the supplied artwork exactly as delivered.
- Preserve the white background in the standard 512-pixel logo.
- Preserve the black background in the dark 512-pixel logo and the 128-pixel icon.
- Keep both SVG and PNG versions in the distributed plugin package.
- Store plugin-level artwork under `plugin/assets/`; do not treat it as skill-owned artwork or
  duplicate its paths in skill metadata.
- Use `#574DFF` as the primary interface brand color; reserve the remaining gradient colors for the
  official logo artwork.
- Configure only fields accepted by each host's current manifest validator.

## Explicit non-goals

- Do not create transparent-background variants in this iteration.
- Do not redraw, simplify, recolor, or add text to the supplied artwork.
- Do not add unsupported Claude Code manifest fields.
- Do not change authentication, API routing, or task behavior.
