"use client";
import { use, useEffect } from "react";
import { useRouter } from "next/navigation";

export default function LinkBuildingRedirect({ params }: { params: { id: string } }) {
  const { id } = params;
  const router = useRouter();
  useEffect(() => {
    router.replace(`/projects/${id}/competitors`);
  }, [id, router]);
  return null;
}
