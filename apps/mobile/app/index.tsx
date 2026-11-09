import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import {
  getCoverageStats,
  getMistakes,
  previewResetCoverage,
  resetCoverage,
  startPractice,
  type CoverageStats,
} from "../src/api/client";
import { BankSwitchDialog } from "../src/components/BankSwitchDialog";
import { MaintenanceDialog } from "../src/components/MaintenanceDialog";
import { setSession } from "../src/sessionStore";
import { tokens } from "../src/theme/tokens";
import { useResponsiveLayout } from "../src/theme/useResponsiveLayout";

export default function HomeScreen() {
  const layout = useResponsiveLayout();
  const [coverage, setCoverage] = useState<CoverageStats | null>(null);
  const [error, setError] = useState("");
  const [starting, setStarting] = useState(false);
  const [mistakeCount, setMistakeCount] = useState(0);
  const [switchVisible, setSwitchVisible] = useState(false);
  const [resetVisible, setResetVisible] = useState(false);

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
      <MaintenanceDialog
        visible={resetVisible}
        title="重置覆盖统计"
        intro="先读取当前题库将删除的实际作答计数；历史报告不会被删除。"
        onCancel={() => setResetVisible(false)}
        loadPreview={async () => {
          const preview = await previewResetCoverage();
          return `将重置当前题库（${preview.bank_name}）共 ${preview.question_total ?? 0} 题的作答统计，实际删除 ${preview.count} 条作答计数。历史报告不会被删除。此操作不可恢复。`;
        }}
        onConfirm={async () => {
          await resetCoverage();
          setCoverage(await getCoverageStats());
          setResetVisible(false);
        }}
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
          <Text style={styles.bank} testID="home-bank-heading">
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
        {coverage ? (
          <View
            style={[styles.coverageBlock, { maxWidth: layout.bodyMaxWidth }]}
            testID="coverage-block"
          >
            <View style={styles.coverageHeader}>
              <View>
                <Text style={styles.coverageTitle} testID="coverage-title">
                  题库覆盖统计
                </Text>
                <Text style={styles.coverageBank}>
                  当前题库：{coverage.bank_name} · 共 {coverage.total} 题
                </Text>
              </View>
              <Pressable
                accessibilityRole="button"
                onPress={() => setResetVisible(true)}
                style={styles.resetButton}
                testID="reset-coverage-button"
              >
                <Text style={styles.resetText}>重置覆盖统计</Text>
              </Pressable>
            </View>
            {coverage.once + coverage.twice_plus === 0 ? (
              <Text style={styles.coverageEmpty} testID="coverage-empty">
                还没有开始练习
              </Text>
            ) : (
              <>
                <View style={styles.coverageBar} testID="coverage-bar">
                  {coverage.twice_plus > 0 ? (
                    <View
                      testID="coverage-repeat"
                      style={[
                        styles.coverageSegment,
                        styles.coverageRepeat,
                        { width: `${(coverage.twice_plus / coverage.total) * 100}%` },
                      ]}
                    >
                      <Text style={styles.coverageSegmentTextLight}>
                        {coverage.twice_plus} (
                        {Math.round((coverage.twice_plus / coverage.total) * 100)}%)
                      </Text>
                    </View>
                  ) : null}
                  {coverage.once > 0 ? (
                    <View
                      testID="coverage-once"
                      style={[
                        styles.coverageSegment,
                        styles.coverageOnce,
                        { width: `${(coverage.once / coverage.total) * 100}%` },
                      ]}
                    >
                      <Text style={styles.coverageSegmentTextLight}>
                        {coverage.once} (
                        {Math.round((coverage.once / coverage.total) * 100)}%)
                      </Text>
                    </View>
                  ) : null}
                  {coverage.none > 0 ? (
                    <View
                      testID="coverage-none"
                      style={[
                        styles.coverageSegment,
                        styles.coverageNone,
                        { width: `${(coverage.none / coverage.total) * 100}%` },
                      ]}
                    >
                      <Text style={styles.coverageSegmentText}>
                        {coverage.none} (
                        {Math.round((coverage.none / coverage.total) * 100)}%)
                      </Text>
                    </View>
                  ) : null}
                </View>
                <View style={styles.coverageLegend}>
                  <Text style={styles.legendRepeat}>
                    做过 ≥2 次 {coverage.twice_plus} (
                    {((coverage.twice_plus / coverage.total) * 100).toFixed(1)}%)
                  </Text>
                  <Text style={styles.legendOnce}>
                    只做 1 次 {coverage.once} (
                    {((coverage.once / coverage.total) * 100).toFixed(1)}%)
                  </Text>
                  <Text style={styles.legendNone}>
                    没做过 {coverage.none} (
                    {((coverage.none / coverage.total) * 100).toFixed(1)}%)
                  </Text>
                </View>
              </>
            )}
            <Text style={styles.coverageFootnote}>
              分母为当前题库 {coverage.total} 题，含错题重做，仅统计已交卷会话
            </Text>
          </View>
        ) : null}
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
    marginBottom: tokens.spacing.section,
  },
  bank: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.sectionTitle,
    fontWeight: "600",
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
  coverageBlock: {
    width: "100%",
    alignSelf: "flex-start",
    borderTopWidth: tokens.border.width,
    borderTopColor: tokens.color.divider,
    marginTop: tokens.spacing.section,
    paddingTop: tokens.spacing.cardPadding,
  },
  coverageHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: tokens.spacing.listGap,
  },
  coverageTitle: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.sectionTitle,
    fontWeight: "600",
  },
  resetButton: {
    minHeight: tokens.control.touchTargetMin,
    justifyContent: "center",
    paddingHorizontal: tokens.spacing.listGap,
  },
  resetText: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
  coverageBank: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    marginTop: tokens.spacing.listGap,
  },
  coverageBar: {
    width: "100%",
    height: tokens.spacing.section,
    flexDirection: "row",
    overflow: "hidden",
    borderRadius: tokens.radius.small,
    marginTop: tokens.spacing.cardPadding,
  },
  coverageSegment: {
    height: "100%",
    justifyContent: "center",
    paddingHorizontal: tokens.web_desktop.optionGap,
  },
  coverageRepeat: { backgroundColor: tokens.color.coverage_repeat },
  coverageOnce: { backgroundColor: tokens.color.coverage_once },
  coverageNone: { backgroundColor: tokens.color.coverage_none },
  coverageSegmentTextLight: {
    color: tokens.color.primaryButtonText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.minimum,
    fontWeight: "600",
  },
  coverageSegmentText: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.minimum,
  },
  coverageLegend: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: tokens.spacing.listGap,
    marginTop: tokens.spacing.listGap,
  },
  legendRepeat: {
    color: tokens.color.coverage_repeat,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    fontWeight: "600",
  },
  legendOnce: {
    color: tokens.color.coverage_once,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    fontWeight: "600",
  },
  legendNone: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
  coverageFootnote: {
    color: tokens.color.tertiaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    marginTop: tokens.spacing.listGap,
  },
  coverageEmpty: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    marginTop: tokens.spacing.cardPadding,
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
