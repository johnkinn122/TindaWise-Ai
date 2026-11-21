import { BrandMark } from "@/components/layout/brand-mark";

/** Sign-in and sign-up: no app shell, one focused card. */
export default function AuthLayout({ children }: LayoutProps<"/">) {
  return (
    <main id="main" className="grid min-h-dvh place-items-center px-4 py-10">
      <div className="w-full max-w-md">
        <div className="mb-6 flex justify-center">
          <BrandMark />
        </div>
        <div className="rounded-lg border border-border bg-card p-6 sm:p-8">{children}</div>
      </div>
    </main>
  );
}
