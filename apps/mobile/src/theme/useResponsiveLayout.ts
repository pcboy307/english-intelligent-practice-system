import { useWindowDimensions } from "react-native";

import { tokens } from "./tokens";

export function useResponsiveLayout() {
  const { width } = useWindowDimensions();
  const desktop = width >= tokens.web_desktop.breakpoint;
  return {
    desktop,
    contentMaxWidth: desktop
      ? tokens.web_desktop.contentMaxWidth
      : tokens.web_desktop.mobileMaxWidth,
    bodyMaxWidth: tokens.web_desktop.bodyMaxWidth,
  };
}
