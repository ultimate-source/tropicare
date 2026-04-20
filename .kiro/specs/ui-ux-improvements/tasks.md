# Implementation Plan: UI/UX Improvements

## Overview

Incremental implementation of UI/UX improvements to the TropiCare frontend. Tasks are ordered by dependency: foundational modules first (i18n, store persistence, hooks), then component modifications that consume them, then integration/wiring, and finally tests. All code is TypeScript with React 19, Next.js App Router, Tailwind CSS 4.2, and Zustand.

## Tasks

- [x] 1. Set up i18n system and translation dictionaries
  - [x] 1.1 Install `fast-check` as devDependency
    - Run `npm install --save-dev fast-check` in the frontend directory
    - Required before any property tests can run
  - [x] 1.2 Create `lib/i18n/fr.ts` and `lib/i18n/en.ts` translation dictionaries
    - Define flat `Record<string, string>` with dot-notation keys covering all ~200 user-facing strings
    - Include keys for nav, chat, citation, intake, feedback, emergency, treatment, errors, loading, admin, auth, breadcrumb, skip-link
    - _Requirements: 26.1_
  - [x] 1.3 Create `lib/i18n/index.ts` with `useTranslation` hook and `getServerTranslation` helper
    - Implement dictionary flattening, dot-notation lookup, `{{key}}` interpolation
    - `useTranslation()` reads locale from Zustand store, returns `{ t, locale }`
    - `getServerTranslation(cookieValue?)` for Server Components (login/register)
    - Fallback chain: active locale → French → raw key string
    - _Requirements: 26.2, 26.3, 26.4, 26.5_
  - [x] 1.4 Write property test: Translation dictionary completeness (Property 13)
    - **Property 13: Translation dictionary completeness**
    - Verify every key in `fr` exists in `en` and vice versa
    - **Validates: Requirements 26.1**
  - [x] 1.5 Write property test: Translation lookup returns correct value (Property 14)
    - **Property 14: Translation lookup returns correct value**
    - For any key in both dictionaries and any locale, `t(key)` returns the exact value from that locale's dictionary
    - **Validates: Requirements 26.2**
  - [x] 1.6 Write property test: Translation fallback to French (Property 15)
    - **Property 15: Translation fallback to French for missing keys**
    - For any key in `fr` but absent from `en`, `t(key)` with locale "en" returns the French value
    - **Validates: Requirements 26.4**
  - [x] 1.7 Write property test: Translation interpolation (Property 16)
    - **Property 16: Translation interpolation replaces all placeholders**
    - For any template with 1–5 `{{key}}` placeholders and a matching params map, result contains no remaining `{{...}}` patterns
    - **Validates: Requirements 26.5**

- [x] 2. Add Zustand store persistence and dismissed alerts
  - [x] 2.1 Add `persist` middleware to `lib/store.ts` with split storage
    - Add `dismissedAlerts: string[]`, `dismissAlert`, `clearDismissedAlerts` fields
    - Configure two persist partials: sessionStorage (`tropicare-auth`: user, token) and localStorage (`tropicare-prefs`: language, session, dismissedAlerts)
    - `setLanguage` must also set `tropicare-lang` cookie for server-side i18n
    - `clearUser` must clear both storage keys
    - _Requirements: 24.1, 24.2, 24.3, 24.4, 25.1_
  - [x] 2.2 Write property test: Preferences persist round-trip (Property 11)
    - **Property 11: Preferences persist round-trip via localStorage**
    - For any language, SessionMeta, and dismissed alerts list, set → persist → rehydrate produces identical values
    - **Validates: Requirements 24.1, 25.1**
  - [x] 2.3 Write property test: Auth persist round-trip (Property 12)
    - **Property 12: Auth persist round-trip via sessionStorage**
    - For any User object and token string, set → persist → rehydrate produces identical values
    - **Validates: Requirements 24.2**

- [x] 3. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Create reusable hooks (useFocusTrap, useAutoScroll)
  - [x] 4.1 Create `hooks/useFocusTrap.ts`
    - Implement Tab/Shift+Tab cycling within `containerRef` when `isActive` is true
    - Call `onEscape` callback on Escape key
    - Set initial focus to first focusable element on activation
    - _Requirements: 1.2, 1.3, 1.5, 9.4_
  - [x] 4.2 Create `hooks/useAutoScroll.ts`
    - Auto-scroll container when dependencies change, unless user scrolled up
    - 50px threshold for "at bottom" detection
    - Return `{ isAtBottom, scrollToBottom }` for scroll-to-bottom button
    - _Requirements: 13.1, 13.2, 13.3_

- [x] 5. Create shared UI components (SkipLink, Breadcrumb, SummaryPreview)
  - [x] 5.1 Create `components/ui/SkipLink.tsx`
    - Visually hidden anchor, visible on focus, links to `#main-content`
    - Use `useTranslation` for label text
    - _Requirements: 32.1, 32.2, 32.3, 32.4_
  - [x] 5.2 Create `components/ui/Breadcrumb.tsx`
    - `<nav aria-label="Fil d'Ariane">` with `<ol>`, `aria-current="page"` on last item
    - Accept `items: BreadcrumbItem[]` prop, resolve labels via `useTranslation`
    - _Requirements: 19.1, 19.2, 19.3_
  - [x] 5.3 Create `components/intake/SummaryPreview.tsx`
    - Modal overlay with focus trap (via `useFocusTrap`)
    - Display all filled PatientContext fields
    - "Confirmer" and "Modifier" buttons, close on Escape
    - Use `useTranslation` for all labels
    - _Requirements: 9.1, 9.2, 9.3, 9.4_
  - [x] 5.4 Write property test: Summary preview displays all filled fields (Property 5)
    - **Property 5: Summary preview displays all filled fields**
    - For any PatientContext with mandatory fields filled and random optional fields, the preview renders all filled field values
    - **Validates: Requirements 9.2**

- [x] 6. Add global CSS: focus-visible ring and skip-link styles
  - Add `:focus-visible` ring utility to `app/globals.css` (2px solid outline, blue-500 on white, white on blue)
  - Add skip-link styles (visually hidden, visible on focus)
    - _Requirements: 33.1, 33.2, 33.3, 32.2_

- [x] 7. Create error categorization utility and reusable error banner
  - [x] 7.1 Create `categorizeError` function in `lib/api.ts` or `lib/errors.ts`
    - Map HTTP status codes: 0/connection → "network", 401/403 → "authentication", all others → "server"
    - _Requirements: 17.3_
  - [x] 7.2 Create a reusable `ApiErrorBanner` component (or inline pattern) for non-streaming API failures
    - Display localized error message with categorized error type and a "Réessayer" button
    - Retry button re-invokes the original API call with the same parameters
    - Wire into chat page (session creation), sessions list page, and FeedbackPanel
    - _Requirements: 17.1, 17.2_
  - [x] 7.3 Write property test: HTTP status code error categorization (Property 10)
    - **Property 10: HTTP status code error categorization**
    - For any HTTP status code 100–599, returns exactly one of "network", "authentication", or "server"
    - **Validates: Requirements 17.3**

- [x] 8. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Update `hooks/useStream.ts` for conversation history and error handling
  - [x] 9.1 Refactor `useStream` to accumulate `Turn[]` with `currentTurn` pattern
    - Define `Turn` interface, update `StreamState` to include `turns`, `currentTurn`, `lastQuery`
    - On `send()`, store query in `lastQuery`, push completed turn to `turns` array
    - Add `retry` callback that re-sends `lastQuery`
    - _Requirements: 11.1, 11.3, 16.2, 16.3_
  - [x] 9.2 Write property test: Streaming error preserves partial results (Property 9)
    - **Property 9: Streaming error preserves partial results**
    - For any StreamState with differential items and citations, applying an error event retains all existing items while setting the error field
    - **Validates: Requirements 16.3**

- [x] 10. Update CitationDrawer with accessibility and search
  - Add backdrop overlay (`fixed inset-0 bg-black/30`), `role="dialog"`, `aria-modal="true"`
  - Integrate `useFocusTrap` with `onEscape` callback
  - Add search input with case-insensitive filter on `source_title`, `section`, `chunk_snippet`
  - Display match count (e.g., "3 / 12 sources")
  - Use `useTranslation` for all labels
  - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 14.1, 14.2, 14.3, 14.4_
  - [x] 10.1 Write property test: Citation filter correctness and count (Property 8)
    - **Property 8: Citation filter correctness and count**
    - For any list of 0–20 citations and any search string, only matching citations are displayed and count text is correct
    - **Validates: Requirements 14.2, 14.3, 14.4**

- [x] 11. Update DifferentialCard accessibility
  - Add `aria-expanded` to toggle button
  - Replace text chevrons ("▲"/"▼") with CSS chevron + `aria-hidden="true"`
  - Add `role="meter"`, `aria-valuemin="0"`, `aria-valuemax="100"`, `aria-valuenow`, `aria-label` to confidence bar
  - Responsive: wrap confidence bar below name on mobile
  - Use `useTranslation` for labels ("Signes d'alarme", "Arguments pour", etc.)
  - _Requirements: 3.1, 3.2, 3.3, 3.4, 28.2, 30.4_
  - [x] 11.1 Write property test: DifferentialCard aria-expanded (Property 2)
    - **Property 2: DifferentialCard aria-expanded reflects expanded state**
    - For any DiagnosisItem and boolean expanded state, `aria-expanded` matches the state
    - **Validates: Requirements 3.1**
  - [x] 11.2 Write property test: Confidence meter attributes (Property 3)
    - **Property 3: DifferentialCard confidence meter attributes**
    - For any confidence in [0,1], the meter has correct `role`, `aria-valuemin`, `aria-valuemax`, `aria-valuenow`, and `aria-label`
    - **Validates: Requirements 3.3, 3.4**

- [x] 12. Update IntakeForm: inline validation, responsive grids, i18n, summary preview
  - [x] 12.1 Add inline validation on blur with `aria-describedby` and `aria-invalid`
    - Track per-field errors (`FieldErrors` type), validate on blur, clear on correction
    - Block submission when errors exist
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_
  - [x] 12.2 Update Section component: `aria-expanded`, `aria-controls`, CSS chevron
    - Replace text chevrons with CSS-based chevron + `aria-hidden="true"`
    - Add `aria-controls` referencing content panel id
    - _Requirements: 2.1, 2.2, 2.3_
  - [x] 12.3 Add TagEditor helper text with `aria-describedby`
    - Display "Appuyez sur Entrée pour ajouter" below input, linked via `aria-describedby`
    - _Requirements: 7.1, 7.2_
  - [x] 12.4 Make grids responsive
    - Mandatory fields: 1 col default, 2 cols sm, 3 cols lg
    - Region + onset: 1 col default, 2 cols sm
    - Vital signs: 2 cols default, 3 cols sm, 4 cols lg
    - _Requirements: 8.1, 8.2, 30.1, 30.2_
  - [x] 12.5 Wire summary preview modal before submission
    - On submit (after validation), show SummaryPreview instead of calling `onComplete` directly
    - "Confirmer" proceeds, "Modifier" returns to form
    - _Requirements: 9.1, 9.3_
  - [x] 12.6 Wire `useTranslation` into IntakeForm for all strings
    - All labels, placeholders, options, errors, section titles, button labels
    - _Requirements: 27.1, 27.2_
  - [x] 12.7 Write property test: Section aria-expanded (Property 1)
    - **Property 1: Section aria-expanded reflects open state**
    - For any boolean open state, the toggle button's `aria-expanded` equals the string representation
    - **Validates: Requirements 2.1**

- [x] 13. Update EmergencyBanner and ChatStream dismissal announcements
  - Add `aria-live="polite"` region in ChatStream for dismissal announcements
  - Announcement text includes dismissed disease name
  - Use `useTranslation` for EmergencyBanner labels ("URGENCE VITALE", "URGENCE", "Pris en compte")
  - Read `dismissedAlerts` from Zustand store, use `dismissAlert` action
  - Clear `dismissedAlerts` when a new session is created (call `clearDismissedAlerts()` in chat page's `handleIntakeComplete`)
  - _Requirements: 4.1, 4.2, 25.1, 25.2, 25.3, 28.4_
  - [x] 13.1 Write property test: Emergency dismissal announcement (Property 4)
    - **Property 4: Emergency dismissal announcement contains disease name**
    - For any EmergencyFlag, dismissing the banner causes the aria-live region text to contain the disease name
    - **Validates: Requirements 4.1, 4.2**

- [x] 14. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 15. Update ThinkingIndicator: scrollable, expandable, i18n
  - Show all lines in scrollable container (max-h-[200px])
  - Add expand toggle to remove height constraint
  - Auto-scroll to bottom on new lines
  - Use `useTranslation` for "Analyse en cours" label
  - _Requirements: 10.1, 10.2, 10.3, 10.4, 28.6_
  - [x] 15.1 Write property test: ThinkingIndicator renders all lines (Property 6)
    - **Property 6: ThinkingIndicator renders all reasoning lines**
    - For any list of 1–50 strings, all lines are rendered and count matches input length
    - **Validates: Requirements 10.1**

- [x] 16. Update ChatStream: conversation history, textarea behavior, auto-scroll, loading state, i18n
  - [x] 16.1 Render all `state.turns` with dividers showing turn number/query
    - Map over `turns` array, render each turn's differential, treatment, emergencies, feedback
    - Render `currentTurn` below previous turns
    - _Requirements: 11.1, 11.2, 11.3_
  - [x] 16.2 Swap textarea Enter/Ctrl+Enter behavior and add hint text
    - Enter → newline, Ctrl+Enter (Cmd+Enter on Mac) → submit
    - Display "Ctrl+Entrée pour envoyer" hint below textarea
    - _Requirements: 12.1, 12.2, 12.3_
  - [x] 16.3 Integrate `useAutoScroll` and add scroll-to-bottom button
    - Attach `useAutoScroll` to the scrollable content container
    - Show floating "scroll to bottom" button when `!isAtBottom`
    - _Requirements: 13.1, 13.2, 13.3_
  - [x] 16.4 Add loading state before first stream event
    - Show spinner + "Envoi en cours…" between submit and first NDJSON event
    - Replace with ThinkingIndicator on first event
    - _Requirements: 23.1, 23.2_
  - [x] 16.5 Add streaming error display with retry button
    - Friendly localized error message, "Réessayer" button calling `retry()`
    - Preserve partial results above error
    - _Requirements: Req 16 AC1, Req 16 AC2, Req 16 AC3_
  - [x] 16.6 Wire `useTranslation` into ChatStream for all strings
    - Section headings, button labels, placeholder, helper text, error messages
    - _Requirements: 28.1_
  - [x] 16.7 Write property test: ChatStream preserves all previous turns (Property 7)
    - **Property 7: ChatStream preserves all previous turns**
    - For any sequence of 1–5 completed turns, all disease names are rendered and turn section count matches
    - **Validates: Requirements 11.1**

- [x] 17. Update TreatmentPlan: tab badge, tooltip, responsive, i18n
  - Active tab badge: `bg-blue-600 text-white` vs inactive `bg-muted`
  - Unavailable drug tooltip with `aria-describedby` (visible on hover/focus)
  - Dosage grid: 1 col on mobile, 2 cols on sm+
  - Use `useTranslation` for all labels
  - _Requirements: 21.1, 21.2, 22.1, 22.2, 28.3, 30.5_

- [x] 18. Update FeedbackPanel: use api.feedback.submit, error/retry, i18n
  - Replace raw `fetch` with `api.feedback.submit`
  - Add error state with inline error message and retry button
  - Use `useTranslation` for all labels
  - _Requirements: 15.1, 15.2, 28.5_

- [x] 19. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 20. Update clinic layout: responsive sidebar, skip link, breadcrumb, admin link, i18n
  - [x] 20.1 Implement responsive sidebar with hamburger menu
    - Hidden below md, hamburger button with inline SVG (24x24, `aria-hidden` on SVG, `aria-label` on button)
    - Hamburger button must include `aria-expanded` reflecting the sidebar open/closed state
    - Overlay with backdrop, `transition-transform duration-300 ease-in-out` slide-in
    - Close on backdrop click or nav link click
    - _Requirements: 18.1, 18.2, 18.3, 18.4, 18.5_
  - [x] 20.2 Add SkipLink as first child, `id="main-content"` on `<main>`
    - _Requirements: 32.1, 32.3_
  - [x] 20.3 Add Breadcrumb derived from `usePathname()` + route-to-label map
    - _Requirements: 19.1, 19.2_
  - [x] 20.4 Add conditional admin link based on user role
    - Show "Administration" link to `/admin/knowledge-base` when user has "admin" role
    - _Requirements: 20.1, 20.2_
  - [x] 20.5 Wire `useTranslation` into clinic layout for all nav labels
    - _Requirements: 29.1_

- [x] 21. Update admin layout: responsive sidebar, skip link, breadcrumb, i18n
  - Same responsive sidebar pattern as clinic layout (hamburger, overlay, transition)
  - SkipLink as first child, `id="main-content"` on `<main>`
  - Breadcrumb derived from `usePathname()` + route-to-label map
  - Use `useTranslation` for all labels
  - _Requirements: 30.8, 32.1, 19.1, 29.2_

- [x] 22. Update auth pages: remove html/body, Tailwind, server-side i18n
  - [x] 22.1 Refactor login page
    - Remove `<html>` and `<body>` tags
    - Replace all inline styles with Tailwind classes
    - Read `tropicare-lang` cookie via `getServerTranslation` for server-side i18n
    - Responsive: full-width on mobile
    - _Requirements: 5.1, 5.2, 5.3, 29.4, 30.7_
  - [x] 22.2 Refactor register page (same pattern as login)
    - _Requirements: 5.1, 5.2, 5.3, 29.4, 30.7_

- [x] 23. Update root layout: LangUpdater client component
  - Create `LangUpdater` client component that reads language from store and sets `document.documentElement.lang` via `useEffect`
  - Render as child of the Server Component root layout
  - _Requirements: 31.1_
  - [x] 23.1 Write property test: HTML lang attribute matches store language (Property 17)
    - **Property 17: HTML lang attribute matches store language**
    - For any language value ("fr" or "en"), after LangUpdater re-renders, `document.documentElement.lang` equals that value
    - **Validates: Requirements 31.1**

- [x] 24. Update sessions page: i18n, locale-aware date formatting, responsive
  - Use `useTranslation` for page title, empty state, labels
  - Import both `fr` and `en` locales from `date-fns/locale`, select based on active language
  - Responsive: full-width cards on mobile, date below query text
  - _Requirements: 29.3, 30.6_

- [x] 25. Wire i18n into remaining components
  - [x] 25.1 Update LoadingSkeleton components with i18n aria-labels
    - _Requirements: 29.6_
  - [x] 25.2 Update ErrorBoundary to extend localized messages for new error states
    - _Requirements: 29.5_

- [x] 26. Responsive polish and final layout adjustments
  - ChatStream input bar: stack vertically below 640px
  - Ensure no horizontal overflow at any viewport 320px–2560px
  - _Requirements: 30.3, 30.9_

- [x] 27. Checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 28. Write remaining unit tests
  - [x] 28.1 Write unit tests for CitationDrawer
    - Focus trap cycling, Escape closes, backdrop click closes, initial focus
    - _Requirements: 1.2, 1.3, 1.4, 1.5_
  - [x] 28.2 Write unit tests for IntakeForm
    - Inline validation on blur, error clearance, aria-describedby wiring, submission prevention, summary preview modal
    - _Requirements: 6.1, 6.2, 6.3, 6.4, 9.1_
  - [x] 28.3 Write unit tests for ChatStream
    - Enter inserts newline, Ctrl+Enter submits, auto-scroll behavior, scroll-to-bottom button, loading state transitions
    - _Requirements: 12.1, 12.2, 13.1, 13.2, 23.1_
  - [x] 28.4 Write unit tests for FeedbackPanel
    - Uses api.feedback.submit, error display with retry
    - _Requirements: 15.1, 15.2_
  - [x] 28.5 Write unit tests for TreatmentPlan
    - Active tab badge styling, unavailable drug tooltip, tooltip aria-describedby
    - _Requirements: 21.1, 22.1, 22.2_
  - [x] 28.6 Write unit tests for sidebar and breadcrumb
    - Admin link visibility based on role, hamburger button ARIA (including aria-expanded), breadcrumb route hierarchy, ARIA attributes
    - _Requirements: 18.5, 19.3, 20.1, 20.2_
  - [x] 28.7 Write unit tests for skip link and auth pages
    - Skip link visibility on focus, focus moves to main, auth pages have no html/body tags, use Tailwind
    - _Requirements: 32.1, 32.2, 32.3, 5.1, 5.2_

- [x] 29. Final checkpoint — Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties from the design document (17 properties total)
- Unit tests validate specific interactions and edge cases
- All code uses TypeScript with React 19, Next.js App Router, Tailwind CSS 4.2, and Zustand
