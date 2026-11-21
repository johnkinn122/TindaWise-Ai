import type { ReactNode } from "react";
import { Label } from "@/components/ui/label";

interface FormFieldProps {
  id: string;
  label: string;
  required?: boolean;
  hint?: string;
  error?: string;
  children: (describedBy: string | undefined) => ReactNode;
}

/**
 * Label above, helper or error text below, linked to the input with aria-describedby.
 * An error replaces the hint, so the person reads one message at a time.
 */
export function FormField({ id, label, required, hint, error, children }: FormFieldProps) {
  const messageId = error || hint ? `${id}-message` : undefined;
  return (
    // content-start: when a neighbour has hint text, don't stretch this field's rows to match.
    <div className="grid content-start gap-1.5">
      <Label htmlFor={id}>
        {label}
        {required && (
          <span className="text-destructive" aria-hidden="true">
            *
          </span>
        )}
      </Label>
      {children(messageId)}
      {error ? (
        <p id={messageId} className="text-[0.8125rem] text-destructive">
          {error}
        </p>
      ) : hint ? (
        <p id={messageId} className="text-[0.8125rem] text-muted-foreground">
          {hint}
        </p>
      ) : null}
    </div>
  );
}
