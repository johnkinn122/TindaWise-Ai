"use client";

import type { ReactNode } from "react";
import { useState, useTransition } from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import type { FormState } from "@/lib/form-state";
import { cn } from "@/lib/utils";

interface ConfirmActionButtonProps {
  /** Button that opens the dialog. */
  trigger: ReactNode;
  triggerVariant?: "default" | "outline" | "destructive" | "ghost";
  title: string;
  description: ReactNode;
  confirmLabel: string;
  pendingLabel: string;
  cancelLabel?: string;
  destructive?: boolean;
  /** Server Action. On success it redirects or refreshes; on failure it returns the error. */
  action: () => Promise<FormState | void>;
}

/** An action that changes money or stock asks first (MASTER.md §5) and shows any refusal inline. */
export function ConfirmActionButton({
  trigger,
  triggerVariant = "outline",
  title,
  description,
  confirmLabel,
  pendingLabel,
  cancelLabel = "Go back",
  destructive = false,
  action,
}: ConfirmActionButtonProps) {
  const [open, setOpen] = useState(false);
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string>();

  function confirm() {
    setError(undefined);
    startTransition(async () => {
      const result = await action();
      if (result?.status === "error") setError(result.message);
      else setOpen(false);
    });
  }

  return (
    <AlertDialog open={open} onOpenChange={setOpen}>
      <AlertDialogTrigger asChild>
        <Button variant={triggerVariant}>{trigger}</Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>{title}</AlertDialogTitle>
          <AlertDialogDescription>{description}</AlertDialogDescription>
        </AlertDialogHeader>
        {error && (
          <p role="alert" className="text-sm text-destructive">
            {error}
          </p>
        )}
        <AlertDialogFooter>
          <AlertDialogCancel>{cancelLabel}</AlertDialogCancel>
          <AlertDialogAction
            onClick={(event) => {
              event.preventDefault();
              confirm();
            }}
            disabled={isPending}
            className={cn(destructive && "bg-destructive text-white hover:bg-destructive/90")}
          >
            {isPending ? pendingLabel : confirmLabel}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
