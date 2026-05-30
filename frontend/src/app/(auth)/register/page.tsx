"use client";
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import toast from "react-hot-toast";
import { authApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { MeResponse, TokenResponse } from "@/types";

export default function RegisterPage() {
  const router = useRouter();
  const { setTokens, setAuth } = useAuthStore();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    full_name: "", email: "", password: "", org_name: "",
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    // if (form.password.length < 8) {
    //   toast.error("Password must be at least 8 characters");
    //   return;
    // }
    setLoading(true);
    try {
      const { data: tokens } = await authApi.register(form) as { data: TokenResponse };
      setTokens(tokens.access_token, tokens.refresh_token);
      const { data: me } = await authApi.me() as { data: MeResponse };
      setAuth(me.user, me.current_org, me.organizations);
      toast.success("Account created! Welcome to RankForge.");
      router.push("/dashboard");
    } catch (err: any) {
      toast.error(err.response?.data?.detail ?? "Registration failed");
    } finally {
      setLoading(false);
    }
  };

  const f = (k: keyof typeof form) => ({
    value: form[k],
    onChange: (e: React.ChangeEvent<HTMLInputElement>) => setForm({ ...form, [k]: e.target.value }),
  });

  return (
    <>
      <h1 className="text-2xl font-semibold text-gray-900 mb-1">Create your account</h1>
      <p className="text-sm text-gray-500 mb-6">Start your free SEO platform today</p>

      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">Full name</label>
          <input type="text" className="input" placeholder="Jane Smith" {...f("full_name")} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Organization name <span className="text-red-500">*</span>
          </label>
          <input type="text" className="input" placeholder="My SEO Agency" required {...f("org_name")} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Email <span className="text-red-500">*</span>
          </label>
          <input type="email" className="input" placeholder="jane@agency.com" required {...f("email")} />
        </div>
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-1">
            Password <span className="text-red-500">*</span>
          </label>
          <input type="password" className="input" placeholder="Min. 8 characters" required {...f("password")} />
        </div>
        <button type="submit" className="btn-primary w-full justify-center" disabled={loading}>
          {loading ? "Creating account…" : "Create account"}
        </button>
      </form>

      <p className="text-center text-sm text-gray-500 mt-6">
        Already have an account?{" "}
        <Link href="/login" className="text-brand-600 font-medium hover:underline">
          Sign in
        </Link>
      </p>
    </>
  );
}
