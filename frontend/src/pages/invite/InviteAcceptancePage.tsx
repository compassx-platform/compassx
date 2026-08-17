import React, { useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useInviteDetails, acceptInvite } from "../../lib/userManagerApi";
import { saveTokens } from "../../lib/auth";

export default function InviteAcceptancePage() {
  const { token } = useParams<{ token: string }>();
  const navigate = useNavigate();

  const { data: invite, isLoading, error: fetchError } = useInviteDetails(token || "");

  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

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
      const resp = await acceptInvite(token || "", {
        display_name: displayName.trim(),
        password,
        confirm_password: confirmPassword,
      });
      saveTokens(resp.access_token, resp.refresh_token);
      navigate("/");
    } catch (err: any) {
      setError(
        err.response?.data?.detail ||
          err.message ||
          "Failed to accept invitation. Please contact your administrator."
      );
    } finally {
      setLoading(false);
    }
  };

  if (isLoading) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "var(--color-bg)",
          color: "var(--color-text-muted)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "var(--font-family)",
        }}
      >
        Loading invitation details…
      </div>
    );
  }

  if (fetchError || !invite) {
    return (
      <div
        style={{
          minHeight: "100vh",
          background: "var(--color-bg)",
          color: "var(--color-text)",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          padding: "24px",
          fontFamily: "var(--font-family)",
        }}
      >
        <div
          className="glass"
          style={{
            maxWidth: "420px",
            background: "var(--color-surface)",
            border: "1px solid var(--color-border)",
            borderRadius: "var(--radius-lg)",
            padding: "36px",
            textAlign: "center",
          }}
        >
          <div style={{ fontSize: "36px", marginBottom: "12px" }}>⚠️</div>
          <h2 style={{ margin: "0 0 8px", fontSize: "20px", color: "var(--color-text)" }}>Invalid or Expired Invite</h2>
          <p style={{ color: "var(--color-text-muted)", fontSize: "14px", lineHeight: 1.5 }}>
            This invitation link is invalid, expired, or has already been used.
          </p>
        </div>
      </div>
    );
  }

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
          maxWidth: "440px",
          background: "var(--color-surface)",
          border: "1px solid var(--color-border)",
          borderRadius: "var(--radius-lg)",
          padding: "36px",
          boxShadow: "var(--shadow-md)",
        }}
      >
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
            Accept Invitation
          </h1>
          <p style={{ margin: "6px 0 0", color: "var(--color-text-muted)", fontSize: "14px" }}>
            Joining as <strong style={{ color: "var(--color-text)" }}>{invite.email}</strong>
          </p>
        </div>

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
            }}
          >
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div style={{ marginBottom: "16px" }}>
            <label className="label">Your Name</label>
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
            {loading ? "Accepting invitation…" : "Join Compass"}
          </button>
        </form>
      </div>
    </div>
  );
}
