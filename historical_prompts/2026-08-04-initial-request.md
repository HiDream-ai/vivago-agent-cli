# Initial request anchor

Date: 2026-08-04

## Request

Create a complete design and a new project for a VivagoAgent plugin that can be used by both Codex and Claude Code.

## Accepted decisions

- V1 uses `Skill -> local vivago-agent CLI -> existing VivagoAgent REST/SSE API`.
- Do not expose VivagoAgent's business MCP tools.
- Conversation history stays in VivagoAgent.
- V1 reuses the existing `vivago-client` login implementation; user center does not participate in V1 development.
- Do not require Hosted MCP, standard OAuth, MCP Tasks, or MRTR in V1.
- Keep authentication replaceable so standard OAuth can be added without changing host-facing commands.
- Build a separate project rather than modifying the existing VivagoAgent service for the POC.
