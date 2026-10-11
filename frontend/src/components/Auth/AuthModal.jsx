/**
 * AegisAI Authentication Modal
 * Sign In & Registration with 1-Click Demo Persona selector.
 */

import React, { useState } from "react";
import { useAuth } from "../../context/AuthContext";

const DEMO_PERSONAS = [
    {
        name: "Commander Alpha",
        email: "commander@aegis.local",
        password: "Password123!",
        role: "COMMANDER",
        desc: "Tactical incident management & smart dispatch authority",
        icon: "🎖️"
    },
    {
        name: "Dispatcher Dave",
        email: "dispatcher@aegis.local",
        password: "Password123!",
        role: "DISPATCHER",
        desc: "Fleet allocation & mission assignment coordination",
        icon: "📡"
    },
    {
        name: "Medic Mary",
        email: "medic@aegis.local",
        password: "Password123!",
        role: "MEDIC",
        desc: "First responder mission execution & arrival tracking",
        icon: "🚑"
    },
    {
        name: "Nitish (Admin)",
        email: "nitrexo19@gmail.com",
        password: "kumar19##Nitish",
        role: "ADMIN",
        desc: "Complete platform control, user management & system settings",
        icon: "🛡️"
    },
    {
        name: "Citizen John",
        email: "citizen@aegis.local",
        password: "Password123!",
        role: "CITIZEN",
        desc: "Public incident reporting & shelter evacuation viewer",
        icon: "👤"
    }
];

export function AuthModal({ isOpen, onClose }) {
    const { login, register } = useAuth();
    const [mode, setMode] = useState("LOGIN"); // "LOGIN" | "REGISTER"
    const [email, setEmail] = useState("");
    const [password, setPassword] = useState("");
    const [name, setName] = useState("");
    const [role, setRole] = useState("CITIZEN");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);

    if (!isOpen) return null;

    const handleSubmit = async (e) => {
        e.preventDefault();
        setError(null);
        setLoading(true);

        try {
            if (mode === "LOGIN") {
                const res = await login(email, password);
                if (res.success) {
                    onClose();
                } else {
                    setError(res.error || "Authentication failed.");
                }
            } else {
                const res = await register(name, email, password, role);
                if (res.success) {
                    onClose();
                } else {
                    setError(res.error || "Registration failed.");
                }
            }
        } catch (err) {
            setError(err?.message || "An unexpected error occurred.");
        } finally {
            setLoading(false);
        }
    };

    const handleSelectPersona = async (persona) => {
        setEmail(persona.email);
        setPassword(persona.password);
        setError(null);
        setLoading(true);

        const res = await login(persona.email, persona.password);
        if (res.success) {
            onClose();
        } else {
            setError(res.error || "Quick login failed.");
        }
        setLoading(false);
    };

    return (
        <div className="modal-overlay" onClick={onClose}>
            <div className="auth-modal-card" onClick={(e) => e.stopPropagation()}>
                {/* MODAL HEADER */}
                <div className="auth-modal-header">
                    <div>
                        <h2>🛡️ AegisAI Identity & Access</h2>
                        <p>Authenticate with your security clearance to unlock platform features.</p>
                    </div>
                    <button className="modal-close-btn" onClick={onClose}>✕</button>
                </div>

                {/* TAB SWITCHER */}
                <div className="auth-tabs">
                    <button
                        type="button"
                        className={`auth-tab-btn ${mode === "LOGIN" ? "active" : ""}`}
                        onClick={() => { setMode("LOGIN"); setError(null); }}
                    >
                        🔑 Sign In
                    </button>
                    <button
                        type="button"
                        className={`auth-tab-btn ${mode === "REGISTER" ? "active" : ""}`}
                        onClick={() => { setMode("REGISTER"); setError(null); }}
                    >
                        ✍️ Register Account
                    </button>
                </div>

                {/* QUICK DEMO PERSONAS */}
                {mode === "LOGIN" && (
                    <div className="quick-personas-section">
                        <div className="section-label">⚡ Quick Demo Clearance (1-Click Login):</div>
                        <div className="personas-grid">
                            {DEMO_PERSONAS.map((p) => (
                                <button
                                    key={p.role}
                                    type="button"
                                    className="persona-chip"
                                    onClick={() => handleSelectPersona(p)}
                                    disabled={loading}
                                >
                                    <span className="persona-icon">{p.icon}</span>
                                    <div className="persona-meta">
                                        <strong>{p.name}</strong>
                                        <span className="badge-mini">{p.role}</span>
                                    </div>
                                </button>
                            ))}
                        </div>
                    </div>
                )}

                {/* ERROR ALERT */}
                {error && (
                    <div className="auth-error-alert">
                        ⚠️ {error}
                    </div>
                )}

                {/* AUTH FORM */}
                <form className="auth-form" onSubmit={handleSubmit}>
                    {mode === "REGISTER" && (
                        <>
                            <div className="form-group">
                                <label>Full Name</label>
                                <input
                                    type="text"
                                    required
                                    placeholder="e.g. Sarah Connor"
                                    value={name}
                                    onChange={(e) => setName(e.target.value)}
                                    disabled={loading}
                                />
                            </div>

                            <div className="form-group">
                                <label>Role Clearance</label>
                                <select
                                    value={role}
                                    onChange={(e) => setRole(e.target.value)}
                                    disabled={loading}
                                >
                                    <option value="CITIZEN">👤 CITIZEN (Public Reporting)</option>
                                    <option value="RESPONDER">🚑 RESPONDER (Field Unit)</option>
                                    <option value="MEDIC">🩺 MEDIC (Hospital Facility)</option>
                                    <option value="DISPATCHER">📡 DISPATCHER (Resource Management)</option>
                                    <option value="COMMANDER">🎖️ COMMANDER (Strategic Incident Control)</option>
                                    <option value="ADMIN">🛡️ ADMIN (Full Platform Control)</option>
                                </select>
                            </div>
                        </>
                    )}

                    <div className="form-group">
                        <label>Email Address</label>
                        <input
                            type="email"
                            required
                            placeholder="commander@aegis.local"
                            value={email}
                            onChange={(e) => setEmail(e.target.value)}
                            disabled={loading}
                        />
                    </div>

                    <div className="form-group">
                        <label>Password</label>
                        <input
                            type="password"
                            required
                            placeholder="••••••••••••"
                            value={password}
                            onChange={(e) => setPassword(e.target.value)}
                            disabled={loading}
                        />
                        {mode === "REGISTER" && (
                            <small style={{ color: "#94a3b8", fontSize: "11px", marginTop: "4px", display: "block" }}>
                                🔒 Min 8 characters with at least 1 uppercase letter, 1 lowercase letter, and 1 number (e.g. <code>Password123!</code>).
                            </small>
                        )}
                    </div>

                    <button
                        type="submit"
                        className="auth-submit-btn"
                        disabled={loading}
                    >
                        {loading ? "Authenticating..." : mode === "LOGIN" ? "🔓 Sign In to AegisAI" : "🚀 Create Account"}
                    </button>
                </form>
            </div>
        </div>
    );
}

export default AuthModal;
