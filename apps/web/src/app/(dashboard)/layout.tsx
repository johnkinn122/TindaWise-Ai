import { AppSidebar } from "@/components/layout/app-sidebar";
import { TopBar } from "@/components/layout/top-bar";

/**
 * App shell for every signed-in screen: sidebar + top bar + main content.
 * The (dashboard) folder is a route group — it shares this layout without adding to the URL.
 */
export default function DashboardLayout({ children }: LayoutProps<"/">) {
  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-[60] focus:rounded-sm focus:bg-card focus:px-3 focus:py-2 focus:shadow-float"
      >
        Skip to main content
      </a>
      <div className="flex min-h-dvh">
        <AppSidebar />
        <div className="flex min-w-0 flex-1 flex-col">
          <TopBar />
          <main id="main" tabIndex={-1} className="mx-auto w-full max-w-[1440px] flex-1 p-4 outline-none sm:p-6">
            {children}
          </main>
        </div>
      </div>
    </>
  );
}
