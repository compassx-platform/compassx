import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { login, fetchEntryPoint, fetchSetupStatus } from "../../lib/userManagerApi";
import { saveTokens, setPrincipalInfo } from "../../lib/auth";

export default function LoginPage() {
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const checkSetup = async () => {
      try {
        const status = await fetchSetupStatus();
        if (status.needs_setup) {
          navigate("/setup");
        }
      } catch (err) {
        console.error("Failed to fetch setup status", err);
      }
    };
    checkSetup();
  }, [navigate]);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const resp = await login({ email: email.trim(), password });
      saveTokens(resp.access_token, resp.refresh_token);
      setPrincipalInfo({
        principal_id: resp.user_id,
        name: resp.display_name || resp.email,
        email: resp.email,
        is_account_admin: resp.is_account_admin,
        account_id: resp.account_id,
        expires_at: "",
      });

      const entryPoint = await fetchEntryPoint();
      navigate(entryPoint.route || "/");
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Invalid email or password. Please try again."
      );
    } finally {
      setLoading(false);
    }
  };

  const performAutoLogin = async (loginEmail: string, loginPass: string) => {
    setEmail(loginEmail);
    setPassword(loginPass);
    setLoading(true);
    setError(null);
    try {
      const resp = await login({ email: loginEmail, password: loginPass });
      saveTokens(resp.access_token, resp.refresh_token);
      setPrincipalInfo({
        principal_id: resp.user_id,
        name: resp.display_name || resp.email,
        email: resp.email,
        is_account_admin: resp.is_account_admin,
        account_id: resp.account_id,
        expires_at: "",
      });

      const entryPoint = await fetchEntryPoint();
      navigate(entryPoint.route || "/");
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Auto-login failed. Please check user credentials."
      );
    } finally {
      setLoading(false);
    }
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        background: "var(--color-bg)",
        color: "var(--color-text)",
        fontFamily: "var(--font-family)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        padding: "24px",
        boxSizing: "border-box",
      }}
    >
      <div
        className="glass"
        style={{
          width: "100%",
          maxWidth: "420px",
          borderRadius: "var(--radius-lg)",
          padding: "36px",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          boxShadow: "var(--shadow-md)",
        }}
      >
        {/* Header */}
        <div style={{ textAlign: "center", marginBottom: "28px" }}>
          <div
            style={{
              width: "44px",
              height: "44px",
              borderRadius: "var(--radius)",
              background: "var(--sb-logo-bg)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: "20px",
              fontWeight: 800,
              color: "#fff",
              margin: "0 auto 16px",
            }}
          >
            C
          </div>
          <h1
            style={{
              margin: 0,
              fontSize: "24px",
              fontWeight: 700,
              color: "var(--color-text)",
            }}
          >
            Compass
          </h1>
          <p style={{ margin: "6px 0 0", color: "var(--color-text-muted)", fontSize: "14px" }}>
            Sign in to your account
          </p>
        </div>

        {/* Error Alert */}
        {error && (
          <div
            style={{
              marginBottom: "20px",
              padding: "12px 16px",
              background: "var(--color-danger-bg)",
              border: "1px solid var(--color-danger)",
              borderRadius: "var(--radius)",
              color: "var(--color-danger)",
              fontSize: "13px",
              lineHeight: 1.4,
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleLogin}>
          <div style={{ marginBottom: "18px" }}>
            <label className="label">Email Address</label>
            <input
              type="email"
              required
              className="input-field"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </div>

          <div style={{ marginBottom: "24px" }}>
            <label className="label">Password</label>
            <div style={{ position: "relative" }}>
              <input
                type={showPassword ? "text" : "password"}
                required
                className="input-field"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                style={{ paddingRight: "44px" }}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                style={{
                  position: "absolute",
                  right: "12px",
                  top: "50%",
                  transform: "translateY(-50%)",
                  background: "none",
                  border: "none",
                  color: "var(--color-text-muted)",
                  cursor: "pointer",
                  fontSize: "13px",
                }}
              >
                {showPassword ? "Hide" : "Show"}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary"
            style={{
              width: "100%",
              padding: "10px",
              justifyContent: "center",
              fontSize: "14px",
            }}
          >
            {loading ? "Signing in…" : "Sign in"}
          </button>

          {/* Testing Shortcuts */}
          <div style={{ marginTop: "20px", paddingTop: "16px", borderTop: "1px dashed var(--color-border)" }}>
            <div style={{ fontSize: "11px", fontWeight: 700, textTransform: "uppercase", color: "var(--color-text-muted)", marginBottom: "10px", textAlign: "center", letterSpacing: "0.05em" }}>
              Testing Shortcuts
            </div>
            <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "10px" }}>
              <button
                type="button"
                className="btn-outline"
                onClick={() => performAutoLogin("vishalgvora@gmail.com", "Test@123")}
                disabled={loading}
                style={{ fontSize: "12px", padding: "8px", justifyContent: "center" }}
              >
                Admin Login
              </button>
              <button
                type="button"
                className="btn-outline"
                onClick={() => performAutoLogin("test@test.com", "Test@123")}
                disabled={loading}
                style={{ fontSize: "12px", padding: "8px", justifyContent: "center" }}
              >
                Test User
              </button>
            </div>
          </div>
        </form>
      </div>
    </div>
  );
}
