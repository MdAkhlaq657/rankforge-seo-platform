export default function AuthLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-screen bg-gradient-to-br from-brand-50 to-indigo-100 flex items-center justify-center p-4">
      <div className="w-full max-w-md">
        <div className="text-center mb-8">
          <div className="inline-flex items-center gap-2 mb-2">
            <div className="w-8 h-8 bg-brand-600 rounded-lg flex items-center justify-center">
              <svg width="18" height="18" viewBox="0 0 18 18" fill="none">
                <path d="M3 14L9 4L15 14H3Z" fill="white" />
              </svg>
            </div>
            <span className="text-xl font-semibold text-gray-900">RankForge</span>
          </div>
          <p className="text-sm text-gray-500">Professional SEO automation platform</p>
        </div>
        <div className="card p-8">{children}</div>
      </div>
    </div>
  );
}
