import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";
import { ApiError } from "../api/client";

export function PageHeader({ title, actions }: { title: string; actions?: ReactNode }) {
  return (
    <div className="mb-4 flex items-center justify-between gap-2">
      <h1 className="text-xl font-semibold text-slate-800">{title}</h1>
      <div className="flex gap-2">{actions}</div>
    </div>
  );
}

export function ErrorText({ error }: { error: unknown }) {
  const { t } = useTranslation();
  if (!error) return null;
  const code = error instanceof ApiError ? error.code : "unknown";
  return (
    <p role="alert" className="text-sm text-red-700">
      {t(`errors.${code}`, { defaultValue: t("errors.unknown") })}
    </p>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="label">{label}</span>
      {children}
    </label>
  );
}

export function Empty() {
  const { t } = useTranslation();
  return <p className="py-6 text-center text-sm text-slate-500">{t("common.empty")}</p>;
}

export function Loading() {
  const { t } = useTranslation();
  return <p className="py-6 text-center text-sm text-slate-500">{t("common.loading")}</p>;
}

export function StatusBadge({ group, value }: { group: string; value: string }) {
  const { t } = useTranslation();
  return <span className="badge">{t(`${group}.${value}`, { defaultValue: value })}</span>;
}

export function Select({
  value,
  onChange,
  options,
  group,
  allowEmpty,
  ariaLabel,
}: {
  value: string;
  onChange: (v: string) => void;
  options: readonly string[];
  group: string;
  allowEmpty?: boolean;
  ariaLabel?: string;
}) {
  const { t } = useTranslation();
  return (
    <select className="input" value={value} onChange={(e) => onChange(e.target.value)} aria-label={ariaLabel}>
      {allowEmpty && <option value="">{t("common.none")}</option>}
      {options.map((o) => (
        <option key={o} value={o}>
          {t(`${group}.${o}`, { defaultValue: o })}
        </option>
      ))}
    </select>
  );
}

export function NeedTenant() {
  const { t } = useTranslation();
  return <p className="card text-sm text-slate-600">{t("common.selectTenant")}</p>;
}
