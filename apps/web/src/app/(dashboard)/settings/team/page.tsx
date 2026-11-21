import type { Metadata } from "next";
import { Suspense } from "react";
import { RoleNotice } from "@/components/auth/role-notice";
import { PageHeader } from "@/components/dashboard/page-header";
import { Panel } from "@/components/dashboard/panel";
import { ApiErrorState } from "@/components/products/api-error-state";
import { AddMemberForm } from "@/components/team/add-member-form";
import { Skeleton } from "@/components/ui/skeleton";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiUnavailableError, apiFetch } from "@/lib/api/client";
import { canManageTeam, getCurrentUser, type Role, roleLabels } from "@/lib/auth/current-user";

export const metadata: Metadata = {
  title: "Team",
};

interface Member {
  user_id: string;
  full_name: string;
  email: string;
  role: Role;
  is_active: boolean;
  joined_at: string;
}

export default function TeamPage() {
  return (
    <div className="grid max-w-4xl gap-5">
      <PageHeader title="Team" description="Who can sign in to your store, and what they can do." />
      <Suspense fallback={<Skeleton className="h-80 w-full" />}>
        <TeamContent />
      </Suspense>
    </div>
  );
}

async function TeamContent() {
  const me = await getCurrentUser();
  if (!canManageTeam(me.role)) {
    return <RoleNotice>Only the store owner can manage the team.</RoleNotice>;
  }

  let members: Member[];
  try {
    members = await apiFetch<Member[]>("/members");
  } catch (error) {
    if (error instanceof ApiUnavailableError) return <ApiErrorState retryHref="/settings/team" />;
    throw error;
  }

  return (
    <>
      <Panel title="Members">
        <Table>
          <TableHeader>
            <TableRow className="hover:bg-transparent">
              <TableHead className="pl-4 sm:pl-5">Name</TableHead>
              <TableHead className="hidden sm:table-cell">Email</TableHead>
              <TableHead className="pr-4 sm:pr-5">Role</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {members.map((member) => (
              <TableRow key={member.user_id}>
                <TableCell className="whitespace-normal pl-4 sm:pl-5">
                  <span className="font-medium">{member.full_name}</span>
                  {member.user_id === me.user.id && <span className="ml-1.5 text-muted-foreground">(you)</span>}
                  <div className="text-xs text-muted-foreground sm:hidden">{member.email}</div>
                </TableCell>
                <TableCell className="hidden text-muted-foreground sm:table-cell">{member.email}</TableCell>
                <TableCell className="pr-4 sm:pr-5">{roleLabels[member.role]}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </Panel>

      <Panel title="Add a team member">
        <div className="p-4 sm:p-5">
          <AddMemberForm />
        </div>
      </Panel>
    </>
  );
}
