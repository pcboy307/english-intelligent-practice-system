import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import {
  deleteReport,
  getCoverageStats,
  listReports,
  type CoverageStats,
  type ReportSummary,
} from "../src/api/client";
import { tokens } from "../src/theme/tokens";
import { useResponsiveLayout } from "../src/theme/useResponsiveLayout";

export default function HistoryScreen() {
  const layout = useResponsiveLayout();
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [coverage, setCoverage] = useState<CoverageStats | null>(null);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([listReports(), getCoverageStats()])
      .then(([nextReports, nextCoverage]) => {
        setReports(nextReports);
        setCoverage(nextCoverage);
      })
      .catch((reason) => setError(String(reason)))
      .finally(() => setLoading(false));
  }, []);

  async function remove(sessionId: string) {
    try {
      await deleteReport(sessionId);
      setReports((current) =>
        current.filter((report) => report.session_id !== sessionId),
      );
      setConfirmingId(null);
    } catch (reason) {
      setError(String(reason));
    }
  }

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.center}>
      <View
        testID="history-shell"
        style={[styles.shell, { maxWidth: layout.contentMaxWidth }]}
      >
        <View style={styles.header}>
          <Text style={styles.title}>历史报告</Text>
          <Pressable
            accessibilityRole="button"
            onPress={() => router.replace("/")}
            style={[styles.button, layout.desktop && styles.buttonDesktop]}
          >
            <Text style={styles.buttonText}>返回首页</Text>
          </Pressable>
        </View>
        <Text style={styles.meta}>报告按“日期-时间-题目数-分数”命名。</Text>

        {coverage ? (
          <View style={styles.coverageBlock} testID="coverage-block">
            <View style={styles.coverageHeader}>
              <View>
                <Text style={styles.coverageTitle}>题库覆盖统计</Text>
                <Text style={styles.coverageBank}>
                  当前题库：{coverage.bank_name} · 共 {coverage.total} 题
                </Text>
              </View>
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
                    做过 ≥2 次 {coverage.twice_plus}
                  </Text>
                  <Text style={styles.legendOnce}>只做 1 次 {coverage.once}</Text>
                  <Text style={styles.legendNone}>没做过 {coverage.none}</Text>
                </View>
              </>
            )}
            <Text style={styles.coverageFootnote}>
              分母为当前题库 {coverage.total} 题，含错题重做，仅统计已交卷会话
            </Text>
          </View>
        ) : null}

        {loading ? <Text style={styles.message}>正在加载…</Text> : null}
        {!loading && !reports.length ? (
          <Text style={styles.message}>还没有历史报告。</Text>
        ) : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}

        <View style={{ maxWidth: layout.bodyMaxWidth, width: "100%", alignSelf: "center" }}>
          {reports.map((report) => (
            <View key={report.session_id} style={styles.reportRow}>
              <View style={styles.reportText}>
                <Text style={styles.reportTitle}>{report.report_title}</Text>
                <Text style={styles.meta}>
                  {report.question_count} 题 · {report.score} 分
                </Text>
              </View>
              <View style={styles.actions}>
                {confirmingId === report.session_id ? (
                  <>
                    <Pressable
                      accessibilityRole="button"
                      onPress={() => setConfirmingId(null)}
                      style={[styles.button, layout.desktop && styles.buttonDesktop]}
                    >
                      <Text style={styles.buttonText}>取消</Text>
                    </Pressable>
                    <Pressable
                      accessibilityRole="button"
                      onPress={() => remove(report.session_id)}
                      style={[styles.deleteButton, layout.desktop && styles.buttonDesktop]}
                    >
                      <Text style={styles.deleteText}>确认删除</Text>
                    </Pressable>
                  </>
                ) : (
                  <>
                    <Pressable
                      accessibilityRole="button"
                      onPress={() =>
                        router.push({
                          pathname: "/report",
                          params: { session_id: report.session_id },
                        })
                      }
                      style={[styles.button, layout.desktop && styles.buttonDesktop]}
                    >
                      <Text style={styles.buttonText}>打开</Text>
                    </Pressable>
                    <Pressable
                      accessibilityRole="button"
                      onPress={() => setConfirmingId(report.session_id)}
                      style={[styles.button, layout.desktop && styles.buttonDesktop]}
                    >
                      <Text style={styles.buttonText}>删除</Text>
                    </Pressable>
                  </>
                )}
              </View>
            </View>
          ))}
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: tokens.color.pageBackground },
  center: { alignItems: "center" },
  shell: {
    width: "100%",
    paddingHorizontal: tokens.spacing.pageX,
    paddingVertical: tokens.spacing.section,
  },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: tokens.spacing.listGap,
  },
  title: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.pageTitle,
    fontWeight: "600",
  },
  meta: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    marginTop: tokens.spacing.listGap,
  },
  message: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    marginTop: tokens.spacing.section,
  },
  coverageBlock: {
    width: "100%",
    maxWidth: 760,
    alignSelf: "center",
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
  reportRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: tokens.spacing.listGap,
    borderTopWidth: tokens.border.width,
    borderTopColor: tokens.color.divider,
    marginTop: tokens.spacing.section,
    paddingTop: tokens.spacing.cardPadding,
  },
  reportText: { flex: 1 },
  reportTitle: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    fontWeight: "600",
  },
  actions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    flexWrap: "wrap",
    gap: tokens.web_desktop.optionGap,
  },
  button: {
    minHeight: tokens.control.touchTargetMin,
    minWidth: tokens.control.touchTargetMin,
    borderWidth: tokens.border.width,
    borderColor: tokens.color.secondaryBorder,
    borderRadius: tokens.radius.medium,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: tokens.spacing.listGap,
  },
  buttonDesktop: {
    height: tokens.web_desktop.buttonHeight,
    minHeight: tokens.web_desktop.buttonHeight,
  },
  buttonText: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
  deleteButton: {
    minHeight: tokens.control.touchTargetMin,
    minWidth: tokens.control.touchTargetMin,
    borderWidth: tokens.border.width,
    borderColor: tokens.color.incorrect,
    borderRadius: tokens.radius.medium,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: tokens.spacing.listGap,
  },
  deleteText: {
    color: tokens.color.incorrect,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
  error: {
    color: tokens.color.incorrect,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    marginTop: tokens.spacing.section,
  },
});
