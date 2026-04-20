/**
 * Unit tests for Sidebar and Breadcrumb components
 * Validates: Requirements 18.5, 19.3, 20.1, 20.2
 *
 * Tests admin link visibility based on role, hamburger button ARIA
 * (including aria-expanded), breadcrumb route hierarchy, ARIA attributes.
 */
import { render, screen, fireEvent } from "@testing-library/react"
import "@testing-library/jest-dom"
import { Breadcrumb, type BreadcrumbItem } from "@/components/ui/Breadcrumb"

// ── Mock useTranslation ───────────────────────────────────────────────────────
const translations: Record<string, string> = {
  "nav.consultation": "Consultation",
  "nav.history": "Historique",
  "nav.admin": "Administration",
  "nav.openMenu": "Ouvrir le menu",
  "nav.mainNav": "Navigation principale",
  "nav.logout": "Déconnexion",
  "nav.langFr": "Changer la langue en français",
  "nav.langEn": "Switch language to English",
  "nav.brand": "TropiCare",
  "breadcrumb.ariaLabel": "Fil d'Ariane",
}

jest.mock("@/lib/i18n", () => ({
  useTranslation: () => ({
    t: (key: string, params?: Record<string, string | number>) => {
      let val = translations[key] ?? key
      if (params) {
        Object.entries(params).forEach(([k, v]) => {
          val = val.replace(`{{${k}}}`, String(v))
        })
      }
      return val
    },
    locale: "fr" as const,
  }),
}))

// ── Mock store state ──────────────────────────────────────────────────────────
let mockStoreState: Record<string, unknown> = {}

jest.mock("@/lib/store", () => ({
  useAppStore: () => mockStoreState,
}))

// ── Mock Next.js navigation ───────────────────────────────────────────────────
let mockPathname = "/chat"

jest.mock("next/navigation", () => ({
  usePathname: () => mockPathname,
  useRouter: () => ({
    push: jest.fn(),
    replace: jest.fn(),
    back: jest.fn(),
  }),
}))

jest.mock("next/link", () => {
  return ({ children, href, ...props }: { children: React.ReactNode; href: string; [key: string]: unknown }) => (
    <a href={href} {...props}>{children}</a>
  )
})

// ── Mock ErrorBoundary and SkipLink ───────────────────────────────────────────
jest.mock("@/components/ErrorBoundary", () => ({
  ErrorBoundary: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}))

jest.mock("@/components/ui/SkipLink", () => ({
  SkipLink: () => <a href="#main-content">Skip</a>,
}))

jest.mock("@/components/ui/Breadcrumb", () => {
  const actual = jest.requireActual("@/components/ui/Breadcrumb")
  return actual
})

// ── Mock api ──────────────────────────────────────────────────────────────────
jest.mock("@/lib/api", () => ({
  api: {
    auth: { logout: jest.fn().mockResolvedValue(undefined) },
  },
}))

// ── Import layout after mocks ─────────────────────────────────────────────────
import ClinicLayout from "@/app/(clinic)/layout"

describe("Breadcrumb — ARIA attributes (Requirement 19.3)", () => {
  it("renders nav with aria-label='Fil d'Ariane'", () => {
    const items: BreadcrumbItem[] = [{ label: "Consultation" }]
    render(<Breadcrumb items={items} />)

    const nav = screen.getByRole("navigation", { name: "Fil d'Ariane" })
    expect(nav).toBeInTheDocument()
  })

  it("renders an ordered list inside the nav", () => {
    const items: BreadcrumbItem[] = [
      { label: "Home", href: "/" },
      { label: "Current Page" },
    ]
    render(<Breadcrumb items={items} />)

    const list = screen.getByRole("list")
    expect(list).toBeInTheDocument()
    expect(list.tagName).toBe("OL")
  })

  it("sets aria-current='page' on the last item", () => {
    const items: BreadcrumbItem[] = [
      { label: "Home", href: "/" },
      { label: "Current Page" },
    ]
    render(<Breadcrumb items={items} />)

    const lastItem = screen.getByText("Current Page")
    expect(lastItem).toHaveAttribute("aria-current", "page")
  })

  it("does not set aria-current on non-last items", () => {
    const items: BreadcrumbItem[] = [
      { label: "Home", href: "/" },
      { label: "Middle", href: "/middle" },
      { label: "Current" },
    ]
    render(<Breadcrumb items={items} />)

    const homeLink = screen.getByText("Home")
    expect(homeLink).not.toHaveAttribute("aria-current")

    const middleLink = screen.getByText("Middle")
    expect(middleLink).not.toHaveAttribute("aria-current")
  })

  it("renders links for items with href (except last)", () => {
    const items: BreadcrumbItem[] = [
      { label: "Home", href: "/" },
      { label: "Current" },
    ]
    render(<Breadcrumb items={items} />)

    const link = screen.getByText("Home")
    expect(link.tagName).toBe("A")
    expect(link).toHaveAttribute("href", "/")
  })

  it("renders nothing when items array is empty", () => {
    const { container } = render(<Breadcrumb items={[]} />)
    expect(container.innerHTML).toBe("")
  })
})

describe("Clinic Sidebar — Admin link visibility (Requirements 20.1, 20.2)", () => {
  beforeEach(() => {
    mockPathname = "/chat"
  })

  it("shows Administration link when user has admin role", () => {
    mockStoreState = {
      user: { id: "1", email: "admin@test.com", roles: ["admin"] },
      clearUser: jest.fn(),
      language: "fr",
      setLanguage: jest.fn(),
      sidebarOpen: false,
      toggleSidebar: jest.fn(),
    }

    render(<ClinicLayout><div>Content</div></ClinicLayout>)

    const adminLink = screen.getByRole("link", { name: "Administration" })
    expect(adminLink).toBeInTheDocument()
    expect(adminLink).toHaveAttribute("href", "/admin/knowledge-base")
  })

  it("does NOT show Administration link when user does not have admin role", () => {
    mockStoreState = {
      user: { id: "2", email: "clinician@test.com", roles: ["clinician"] },
      clearUser: jest.fn(),
      language: "fr",
      setLanguage: jest.fn(),
      sidebarOpen: false,
      toggleSidebar: jest.fn(),
    }

    render(<ClinicLayout><div>Content</div></ClinicLayout>)

    const adminLink = screen.queryByRole("link", { name: "Administration" })
    expect(adminLink).not.toBeInTheDocument()
  })

  it("does NOT show Administration link when user has no roles", () => {
    mockStoreState = {
      user: { id: "3", email: "noroles@test.com", roles: [] },
      clearUser: jest.fn(),
      language: "fr",
      setLanguage: jest.fn(),
      sidebarOpen: false,
      toggleSidebar: jest.fn(),
    }

    render(<ClinicLayout><div>Content</div></ClinicLayout>)

    const adminLink = screen.queryByRole("link", { name: "Administration" })
    expect(adminLink).not.toBeInTheDocument()
  })
})

describe("Clinic Sidebar — Hamburger button ARIA (Requirement 18.5)", () => {
  it("hamburger button has aria-label='Ouvrir le menu'", () => {
    mockStoreState = {
      user: { id: "1", email: "test@test.com", roles: [] },
      clearUser: jest.fn(),
      language: "fr",
      setLanguage: jest.fn(),
      sidebarOpen: false,
      toggleSidebar: jest.fn(),
    }

    render(<ClinicLayout><div>Content</div></ClinicLayout>)

    const hamburger = screen.getByRole("button", { name: "Ouvrir le menu" })
    expect(hamburger).toBeInTheDocument()
  })

  it("hamburger button has aria-expanded=false when sidebar is closed", () => {
    mockStoreState = {
      user: { id: "1", email: "test@test.com", roles: [] },
      clearUser: jest.fn(),
      language: "fr",
      setLanguage: jest.fn(),
      sidebarOpen: false,
      toggleSidebar: jest.fn(),
    }

    render(<ClinicLayout><div>Content</div></ClinicLayout>)

    const hamburger = screen.getByRole("button", { name: "Ouvrir le menu" })
    expect(hamburger).toHaveAttribute("aria-expanded", "false")
  })

  it("hamburger button has aria-expanded=true when sidebar is open", () => {
    mockStoreState = {
      user: { id: "1", email: "test@test.com", roles: [] },
      clearUser: jest.fn(),
      language: "fr",
      setLanguage: jest.fn(),
      sidebarOpen: true,
      toggleSidebar: jest.fn(),
    }

    render(<ClinicLayout><div>Content</div></ClinicLayout>)

    const hamburger = screen.getByRole("button", { name: "Ouvrir le menu" })
    expect(hamburger).toHaveAttribute("aria-expanded", "true")
  })

  it("hamburger button calls toggleSidebar on click", () => {
    const toggleSidebar = jest.fn()
    mockStoreState = {
      user: { id: "1", email: "test@test.com", roles: [] },
      clearUser: jest.fn(),
      language: "fr",
      setLanguage: jest.fn(),
      sidebarOpen: false,
      toggleSidebar,
    }

    render(<ClinicLayout><div>Content</div></ClinicLayout>)

    const hamburger = screen.getByRole("button", { name: "Ouvrir le menu" })
    fireEvent.click(hamburger)

    expect(toggleSidebar).toHaveBeenCalledTimes(1)
  })
})
