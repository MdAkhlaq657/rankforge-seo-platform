"use client";
import { useEffect } from "react";
import { useRouter } from "next/navigation";
import Cookies from "js-cookie";
import { useQuery } from "@tanstack/react-query";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { MeResponse } from "@/types";
import Sidebar from "@/components/layout/Sidebar";

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const { setAuth, isLoaded } = useAuthStore();

  const { data, isError, isLoading } = useQuery<MeResponse>({
    queryKey: ["me"],
    queryFn: async () => {
      const { data } = await authApi.me();
      return data;
    },
    retry: false,
    enabled: !!Cookies.get("access_token"),
  });

  useEffect(() => {
    if (!Cookies.get("access_token")) {
      router.replace("/login");
      return;
    }
    if (isError) {
      router.replace("/login");
    }
    if (data) {
      setAuth(data.user, data.current_org, data.organizations);
    }
  }, [data, isError, router, setAuth]);

  if (isLoading || !isLoaded) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="flex items-center gap-3 text-gray-400">
          <div className="w-5 h-5 border-2 border-brand-500 border-t-transparent rounded-full animate-spin" />
          <span className="text-sm">Loading…</span>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Sidebar />
      <main className="ml-60 min-h-screen">
        <div className="max-w-7xl mx-auto px-6 py-8">
          {children}
        </div>
      </main>
    </div>
  );
}
