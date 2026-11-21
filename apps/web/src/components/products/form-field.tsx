import { type ReactNode, useId } from "react";
import { Label } from "@/components/ui/label";

interface FormFieldProps {
  /** Stable prefix for readability in the DOM; a React-generated suffix keeps it unique. */
  name: string;
  label: string;
  required?: boolean;
  hint?: string;
  error?: string;
  children: (field: { id: string; describedBy: string | undefined }) => ReactNode;
}

/**
 * Label above, helper or error text below, linked to the input with aria-describedby.
 * An error replaces the hint, so the person reads one message at a time.
 *
 * Ids come from useId(): with Cache Components, a previously visited page can stay in the DOM
 * (hidden by <Activity>), so a fixed id like "quantity" could exist twice and a label would
 * point at the hidden copy.
 */
export function FormField({ name, label, required, hint, error, children }: FormFieldProps) {
  const id = `${name}-${useId()}`;
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
      {children({ id, describedBy: messageId })}
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
