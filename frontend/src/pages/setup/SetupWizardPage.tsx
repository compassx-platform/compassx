import React, { useState } from "react";
import { useNavigate } from "react-router-dom";
import { completeSetup } from "../../lib/userManagerApi";
import { saveTokens, setPrincipalInfo } from "../../lib/auth";

export default function SetupWizardPage() {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [accountName, setAccountName] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirmPassword) {
      setError("Passwords do not match");
      return;
    }
    if (password.length < 8) {
      setError("Password must be at least 8 characters");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const resp = await completeSetup({
        account_name: accountName.trim(),
        admin_email: adminEmail.trim(),
        admin_display_name: displayName.trim(),
        admin_password: password,
      });
      // Save tokens and navigate directly to the ready default workspace
      saveTokens(resp.access_token, resp.refresh_token);
      setPrincipalInfo({
        principal_id: resp.user_id,
        name: resp.display_name || resp.email,
        email: resp.email,
        is_account_admin: resp.is_account_admin ?? true,
        account_id: resp.account_id,
        expires_at: "",
      });
      navigate("/w/default/platform");
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Failed to complete setup. Please try again."
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
          maxWidth: "460px",
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
            Compass Initial Setup
          </h1>
          <p style={{ margin: "6px 0 0", color: "var(--color-text-muted)", fontSize: "14px" }}>
            Set up your organization account & admin user
          </p>
        </div>

        {/* Error Notification */}
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

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "16px" }}>
            <label className="label">Account Name</label>
            <input
              type="text"
              required
              className="input-field"
              value={accountName}
              onChange={(e) => setAccountName(e.target.value)}
            />
          </div>

          <div style={{ marginBottom: "16px" }}>
            <label className="label">Admin Email</label>
            <input
              type="email"
              required
              className="input-field"
              value={adminEmail}
              onChange={(e) => setAdminEmail(e.target.value)}
            />
          </div>

          <div style={{ marginBottom: "16px" }}>
            <label className="label">Display Name</label>
            <input
              type="text"
              required
              className="input-field"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
            />
          </div>

          <div style={{ marginBottom: "16px" }}>
            <label className="label">Password</label>
            <input
              type="password"
              required
              className="input-field"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          </div>

          <div style={{ marginBottom: "24px" }}>
            <label className="label">Confirm Password</label>
            <input
              type="password"
              required
              className="input-field"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
            />
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
            {loading ? "Creating Account…" : "Complete Setup →"}
          </button>
        </form>
      </div>
    </div>
  );
}
