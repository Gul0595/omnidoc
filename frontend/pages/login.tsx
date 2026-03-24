import { useState, useEffect } from "react";
import { Loader2 } from "lucide-react";
import { login, register, isLoggedIn } from "../hooks/useApi";

export default function LoginPage() {
  const [mode, setMode]       = useState<"login" | "register">("login");
  const [form, setForm]       = useState({ email: "", password: "", full_name: "", organisation: "" });
  const [loading, setLoading] = useState(false);
  const [error, setError]     = useState("");

  useEffect(() => {
    if (isLoggedIn()) window.location.href = "/";
  }, []);

  const handle = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError("");
    try {
      if (mode === "login") {
        await login(form.email, form.password);
      } else {
        if (!form.full_name.trim()) { setError("Full name is required"); setLoading(false); return; }
        await register(form);
      }
      window.location.href = "/";
    } catch (err: any) {
      setError(err?.response?.data?.detail || "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const f = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm(prev => ({ ...prev, [k]: e.target.value }));

  const inputClass = "w-full px-3 py-2.5 border border-gray-200 dark:border-gray-700 rounded-lg text-sm bg-white dark:bg-gray-800 dark:text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-blue-400 transition";

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 to-blue-50 dark:from-gray-950 dark:to-gray-900 flex items-center justify-center p-4">
      <div className="w-full max-w-sm">

        {/* Logo */}
        <div className="text-center mb-8">
          <div className="w-12 h-12 bg-blue-600 rounded-2xl flex items-center justify-center mx-auto mb-3 shadow-lg">
            <span className="text-white font-bold text-xl">O</span>
          </div>
          <h1 className="text-2xl font-semibold text-gray-900 dark:text-white">OmniDoc</h1>
          <p className="text-sm text-gray-500 mt-1">Multi-sector document intelligence</p>
        </div>

        {/* Card */}
        <div className="bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800 shadow-sm p-6">

          {/* Tab toggle */}
          <div className="flex rounded-xl overflow-hidden border border-gray-200 dark:border-gray-700 mb-5">
            {(["login", "register"] as const).map(m => (
              <button key={m} onClick={() => { setMode(m); setError(""); }}
                className={`flex-1 py-2 text-sm font-medium transition-colors ${
                  mode === m
                    ? "bg-blue-600 text-white"
                    : "text-gray-600 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-800"
                }`}>
                {m === "login" ? "Sign in" : "Create account"}
              </button>
            ))}
          </div>

          <form onSubmit={handle} className="space-y-3">
            {mode === "register" && (
              <>
                <input value={form.full_name} onChange={f("full_name")}
                  placeholder="Full name" required className={inputClass} />
                <input value={form.organisation} onChange={f("organisation")}
                  placeholder="Organisation (optional)" className={inputClass} />
              </>
            )}
            <input type="email" value={form.email} onChange={f("email")}
              placeholder="Email address" required className={inputClass} />
            <input type="password" value={form.password} onChange={f("password")}
              placeholder="Password" required minLength={6} className={inputClass} />

            {error && (
              <div className="bg-red-50 border border-red-200 text-red-700 text-xs rounded-lg px-3 py-2">
                {error}
              </div>
            )}

            <button type="submit" disabled={loading}
              className="w-full py-2.5 bg-blue-600 text-white rounded-xl hover:bg-blue-700 text-sm font-medium disabled:opacity-50 flex items-center justify-center gap-2 transition">
              {loading && <Loader2 className="w-4 h-4 animate-spin" />}
              {mode === "login" ? "Sign in" : "Create account"}
            </button>
          </form>

          {mode === "login" && (
            <p className="text-center text-xs text-gray-400 mt-4">
              Don&apos;t have an account?{" "}
              <button onClick={() => setMode("register")} className="text-blue-600 hover:underline">
                Register
              </button>
            </p>
          )}
        </div>

        <p className="text-center text-xs text-gray-400 mt-6">
          Agriculture · Healthcare · Education · Military · Household · IT
        </p>
      </div>
    </div>
  );
}
