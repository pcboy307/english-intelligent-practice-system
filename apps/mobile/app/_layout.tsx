import { Stack } from "expo-router";
import { useEffect } from "react";

import { applyWebTheme } from "../src/theme/applyWebTheme";
import { tokens } from "../src/theme/tokens";

export default function RootLayout() {
  useEffect(() => {
    applyWebTheme();
  }, []);

  return (
    <Stack
      screenOptions={{
        headerShown: false,
        contentStyle: { backgroundColor: tokens.color.pageBackground },
      }}
    />
  );
}
