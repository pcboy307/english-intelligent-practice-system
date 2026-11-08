import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import {
  getCoverageStats,
  getMistakes,
  startPractice,
} from "../src/api/client";
import { BankSwitchDialog } from "../src/components/BankSwitchDialog";
import { setSession } from "../src/sessionStore";
import { tokens } from "../src/theme/tokens";
import { useResponsiveLayout } from "../src/theme/useResponsiveLayout";

export default function HomeScreen() {
  const layout = useResponsiveLayout();
  const [coverage, setCoverage] = useState<{
    bank_name: string;
    total: number;
  } | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const [mistakeCount, setMistakeCount] = useState(0);
  const [switchVisible, setSwitchVisible] = useState(false);

  async function loadHome() {
    Promise.all([getCoverageStats(), getMistakes()])
      .then(([nextCoverage, mistakes]) => {
        setCoverage(nextCoverage);
        setMistakeCount(mistakes.total_open);
      })
      .catch((reason) => setError(String(reason)));
  }

  useEffect(() => {
    loadHome();
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
      <BankSwitchDialog
        visible={switchVisible}
        onCancel={() => setSwitchVisible(false)}
        onSwitched={loadHome}
      />
      <View
        testID="home-shell"
        style={[styles.shell, { maxWidth: layout.contentMaxWidth }]}
      >
        <View style={styles.header}>
          <View>
            <Text style={styles.eyebrow}>高二英语</Text>
            <Text style={styles.title}>智能练习</Text>
          </View>
          <View style={styles.headerActions}>
            <Pressable
              accessibilityRole="button"
              onPress={() => router.push("/mistakes")}
              style={[styles.secondaryButton, layout.desktop && styles.primaryButtonDesktop]}
              testID="home-mistakes-entry"
            >
              <Text style={styles.secondaryButtonText}>
                错题本 · 待订正 {mistakeCount} 题
              </Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => router.push("/history")}
              style={[styles.secondaryButton, layout.desktop && styles.primaryButtonDesktop]}
            >
              <Text style={styles.secondaryButtonText}>历史报告</Text>
            </Pressable>
          </View>
        </View>
        <View style={styles.bankLine}>
          <Text style={styles.bank}>
            当前题库：{coverage?.bank_name || "加载中"}
            {coverage ? ` · 共 ${coverage.total} 题` : ""}
          </Text>
          <Pressable
            accessibilityRole="button"
            onPress={() => setSwitchVisible(true)}
            style={styles.switchButton}
            testID="home-switch-bank"
          >
            <Text style={styles.switchText}>切换</Text>
          </Pressable>
        </View>
        <Text style={[styles.body, { maxWidth: layout.bodyMaxWidth }]}>
          一套 30 分钟练习，包含完型填空、语法填空和阅读或七选五。交卷后查看分数、正确率、薄弱知识点和逐题解析。
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
  headerActions: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "flex-end",
    gap: tokens.web_desktop.optionGap,
  },
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
  bankLine: {
    flexDirection: "row",
    alignItems: "center",
    alignSelf: "flex-start",
    gap: tokens.web_desktop.optionGap,
  },
  switchButton: {
    minHeight: tokens.control.touchTargetMin,
    justifyContent: "center",
    paddingHorizontal: tokens.spacing.listGap,
  },
  switchText: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
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
