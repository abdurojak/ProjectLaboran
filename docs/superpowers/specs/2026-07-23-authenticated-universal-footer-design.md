# Authenticated Universal Footer Design

## Scope

Add one reusable LabHub footer component to every page rendered for an
authenticated user. Public pages, including login, registration, password
recovery, verification, and public registration pages, must not show it.

Restore the inventory item list's `Aksi` column to the rightmost position.

## Component Placement

Create `components/footer.html` and include it from the shared `base.html`
inside the existing `current_pengguna` condition. The footer belongs below the
main page frame so it appears after page content, not inside individual cards
or tables.

The shared component must use Django's existing static asset:
`core/img/labhub-logo.png`.

## Content

The footer contains:

- LabHub logo, product name, and "Laboran Teknik Informatika Usakti".
- A "Hubungi Kami" section with:
  - Telephone: `+62 858-9448-8626`, linked using `tel:`.
  - Email: `Labtif.fti@trisakti.ac.id`, linked using `mailto:`.
  - Address: `Jl. Kyai Tapa No. 1, Grogol, Jakarta Barat, Indonesia`.
  - A Google Maps location link that opens in a new tab with safe
    `rel="noopener noreferrer"` behavior.
- Direct navigation links without a "Navigasi Penting" heading:
  - Dashboard.
  - Profil.
  - Bantuan.
- A bottom copyright row:
  `Copyright (c) 2026 Laboran Teknik Informatika Usakti`.

The rendered UI may use the copyright symbol. The year remains 2026 as
explicitly requested.

## Responsive Layout

- Desktop: identity, contact, and navigation are displayed in three columns.
- Tablet: identity occupies the first area; contact and navigation reflow
  without horizontal overflow.
- Mobile: all sections stack vertically, with adequate spacing and touch
  targets.
- Long address and email text must wrap without overlapping nearby content.
- The footer remains in normal document flow and must not be covered by, or
  compete spatially with, the floating LabBot.

## Visual Treatment

Use the established LabHub dark navy, teal accent, and muted light text colors.
Keep borders and corner radii restrained and consistent with the existing
application. The footer must read as a page boundary rather than another
dashboard card.

## Accessibility

- Give the logo meaningful alternative text.
- Use semantic `footer`, navigation, address, and link elements.
- Provide visible keyboard focus states.
- Add descriptive accessible labels to telephone, email, and location links.

## Verification

- Assert the footer appears for an authenticated request.
- Assert it does not appear for an anonymous request.
- Assert the component contains the logo and required contact/navigation links.
- Verify the inventory action header and row controls are rightmost again.
- Run Django system checks and focused template/view tests.
- Inspect desktop, tablet, and mobile layouts for overflow and overlap.
