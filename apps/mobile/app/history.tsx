import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import {
  deleteReport,
  listReports,
  type ReportSummary,
} from "../src/api/client";
import { tokens } from "../src/theme/tokens";
import { useResponsiveLayout } from "../src/theme/useResponsiveLayout";

export default function HistoryScreen() {
  const layout = useResponsiveLayout();
  const [reports, setReports] = useState<ReportSummary[]>([]);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    listReports()
      .then(setReports)
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
