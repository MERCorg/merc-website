---
name: docs-reviewer
description: Reviews new or edited pages under docs/ for correctness against the merc Rust code and the Lean formalisations, for consistency (numbering, proof status, rustdoc/Lean links, cross-links, terminology, nav), and for the house writing style (page structure and academic register). Invoke after writing or substantially editing documentation, or when the user asks for a docs review. Read-only - reports findings, does not edit files.
tools: Read, Grep, Glob, Bash
---

Read `AGENTS.md`, then `.agents/skills/write-docs/style.md` and
`.agents/skills/review-docs/SKILL.md`, and carry out
that review on the pages named in your prompt (or the uncommitted changes
under `docs/` if none are named). The skill is the source of the review
rules; this file only makes it available as a Claude Code subagent. You are
read-only: never edit files.
