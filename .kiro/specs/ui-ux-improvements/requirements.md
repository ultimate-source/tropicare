# Requirements Document

## Introduction

Systematic UI/UX improvements to the TropiCare frontend — a clinical decision support system for tropical disease diagnosis in Togo. This feature addresses accessibility gaps, form UX deficiencies, streaming and chat experience issues, error handling weaknesses, navigation and layout problems, visual polish, state persistence, and full internationalization (i18n) across all components. The tech stack is Next.js 14+ (App Router), React 19, TypeScript, Tailwind CSS 4.2, and Zustand for state management.

## Glossary

- **TropiCare_Frontend**: The Next.js 14+ client application that clinicians use to interact with the TropiCare clinical decision support system
- **CitationDrawer**: A slide-in panel (fixed right, 320px wide) that displays sourced references for clinical assertions
- **IntakeForm**: The structured patient intake form with collapsible sections that produces a PatientContext object for the backend
- **Section_Component**: A collapsible container used within IntakeForm to group related fields (e.g., vital signs, lab results, clinical context)
- **DifferentialCard**: A card component displaying a ranked diagnosis item with confidence bar, evidence, and confirmatory tests
- **EmergencyBanner**: An alert banner displayed when the system detects critical or urgent clinical conditions (e.g., meningitis, severe malaria)
- **ChatStream**: The main consultation view that orchestrates streaming results, differential cards, treatment plans, emergency banners, and the input bar
- **ThinkingIndicator**: An animated indicator showing the AI reasoning chain during streaming analysis
- **TreatmentPlan**: A tabbed component displaying first-line, second-line, and alternative drug regimens with CAME availability and DDI warnings
- **FeedbackPanel**: A component allowing clinicians to rate diagnostic accuracy (correct, partial, incorrect) with optional notes
- **ErrorBoundary**: A React class component that catches rendering errors and displays a localized fallback UI
- **Sidebar**: The fixed 224px-wide navigation panel in the clinic layout containing nav links, language toggle, and user info
- **TagEditor**: An input component for adding/removing string tags (symptoms, allergies, travel history) via Enter key
- **Zustand_Store**: The client-side state management store (useAppStore) holding auth, session, language, and UI preferences
- **I18n_System**: The internationalization system providing translation dictionaries for French (fr) and English (en) with a hook-based API for component consumption
- **Api_Client**: The typed fetch wrapper (lib/api.ts) that handles authentication cookies, JSON serialization, and error responses for all backend calls
- **NDJSON_Stream**: The newline-delimited JSON streaming protocol used between the backend and frontend for progressive rendering of diagnostic results
- **Focus_Trap**: A keyboard accessibility pattern that constrains Tab/Shift+Tab focus cycling within a modal or drawer while it is open
- **Aria_Live_Region**: An ARIA attribute (aria-live="polite" or "assertive") that causes screen readers to announce dynamic content changes

## Requirements

### Requirement 1: CitationDrawer Accessibility

**User Story:** As a clinician using assistive technology, I want the citation drawer to behave as a proper modal panel, so that I can navigate it with keyboard alone and understand its state.

#### Acceptance Criteria

1. WHEN the CitationDrawer opens, THE CitationDrawer SHALL render a semi-transparent backdrop overlay behind the panel that dims the main content
2. WHEN the CitationDrawer is open, THE CitationDrawer SHALL implement a Focus_Trap that constrains Tab and Shift+Tab cycling within the drawer
3. WHEN the user presses the Escape key while the CitationDrawer is open, THE CitationDrawer SHALL close the drawer and return focus to the element that triggered it
4. WHEN the user clicks the backdrop overlay, THE CitationDrawer SHALL close the drawer
5. WHEN the CitationDrawer opens, THE CitationDrawer SHALL set focus on the first focusable element inside the drawer
6. THE CitationDrawer SHALL include role="dialog" and aria-modal="true" attributes on the drawer container

### Requirement 2: Collapsible Section Accessibility

**User Story:** As a clinician using a screen reader, I want collapsible sections to announce their expanded or collapsed state, so that I understand the form structure without visual cues.

#### Acceptance Criteria

1. THE Section_Component SHALL render the toggle button with an aria-expanded attribute set to "true" when the section is open and "false" when collapsed
2. THE Section_Component SHALL replace the text characters "▲" and "▼" with a CSS-based chevron icon that uses aria-hidden="true" so screen readers rely on the aria-expanded attribute instead
3. THE Section_Component SHALL associate the toggle button with the collapsible content region using aria-controls referencing the content panel id

### Requirement 3: DifferentialCard Expand/Collapse Accessibility

**User Story:** As a clinician using a screen reader, I want the differential diagnosis expand/collapse button to announce its state, so that I know whether details are visible.

#### Acceptance Criteria

1. THE DifferentialCard expand/collapse button SHALL include an aria-expanded attribute set to "true" when expanded and "false" when collapsed
2. THE DifferentialCard SHALL replace the text characters "▲" and "▼" with a CSS-based chevron icon that uses aria-hidden="true" so screen readers rely on the aria-expanded attribute instead
3. THE DifferentialCard confidence bar SHALL include an aria-label attribute describing the confidence percentage (e.g., "Confiance : 85%")
4. THE DifferentialCard confidence bar SHALL include role="meter", aria-valuemin="0", aria-valuemax="100", and aria-valuenow set to the confidence percentage

### Requirement 4: EmergencyBanner Dismissal Announcement

**User Story:** As a clinician using a screen reader, I want to be informed when an emergency alert is dismissed, so that I have confirmation my acknowledgment was registered.

#### Acceptance Criteria

1. WHEN the clinician dismisses an EmergencyBanner, THE ChatStream SHALL announce the dismissal through an Aria_Live_Region with aria-live="polite"
2. THE Aria_Live_Region announcement SHALL include the disease name that was dismissed (e.g., "Alerte paludisme grave prise en compte")

### Requirement 5: Auth Pages Layout Compliance

**User Story:** As a developer, I want the login and register pages to use the root layout instead of rendering their own html and body tags, so that the pages do not conflict with the Next.js App Router root layout.

#### Acceptance Criteria

1. THE login page and register page SHALL NOT render their own html or body elements
2. THE login page and register page SHALL use Tailwind CSS classes consistent with the rest of the TropiCare_Frontend instead of inline style attributes
3. THE login page and register page SHALL inherit the root layout font and base styles from the app/layout.tsx root layout

### Requirement 6: IntakeForm Inline Validation

**User Story:** As a clinician, I want to see validation errors next to the specific fields that have problems, so that I can correct mistakes without scrolling to the top of the form.

#### Acceptance Criteria

1. WHEN a required field is left empty and the field loses focus, THE IntakeForm SHALL display an inline error message directly below that field
2. WHEN the clinician corrects an invalid field, THE IntakeForm SHALL remove the inline error message for that field immediately
3. THE IntakeForm SHALL associate each inline error message with its field using aria-describedby referencing the error element id
4. THE IntakeForm SHALL mark invalid fields with aria-invalid="true"
5. THE IntakeForm SHALL continue to prevent form submission when required fields are empty or invalid

### Requirement 7: TagEditor Visual Affordance

**User Story:** As a clinician, I want a clear visual hint that pressing Enter adds a tag, so that I discover the interaction without guessing.

#### Acceptance Criteria

1. THE TagEditor input field SHALL display a persistent helper text below the input indicating "Appuyez sur Entrée pour ajouter" (or the English equivalent based on the active language)
2. THE TagEditor helper text SHALL be associated with the input using aria-describedby

### Requirement 8: Vital Signs Responsive Grid

**User Story:** As a clinician using a tablet, I want the vital signs grid to adapt to smaller screens, so that fields remain readable and usable without horizontal scrolling.

#### Acceptance Criteria

1. THE IntakeForm vital signs grid SHALL use responsive Tailwind breakpoints: 2 columns by default (below 640px), 3 columns at the sm breakpoint (640px and above), and 4 columns at the lg breakpoint (1024px and above)
2. WHILE the viewport width is below 640px, THE IntakeForm vital signs fields SHALL each occupy at least 50% of the available width

### Requirement 9: Consultation Summary Preview

**User Story:** As a clinician, I want to review a summary of the patient data before submitting the consultation, so that I can catch data entry errors before the analysis begins.

#### Acceptance Criteria

1. WHEN the clinician clicks the submit button on the IntakeForm, THE IntakeForm SHALL display a modal summary preview of all entered patient data before initiating the session creation API call
2. THE summary preview SHALL display all mandatory fields (age, sex, region, chief complaint) and all filled optional fields (weight, vital signs, lab results, medications, allergies, travel history, pregnancy status, symptom onset, symptoms)
3. THE summary preview SHALL provide a "Confirmer" button to proceed with submission and a "Modifier" button to return to the form
4. THE summary preview modal SHALL implement Focus_Trap and close on Escape key press

### Requirement 10: ThinkingIndicator Expandable Reasoning

**User Story:** As a clinician, I want to see the full AI reasoning chain, so that I can understand the complete diagnostic thought process rather than only the last two lines.

#### Acceptance Criteria

1. THE ThinkingIndicator SHALL display all reasoning lines in a scrollable container instead of truncating to the last 2 lines
2. THE ThinkingIndicator SHALL have a maximum height of 200px with vertical overflow scrolling
3. WHEN new reasoning lines arrive during streaming, THE ThinkingIndicator SHALL auto-scroll to the bottom to show the latest line
4. THE ThinkingIndicator SHALL provide a toggle button to expand the container to show the full reasoning chain without a height constraint

### Requirement 11: Conversation History Persistence

**User Story:** As a clinician, I want previous turn results to remain visible when I ask follow-up questions, so that I can reference earlier diagnoses during the consultation.

#### Acceptance Criteria

1. WHEN the clinician submits a follow-up query, THE ChatStream SHALL preserve all previous turn results (differential cards, treatment plans, emergency banners, feedback panels) above the new streaming results
2. THE ChatStream SHALL visually separate each turn with a divider or turn header indicating the turn number or query text
3. THE ChatStream SHALL maintain the full conversation history for the duration of the session

### Requirement 12: Textarea Submit Behavior

**User Story:** As a clinician writing multi-line clinical descriptions, I want Enter to create a new line by default, so that I do not accidentally submit incomplete text.

#### Acceptance Criteria

1. WHEN the clinician presses Enter in the ChatStream textarea, THE ChatStream SHALL insert a newline character instead of submitting the form
2. WHEN the clinician presses Ctrl+Enter (or Cmd+Enter on macOS) in the ChatStream textarea, THE ChatStream SHALL submit the form
3. THE ChatStream SHALL display a helper text below the textarea indicating the submit shortcut (e.g., "Ctrl+Entrée pour envoyer")

### Requirement 13: Auto-Scroll on Streaming Content

**User Story:** As a clinician, I want the chat view to automatically scroll to the bottom when new streaming content arrives, so that I always see the latest results without manual scrolling.

#### Acceptance Criteria

1. WHEN new streaming content (thinking lines, differential items, treatment lines) arrives, THE ChatStream scrollable container SHALL auto-scroll to the bottom
2. WHEN the clinician has manually scrolled up to review earlier content, THE ChatStream SHALL NOT auto-scroll and SHALL display a "scroll to bottom" button
3. WHEN the clinician clicks the "scroll to bottom" button, THE ChatStream SHALL scroll to the bottom and resume auto-scrolling

### Requirement 14: CitationDrawer Search and Filter

**User Story:** As a clinician, I want to search and filter citations within the drawer, so that I can quickly find the specific source I need among many references.

#### Acceptance Criteria

1. THE CitationDrawer SHALL provide a text search input at the top of the citation list
2. WHEN the clinician types in the search input, THE CitationDrawer SHALL filter the displayed citations to show only those whose source_title, section, or chunk_snippet contain the search text (case-insensitive)
3. WHEN the search input is cleared, THE CitationDrawer SHALL display all citations
4. THE CitationDrawer SHALL display the count of matching citations out of the total (e.g., "3 / 12 sources")

### Requirement 15: FeedbackPanel Api_Client Usage

**User Story:** As a developer, I want the FeedbackPanel to use the shared Api_Client instead of raw fetch, so that authentication headers and error handling are consistent across the application.

#### Acceptance Criteria

1. THE FeedbackPanel SHALL use the api.feedback.submit method from the Api_Client instead of calling fetch directly
2. IF the feedback submission fails, THEN THE FeedbackPanel SHALL display a user-friendly error message with a retry button instead of failing silently

### Requirement 16: Streaming Error Messages

**User Story:** As a clinician, I want friendly error messages when network errors occur during streaming, so that I understand what happened and can take action.

#### Acceptance Criteria

1. IF a network error occurs during NDJSON_Stream processing, THEN THE ChatStream SHALL display a localized, user-friendly error message instead of the raw error string
2. THE error message SHALL include a "Réessayer" (Retry) button that re-sends the last query
3. IF the streaming connection is lost mid-response, THEN THE ChatStream SHALL preserve any partial results already rendered and display the error below them

### Requirement 17: API Failure Retry Pattern

**User Story:** As a clinician, I want a retry option when API calls fail outside of streaming, so that I can recover from transient network issues without reloading the page.

#### Acceptance Criteria

1. WHEN an API call fails in a non-streaming context (session creation, session list, feedback submission), THE TropiCare_Frontend SHALL display a localized error message with a "Réessayer" button
2. WHEN the clinician clicks the retry button, THE TropiCare_Frontend SHALL re-attempt the failed API call
3. THE error display SHALL include a categorized error type (network, authentication, server) derived from the HTTP status code to help the clinician understand the failure

### Requirement 18: Responsive Sidebar

**User Story:** As a clinician using a tablet, I want the sidebar to collapse on smaller screens, so that the main content area has sufficient space for clinical data.

#### Acceptance Criteria

1. WHILE the screen width is below 768px (md breakpoint), THE Sidebar SHALL be hidden by default and accessible via a hamburger menu button
2. WHEN the clinician clicks the hamburger menu button, THE Sidebar SHALL slide in as an overlay with a backdrop
3. WHEN the clinician clicks the backdrop or a navigation link, THE Sidebar SHALL close
4. WHILE the screen width is 768px or wider, THE Sidebar SHALL remain visible in its fixed 224px layout
5. THE hamburger menu button SHALL include aria-label="Ouvrir le menu" and aria-expanded reflecting the sidebar state

### Requirement 19: Breadcrumb Navigation

**User Story:** As a clinician, I want a breadcrumb trail showing my current location in the application, so that I always know where I am and can navigate back easily.

#### Acceptance Criteria

1. THE TropiCare_Frontend SHALL display a breadcrumb navigation bar below the page header in the clinic and admin layouts
2. THE breadcrumb SHALL reflect the current route hierarchy (e.g., "Consultation" > "Session abc123" or "Admin" > "Base de connaissances")
3. THE breadcrumb SHALL use a nav element with aria-label="Fil d'Ariane" and an ordered list with aria-current="page" on the last item

### Requirement 20: Admin Link Visibility from Clinic Layout

**User Story:** As an admin-clinician, I want to access the admin section from the clinic sidebar, so that I do not need to manually type the URL.

#### Acceptance Criteria

1. WHEN the logged-in user has the "admin" role, THE Sidebar in the clinic layout SHALL display an "Administration" navigation link pointing to /admin/knowledge-base
2. WHEN the logged-in user does not have the "admin" role, THE Sidebar SHALL NOT display the admin link

### Requirement 21: TreatmentPlan Tab Count Badge Prominence

**User Story:** As a clinician, I want the active tab's drug count badge to be visually prominent, so that I can quickly see how many regimens are in the selected treatment line.

#### Acceptance Criteria

1. WHEN a TreatmentPlan tab is active, THE tab count badge SHALL use a high-contrast style (e.g., white text on blue background) distinct from the muted style of inactive tab badges
2. WHEN a TreatmentPlan tab is inactive, THE tab count badge SHALL use a muted, low-contrast style

### Requirement 22: Unavailable Drug Regimen Tooltip

**User Story:** As a clinician, I want to understand why a drug regimen appears dimmed, so that I know it is unavailable in the CAME formulary.

#### Acceptance Criteria

1. WHEN a DrugRegimen has came_available set to false, THE TreatmentPlan RegimenCard SHALL display a tooltip on hover explaining "Non disponible dans le formulaire CAME" (or the English equivalent based on the active language)
2. THE tooltip SHALL be accessible via keyboard focus using an aria-describedby attribute referencing a visually hidden tooltip element that becomes visible on hover and focus

### Requirement 23: Loading State Between Submit and First Stream Event

**User Story:** As a clinician, I want to see a loading indicator after clicking "Envoyer" and before the first streaming event arrives, so that I know the system is processing my request.

#### Acceptance Criteria

1. WHEN the clinician submits a query and before the first NDJSON_Stream event is received, THE ChatStream SHALL display a loading indicator (spinner with text "Envoi en cours…")
2. WHEN the first streaming event arrives, THE ChatStream SHALL replace the loading indicator with the ThinkingIndicator

### Requirement 24: Zustand Store Persistence

**User Story:** As a clinician, I want my session, authentication state, and language preference to survive a page refresh, so that I do not lose my work or need to log in again.

#### Acceptance Criteria

1. THE Zustand_Store SHALL persist the session and language fields to localStorage using Zustand's persist middleware
2. THE Zustand_Store SHALL persist the user and token fields to sessionStorage (not localStorage) to limit exposure to XSS attacks, since JWT tokens are sensitive credentials
3. WHEN the page is refreshed within the same browser tab, THE Zustand_Store SHALL rehydrate the persisted state from sessionStorage (auth) and localStorage (preferences)
4. WHEN the clinician logs out, THE Zustand_Store SHALL clear all persisted state from both sessionStorage and localStorage

### Requirement 25: Dismissed Emergency Alerts Persistence

**User Story:** As a clinician, I want dismissed emergency alerts to remain dismissed after a page refresh within the same session, so that acknowledged alerts do not reappear.

#### Acceptance Criteria

1. THE ChatStream SHALL persist the list of dismissed emergency alert disease names to the Zustand_Store
2. WHEN the page is refreshed within the same session, THE ChatStream SHALL read the dismissed list from the Zustand_Store and suppress those alerts
3. WHEN a new session is created, THE dismissed alerts list SHALL be cleared

### Requirement 26: Internationalization System Setup

**User Story:** As a developer, I want a structured i18n system with translation dictionaries for French and English, so that all UI text can be translated without hardcoding strings in components.

#### Acceptance Criteria

1. THE I18n_System SHALL provide translation dictionaries for French (fr) and English (en) covering all user-facing strings in the TropiCare_Frontend
2. THE I18n_System SHALL provide a React hook (e.g., useTranslation) that returns a translation function accepting a dot-notation key and returning the localized string for the active language
3. THE I18n_System SHALL read the active language from the Zustand_Store language field
4. IF a translation key is missing for the active language, THEN THE I18n_System SHALL fall back to the French (fr) translation
5. THE I18n_System SHALL support interpolation of dynamic values within translation strings (e.g., "{{count}} sources" resolving to "3 sources")

### Requirement 27: IntakeForm Internationalization

**User Story:** As a clinician who speaks English, I want the intake form to display all labels, placeholders, options, and error messages in my selected language, so that I can use the system comfortably.

#### Acceptance Criteria

1. THE IntakeForm SHALL use the I18n_System for all field labels, placeholder texts, section titles, button labels, validation error messages, and option labels (regions, pregnancy status, sex)
2. WHEN the active language changes, THE IntakeForm SHALL re-render all text in the newly selected language without requiring a page reload

### Requirement 28: ChatStream and Results Internationalization

**User Story:** As a clinician who speaks English, I want the chat interface, differential cards, treatment plan, emergency banners, and feedback panel to display in my selected language.

#### Acceptance Criteria

1. THE ChatStream SHALL use the I18n_System for all static labels including section headings ("Diagnostic différentiel", "Plan thérapeutique"), button labels ("Envoyer", "Arrêter"), placeholder text, and helper text
2. THE DifferentialCard SHALL use the I18n_System for labels including "Signes d'alarme", "Arguments pour", "Arguments contre", "Examens complémentaires", and priority/availability labels
3. THE TreatmentPlan SHALL use the I18n_System for tab labels ("1ère ligne", "2ème ligne", "Alternatives"), field labels ("Dose", "Voie", "Fréquence", "Durée"), and status labels ("CAME ✓", "CAME ✗", "Grossesse", "Contre-indiqués")
4. THE EmergencyBanner SHALL use the I18n_System for "URGENCE VITALE", "URGENCE", and the dismiss button label "Pris en compte"
5. THE FeedbackPanel SHALL use the I18n_System for the question text, verdict button labels ("Correcte", "Partielle", "Incorrecte"), placeholder text, submit button label, and confirmation message
6. THE ThinkingIndicator SHALL use the I18n_System for the "Analyse en cours" label

### Requirement 29: Navigation and Layout Internationalization

**User Story:** As a clinician who speaks English, I want the sidebar navigation, admin layout, session history, login page, and all layout chrome to display in my selected language.

#### Acceptance Criteria

1. THE Sidebar in the clinic layout SHALL use the I18n_System for navigation labels ("Consultation", "Historique"), the logout button label ("Déconnexion"), and language toggle aria-labels
2. THE admin layout SHALL use the I18n_System for navigation labels ("Base de connaissances", "Analytiques") and the "Retour" link
3. THE sessions page SHALL use the I18n_System for the page title ("Historique des consultations"), empty state message, and relative date formatting locale
4. THE login page SHALL determine the active language from a cookie or URL parameter (since it is a Server Component that cannot use React hooks), and pass it to the I18n_System for server-side rendering
5. THE ErrorBoundary SHALL continue to use its existing localized messages object and extend it to cover any new error states added by these improvements
6. THE LoadingSkeleton components SHALL use the I18n_System for all aria-label values ("Chargement en cours", "Chargement du contenu", "Chargement de la carte")

### Requirement 30: Responsive Page Layouts

**User Story:** As a clinician using a tablet or mobile device, I want all pages and content areas to adapt fluidly to my screen size, so that I can use TropiCare comfortably on any device without horizontal scrolling or truncated content.

#### Acceptance Criteria

1. THE IntakeForm mandatory fields grid SHALL use responsive Tailwind breakpoints: 1 column by default (below 640px), 2 columns at the sm breakpoint (640px and above), and 3 columns at the lg breakpoint (1024px and above)
2. THE IntakeForm two-column grid (region + symptom onset) SHALL stack to 1 column by default (below 640px)
3. THE ChatStream input bar SHALL stack the citation link, textarea, and submit button vertically by default (below 640px)
4. THE DifferentialCard header row SHALL wrap the confidence bar below the disease name by default (below 640px) instead of truncating
5. THE TreatmentPlan RegimenCard dosage grid SHALL switch from 2 columns to 1 column by default (below 640px)
6. THE sessions history page cards SHALL use full-width layout by default (below 640px) with the date displayed below the query text instead of beside it
7. THE login page form SHALL use a max-width of 100% with horizontal padding by default (below 640px) instead of the fixed 24rem max-width
8. THE admin layout sidebar SHALL follow the same responsive collapse behavior as the clinic Sidebar defined in Requirement 18
9. ALL pages SHALL have no horizontal overflow or horizontal scrollbar at any viewport width from 320px to 2560px

### Requirement 31: Root Layout Dynamic Language

**User Story:** As a clinician, I want the HTML lang attribute to reflect my selected language, so that screen readers and browser features use the correct language context.

#### Acceptance Criteria

1. WHEN the active language in the Zustand_Store changes, THE root layout html element SHALL update its lang attribute to match (either "fr" or "en")

### Requirement 32: Skip-to-Content Link

**User Story:** As a clinician using keyboard navigation, I want a skip-to-content link at the top of each page, so that I can bypass the sidebar navigation and jump directly to the main content area.

#### Acceptance Criteria

1. THE clinic layout and admin layout SHALL render a visually hidden anchor link as the first focusable element in the DOM with text "Aller au contenu principal" (or the English equivalent based on the active language)
2. WHEN the skip link receives keyboard focus, THE skip link SHALL become visible on screen
3. WHEN the clinician activates the skip link, THE browser focus SHALL move to the main content area (the main element)
4. THE skip link SHALL use the I18n_System for its label text

### Requirement 33: Focus-Visible Styles

**User Story:** As a clinician using keyboard navigation, I want all interactive elements to display a visible focus indicator when focused via keyboard, so that I can track my position on the page.

#### Acceptance Criteria

1. ALL interactive elements (buttons, links, inputs, selects, textareas) in the TropiCare_Frontend SHALL display a visible focus ring when focused via keyboard (using the :focus-visible pseudo-class)
2. THE focus ring style SHALL use a 2px solid outline with a color that meets WCAG 2.1 AA contrast requirements against the element's background (e.g., blue-500 on white backgrounds, white on blue backgrounds)
3. THE focus ring SHALL NOT appear on mouse click (using :focus-visible rather than :focus to avoid visual noise for mouse users)
