"use client";
import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import toast from "react-hot-toast";
import { billingApi } from "@/lib/api";
import { useAuthStore } from "@/lib/store";
import { cn } from "@/lib/utils";
import { CreditCard, Zap, CheckCircle, TrendingUp, Building2, ArrowRight } from "lucide-react";

const PLAN_ICONS: Record<string, React.ReactNode> = {
  starter: <Zap size={18} className="text-gray-500" />,
  growth:  <TrendingUp size={18} className="text-brand-500" />,
  agency:  <Building2 size={18} className="text-purple-500" />,
};

const PLAN_COLORS: Record<string, string> = {
  starter: "border-gray-200",
  growth:  "border-brand-400",
  agency:  "border-purple-400",
};

const CREDIT_TYPE_LABEL: Record<string, string> = {
  crawl: "Crawl",
  keyword: "Keyword / AI / Report",
  grant: "Credits granted",
  debit: "Credits used",
};

export default function BillingPage() {
  const { currentOrg } = useAuthStore();
  const qc = useQueryClient();
  const [upgrading, setUpgrading] = useState<string | null>(null);

  const { data: plans = [] } = useQuery<any[]>({
    queryKey: ["plans"],
    queryFn: async () => { const { data } = await billingApi.plans(); return data; },
  });

  const { data: usage } = useQuery<any>({
    queryKey: ["billing-usage"],
    queryFn: async () => { const { data } = await billingApi.usage(); return data; },
  });

  const devUpgrade = useMutation({
    mutationFn: (plan: string) => billingApi.devUpgrade(plan),
    onSuccess: (_, plan) => {
      qc.invalidateQueries({ queryKey: ["billing-usage"] });
      qc.invalidateQueries({ queryKey: ["me"] });
      toast.success(`Upgraded to ${plan} (dev mode)`);
      setUpgrading(null);
    },
    onError: () => toast.error("Upgrade failed"),
  });

  const checkout = useMutation({
    mutationFn: (plan: string) =>
      billingApi.checkout({ plan, base_url: window.location.origin }),
    onSuccess: (res) => {
      if (res.data.checkout_url) {
        window.location.href = res.data.checkout_url;
      } else {
        // Dev mode — use devUpgrade
        toast("Stripe not configured — using dev upgrade", { icon: "ℹ️" });
      }
      setUpgrading(null);
    },
    onError: () => toast.error("Checkout failed"),
  });

  const handleUpgrade = (plan: string) => {
    setUpgrading(plan);
    // Use dev upgrade directly since Stripe likely not configured
    devUpgrade.mutate(plan);
  };

  const currentPlan = usage?.plan ?? currentOrg?.plan ?? "starter";

  const crawlPct = usage
    ? Math.min(100, Math.round(
        ((usage.crawl_credits_total - usage.crawl_credits_remaining) / Math.max(usage.crawl_credits_total, 1)) * 100
      ))
    : 0;
  const kwPct = usage
    ? Math.min(100, Math.round(
        ((usage.keyword_credits_total - usage.keyword_credits_remaining) / Math.max(usage.keyword_credits_total, 1)) * 100
      ))
    : 0;

  return (
    <div className="max-w-4xl">
      <div className="mb-8">
        <h1 className="text-2xl font-semibold text-gray-900">Billing &amp; Credits</h1>
        <p className="text-sm text-gray-500 mt-1">
          Manage your subscription and monitor credit usage
        </p>
      </div>

      {/* Current usage */}
      {usage && (
        <div className="card p-6 mb-8">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-medium text-gray-900">Current plan</h2>
            <span className="badge bg-brand-100 text-brand-700 border border-brand-200 capitalize">
              {usage.plan_name}
            </span>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div>
              <div className="flex justify-between text-sm mb-1.5">
                <span className="text-gray-600">Crawl credits</span>
                <span className="font-medium text-gray-900">
                  {usage.crawl_credits_remaining.toLocaleString()} / {usage.crawl_credits_total.toLocaleString()}
                </span>
              </div>
              <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={cn("h-full rounded-full transition-all", crawlPct >= 90 ? "bg-red-500" : crawlPct >= 70 ? "bg-amber-500" : "bg-brand-500")}
                  style={{ width: `${crawlPct}%` }}
                />
              </div>
              <p className="text-xs text-gray-400 mt-1">{crawlPct}% used · resets monthly</p>
            </div>
            <div>
              <div className="flex justify-between text-sm mb-1.5">
                <span className="text-gray-600">Keyword &amp; AI credits</span>
                <span className="font-medium text-gray-900">
                  {usage.keyword_credits_remaining.toLocaleString()} / {usage.keyword_credits_total.toLocaleString()}
                </span>
              </div>
              <div className="h-2.5 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={cn("h-full rounded-full transition-all", kwPct >= 90 ? "bg-red-500" : kwPct >= 70 ? "bg-amber-500" : "bg-brand-500")}
                  style={{ width: `${kwPct}%` }}
                />
              </div>
              <p className="text-xs text-gray-400 mt-1">{kwPct}% used · resets monthly</p>
            </div>
          </div>
        </div>
      )}

      {/* Plans */}
      <h2 className="font-medium text-gray-900 mb-4">Available plans</h2>
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
        {plans.map((plan: any) => {
          const isCurrent = plan.id === currentPlan;
          return (
            <div
              key={plan.id}
              className={cn(
                "card p-5 relative",
                PLAN_COLORS[plan.id] ?? "border-gray-200",
                plan.id === "growth" ? "border-2" : "border"
              )}
            >
              {plan.id === "growth" && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="badge bg-brand-600 text-white text-xs px-3 py-1 shadow-sm">
                    Most popular
                  </span>
                </div>
              )}

              <div className="flex items-center gap-2 mb-3 mt-1">
                {PLAN_ICONS[plan.id]}
                <span className="font-semibold text-gray-900">{plan.name}</span>
              </div>

              <div className="mb-4">
                <span className="text-3xl font-bold text-gray-900">${plan.price_monthly}</span>
                <span className="text-gray-400 text-sm">/mo</span>
              </div>

              <ul className="space-y-2 mb-5 text-sm text-gray-600">
                {[
                  `${plan.crawl_credits.toLocaleString()} crawl credits`,
                  `${plan.keyword_credits.toLocaleString()} keyword credits`,
                  `${plan.ai_credits} AI briefs/month`,
                  `${plan.projects === -1 ? "Unlimited" : plan.projects} projects`,
                  `${plan.users} team members`,
                ].map((feat) => (
                  <li key={feat} className="flex items-center gap-2">
                    <CheckCircle size={14} className="text-green-500 flex-shrink-0" />
                    {feat}
                  </li>
                ))}
              </ul>

              {isCurrent ? (
                <div className="btn-secondary w-full justify-center cursor-default opacity-60 select-none">
                  Current plan
                </div>
              ) : (
                <button
                  className={cn(
                    "w-full justify-center",
                    plan.id === "growth" ? "btn-primary" : "btn-secondary"
                  )}
                  onClick={() => handleUpgrade(plan.id)}
                  disabled={upgrading === plan.id}
                >
                  {upgrading === plan.id ? "Upgrading…" : (
                    <>Upgrade to {plan.name} <ArrowRight size={14} /></>
                  )}
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Credit pricing */}
      <div className="card p-5 mb-8">
        <h2 className="font-medium text-gray-900 mb-3">Credit pricing</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-sm">
          {[
            { label: "Crawl", cost: "1 credit / 100 pages" },
            { label: "Keyword lookup", cost: "1 credit / 10 keywords" },
            { label: "AI brief", cost: "5 credits / brief" },
            { label: "PDF report", cost: "2 credits / report" },
          ].map(({ label, cost }) => (
            <div key={label} className="bg-gray-50 rounded-lg p-3">
              <p className="font-medium text-gray-700">{label}</p>
              <p className="text-xs text-gray-400 mt-0.5">{cost}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Recent transactions */}
      {usage?.recent_transactions?.length > 0 && (
        <div className="card">
          <div className="px-5 py-3 border-b border-gray-100">
            <h2 className="font-medium text-gray-900">Recent credit activity</h2>
          </div>
          <div className="divide-y divide-gray-50">
            {usage.recent_transactions.map((t: any, i: number) => (
              <div key={i} className="px-5 py-3 flex items-center justify-between">
                <div>
                  <p className="text-sm text-gray-700">{t.description || "Credit transaction"}</p>
                  <p className="text-xs text-gray-400 mt-0.5">
                    {t.credit_type} · {new Date(t.created_at).toLocaleDateString()}
                  </p>
                </div>
                <span className={cn(
                  "text-sm font-semibold",
                  t.amount > 0 ? "text-green-600" : "text-red-500"
                )}>
                  {t.amount > 0 ? "+" : ""}{t.amount.toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      <p className="text-xs text-gray-400 mt-6 text-center">
        Stripe not yet configured · Set <code className="bg-gray-100 px-1 rounded">STRIPE_SECRET_KEY</code> in{" "}
        <code className="bg-gray-100 px-1 rounded">.env</code> to enable real payment processing
      </p>
    </div>
  );
}
