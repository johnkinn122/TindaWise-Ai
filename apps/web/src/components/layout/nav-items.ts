import {
  BarChart3,
  Boxes,
  LayoutDashboard,
  MonitorSmartphone,
  Package,
  Truck,
  type LucideIcon,
} from "lucide-react";

export interface NavItem {
  href: string;
  label: string;
  icon: LucideIcon;
}

/** Primary navigation. Order follows a store owner's day: check, sell, stock, buy, review. */
export const navItems: NavItem[] = [
  { href: "/", label: "Overview", icon: LayoutDashboard },
  { href: "/sell", label: "Sell", icon: MonitorSmartphone },
  { href: "/products", label: "Products", icon: Package },
  { href: "/inventory", label: "Inventory", icon: Boxes },
  { href: "/suppliers", label: "Suppliers", icon: Truck },
  { href: "/reports", label: "Reports", icon: BarChart3 },
];
