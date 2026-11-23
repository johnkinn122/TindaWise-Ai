import { fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { LoginForm } from "@/components/auth/login-form";

const wakeApiAction = vi.fn();
vi.mock("@/app/(auth)/actions", () => ({
  loginAction: vi.fn(),
  wakeApiAction: () => wakeApiAction(),
}));
vi.mock("next/navigation", () => ({
  useSearchParams: () => new URLSearchParams(),
}));

const demo = {
  accounts: [
    { email: "owner@example.com", label: "Owner" },
    { email: "cashier@example.com", label: "Cashier" },
  ],
  password: "tindawise-demo",
};

describe("LoginForm on the public demo", () => {
  beforeEach(() => wakeApiAction.mockReset());

  it("lists the demo accounts and fills the form with one click", () => {
    render(<LoginForm demo={demo} />);
    expect(screen.getByRole("heading", { name: "Demo accounts" })).toBeInTheDocument();
    expect(screen.getByText("tindawise-demo")).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "Use cashier@example.com" }));
    expect(screen.getByRole("textbox", { name: "Email" })).toHaveValue("cashier@example.com");
    expect(screen.getByLabelText("Password")).toHaveValue("tindawise-demo");
    expect(screen.getByRole("button", { name: "Sign in" })).toHaveFocus();
  });

  it("starts waking the API and explains the wait, with no sign-up link", () => {
    render(<LoginForm demo={demo} />);
    expect(wakeApiAction).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/first sign-in can take up to a minute/)).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Create an account" })).not.toBeInTheDocument();
  });
});

describe("LoginForm outside the demo", () => {
  beforeEach(() => wakeApiAction.mockReset());

  it("offers sign-up and doesn't list accounts or wake anything", () => {
    render(<LoginForm />);
    expect(screen.getByRole("link", { name: "Create an account" })).toHaveAttribute("href", "/signup");
    expect(screen.queryByRole("heading", { name: "Demo accounts" })).not.toBeInTheDocument();
    expect(wakeApiAction).not.toHaveBeenCalled();
  });
});
