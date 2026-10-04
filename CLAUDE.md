# CLAUDE.md

This file guides Claude Code when working in this repository.

## Mandatory rules (non-negotiable)

These rules apply to every change, without asking.

1. **Every change ships with tests.** New code gets new tests; changed behaviour gets
   updated tests. The full test suite must pass before work is reported as done.
2. **Every piece of code is documented.** Modules, classes and public methods have
   docstrings covering purpose, arguments and non-obvious behaviour. Comments explain
   *why*, not *what*.
3. **Respect design principles.** SOLID, DRY, separation of concerns, and idiomatic
   Django: fat models / thin views, custom QuerySets and managers, mixins, and service
   modules for business rules that span several objects.
4. **Every user-facing string is translated into Arabic and French in the same commit.**
   Workflow: `makemessages` → translate both `.po` files → `msgfmt --check` →
   `compilemessages` → commit the `.po` and `.mo` files together. Brand names are not
   translated.
5. **Every RAG step is documented in `docs/rag/`.** This covers findings with measured
   evidence, decisions with rationale, processing stages, validation results, a
   development log of problems and fixes, and known limitations. Never document numbers
   that were not measured.
6. **Every change updates the documentation in `docs/` in the same commit.** Docs are
   professional reference material for experienced engineers.
   - Significant design choices get an ADR in `docs/architecture/decisions/`, named
     `NNNN-kebab-title.md`, with the sections Status, Context, Decision, Consequences.
   - Every new dependency is listed in `docs/technology-stack.md` with its version, role
     and license.

## Working agreement

- Never delete, move or overwrite files, and never run destructive commands (`rm`,
  `git reset --hard`, `git clean`, `git push --force`), without asking the user first.
- Commit and push only when asked. Commit messages are descriptive: a title, then what
  changed and why.
- Before choosing an architecture the spec does not dictate, check the framework's
  documented conventions and propose it to the user first.
- Never run two test runs at the same time.
- Never commit `.env`, secrets, source books (`data/raw/`) or extracted text
  (`data/processed/`).
- Never print the contents of `.env` or any secret.

## Project

Backend for the competition "AI Challenge – Serving Islamic Content". The service answers
questions about Islam from vetted sources using retrieval-augmented generation (RAG) and
AI agents. Questions the AI must not answer are routed to centers of specialists, who
receive and answer them.

<!-- Sections to be added as the project grows: Layout, Commands, Conventions. -->
