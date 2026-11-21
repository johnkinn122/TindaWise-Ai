import { Lock } from "lucide-react";

/** Shown where a role can't act. The API refuses these actions too; this just explains it. */
export function RoleNotice({ children }: { children: React.ReactNode }) {
  return (
    <p className="flex items-start gap-2 rounded-sm bg-muted px-3 py-2.5 text-sm text-muted-foreground">
      <Lock className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
      <span>{children}</span>
    </p>
  );
}
