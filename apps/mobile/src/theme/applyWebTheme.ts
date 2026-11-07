import { tokens } from "./tokens";

export function applyWebTheme() {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.style.colorScheme = tokens.web.colorScheme;
  root.style.setProperty("--color-page-background", tokens.color.pageBackground);
  root.style.setProperty("--color-primary-text", tokens.color.primaryText);
  root.style.setProperty("--color-divider", tokens.color.divider);
  Object.assign(document.body.style, {
    background: tokens.color.pageBackground,
    color: tokens.color.primaryText,
    colorScheme: tokens.web.colorScheme,
  });
}
