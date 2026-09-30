export function fmtDate(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString() : "";
}
