import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { api } from "../api/client";
import type { Me } from "../api/types";
import { ErrorText, Field } from "../components/ui";

export function LoginPage() {
  const { t } = useTranslation();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const qc = useQueryClient();
  const navigate = useNavigate();
  const login = useMutation({
    mutationFn: () => api<Me>("/auth/login", { method: "POST", body: { email, password } }),
    onSuccess: (me) => {
      qc.clear();
      qc.setQueryData(["me"], me);
      navigate("/");
    },
  });
  const submit = (e: FormEvent) => {
    e.preventDefault();
    login.mutate();
  };
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-100 font-sans">
      <form onSubmit={submit} className="card w-80 space-y-3">
        <h1 className="text-lg font-bold text-blue-900">{t("app.title")}</h1>
        <Field label={t("auth.email")}>
          <input className="input" type="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </Field>
        <Field label={t("auth.password")}>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
        <ErrorText error={login.error} />
        <button className="btn btn-primary w-full justify-center" disabled={login.isPending}>
          {t("auth.login")}
        </button>
      </form>
    </div>
  );
}
