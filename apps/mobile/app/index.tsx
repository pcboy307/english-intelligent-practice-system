import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { getActiveBank, startPractice } from "../src/api/client";
import { setSession } from "../src/sessionStore";
import { tokens } from "../src/theme/tokens";
import { useResponsiveLayout } from "../src/theme/useResponsiveLayout";

export default function HomeScreen() {
  const layout = useResponsiveLayout();
  const [bankName, setBankName] = useState("加载中");
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);

  useEffect(() => {
    getActiveBank()
      .then((bank) => setBankName(bank.name))
      .catch((reason) => setError(String(reason)));
  }, []);

  async function start() {
    setStarting(true);
    setError("");
    try {
      const session = await startPractice(30);
      setSession(session);
      router.push("/practice");
    } catch (reason) {
      setError(String(reason));
    } finally {
      setStarting(false);
    }
  }

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.center}>
      <View
        testID="home-shell"
        style={[styles.shell, { maxWidth: layout.contentMaxWidth }]}
      >
        <View style={styles.header}>
          <View>
            <Text style={styles.eyebrow}>高二英语</Text>
            <Text style={styles.title}>智能练习</Text>
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => router.push("/history")}
            style={[styles.secondaryButton, layout.desktop && styles.primaryButtonDesktop]}
          >
            <Text style={styles.secondaryButtonText}>历史报告</Text>
          </Pressable>
        </View>
        <Text style={styles.bank}>当前题库：{bankName}</Text>
        <Text style={[styles.body, { maxWidth: layout.bodyMaxWidth }]}>
          一套 30 分钟练习，包含完型填空、语法填空和七选五。交卷后查看分数、正确率、薄弱知识点和逐题解析。
        </Text>
        <Pressable
          accessibilityRole="button"
          disabled={starting}
          onPress={start}
          style={[
            styles.primaryButton,
            layout.desktop && styles.primaryButtonDesktop,
            starting && styles.disabled,
          ]}
        >
          <Text style={styles.primaryButtonText}>
            {starting ? "正在组卷" : "开始 30 分钟练习"}
          </Text>
        </Pressable>
        {error ? <Text style={styles.error}>{error}</Text> : null}
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: tokens.color.pageBackground },
  center: { alignItems: "center" },
  shell: {
    width: "100%",
    maxWidth: tokens.web.maxContentWidth,
    paddingHorizontal: tokens.spacing.pageX,
    paddingTop: 80,
  },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", gap: tokens.spacing.listGap },
  eyebrow: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    letterSpacing: 1.2,
    marginBottom: tokens.spacing.listGap,
  },
  title: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.pageTitle,
    fontWeight: "600",
  },
  bank: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.subheading,
    marginTop: tokens.spacing.section,
  },
  body: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    lineHeight: tokens.font.sizes.body * tokens.font.lineHeight.ui,
    marginTop: tokens.spacing.listGap,
  },
  primaryButton: {
    minHeight: tokens.control.primaryButtonHeightMin,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: tokens.color.primaryButtonBackground,
    borderRadius: tokens.radius.medium,
    marginTop: tokens.spacing.section,
    paddingHorizontal: tokens.spacing.cardPadding,
  },
  primaryButtonText: {
    color: tokens.color.primaryButtonText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
  },
  secondaryButton: {
    minHeight: tokens.control.touchTargetMin,
    borderWidth: tokens.border.width,
    borderColor: tokens.color.secondaryBorder,
    borderRadius: tokens.radius.medium,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: tokens.spacing.cardPadding,
  },
  secondaryButtonText: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
  primaryButtonDesktop: {
    height: tokens.web_desktop.buttonHeight,
    minHeight: tokens.web_desktop.buttonHeight,
  },
  disabled: { backgroundColor: tokens.color.disabled },
  error: {
    color: tokens.color.incorrect,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    marginTop: tokens.spacing.listGap,
  },
});
