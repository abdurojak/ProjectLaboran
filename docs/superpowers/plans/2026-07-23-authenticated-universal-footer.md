# Authenticated Universal Footer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a responsive footer to authenticated pages and restore the inventory action column to the right.

**Architecture:** Keep footer markup in one reusable component included by the shared base template under `current_pengguna`. Use existing static assets and named Django URLs.

**Tech Stack:** Django templates, Tailwind CSS, Lucide icons.

---

### Task 1: Footer component

**Files:**
- Create: `apps/core/templates/components/footer.html`
- Modify: `apps/inventaris/templates/base.html`

- [ ] Add semantic responsive footer markup with the existing LabHub logo, contacts, location, menu, and copyright.
- [ ] Include it after `main` only when `current_pengguna` exists.

### Task 2: Inventory action position

**Files:**
- Modify: `apps/inventaris/templates/inventaris/barang_list.html`

- [ ] Restore the action header and controls as the rightmost table column.

### Task 3: User verification

- [ ] Leave changes unpushed for manual user testing.
