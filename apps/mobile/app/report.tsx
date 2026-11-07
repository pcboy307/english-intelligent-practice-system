import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { getReport, type Report } from "../src/api/client";
import { getStoredReport, getSession } from "../src/sessionStore";
import { tokens } from "../src/theme/tokens";
import { useResponsiveLayout } from "../src/theme/useResponsiveLayout";

export default function ReportScreen() {
  const layout = useResponsiveLayout();
  const params = useLocalSearchParams<{ session_id?: string }>();
  const routeSessionId = Array.isArray(params.session_id)
    ? params.session_id[0]
    : params.session_id;
  const [report, setLocalReport] = useState<Report | null>(getStoredReport());
  const [error, setError] = useState("");

  useEffect(() => {
    if (report) return;
    const sessionId = routeSessionId || getSession()?.session_id;
    if (!sessionId) return;
    getReport(sessionId)
      .then(setLocalReport)
      .catch((reason) => setError(String(reason)));
  }, [report, routeSessionId]);

  if (!report) {
    return (
      <View style={[styles.shell, { maxWidth: layout.contentMaxWidth }]}>
        <Text style={styles.text}>{error || "正在加载报告…"}</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.center}>
      <View
        testID="report-shell"
        style={[styles.shell, { maxWidth: layout.contentMaxWidth }]}
      >
        <View
          testID="report-body"
          style={[styles.contentColumn, { maxWidth: layout.bodyMaxWidth }]}
        >
        <Text style={styles.title}>练习报告</Text>
        <Text style={styles.bank}>{report.bank_name}</Text>
        <Text style={styles.score}>{report.score} 分</Text>
        <Text style={styles.meta}>正确率 {Math.round(report.accuracy * 100)}% · 用时 {Math.round(report.duration_seconds / 60)} 分钟</Text>
        <Text style={styles.meta}>计分口径：满分 {report.max_score} 分；按题等分，得分 = 答对题数 ÷ {report.question_results.length} × {report.max_score}。</Text>

        <Text style={styles.sectionTitle}>分题型正确率</Text>
        {Object.entries(report.type_scores).map(([type, score]) => (
          <View key={type} style={styles.row}>
            <Text style={styles.text}>
              {
                {
                  cloze: "完型填空",
                  grammar_fill: "语法填空",
                  gap_fill: "七选五",
                  reading: "阅读理解",
                }[type] || type
              }
            </Text>
            <Text style={styles.value}>{Math.round(score.accuracy * 100)}%</Text>
          </View>
        ))}

        <Text style={styles.sectionTitle}>薄弱知识点</Text>
        {report.weak_points.length ? report.weak_points.map((item) => (
          <Text key={item.knowledge_point} style={styles.text}>· {item.knowledge_point}：{item.error_stage}</Text>
        )) : <Text style={styles.text}>本套没有明显薄弱点。</Text>}

        <Text style={styles.sectionTitle}>逐题解析</Text>
        {report.question_results.map((item, index) => (
          <View key={item.question_id} style={styles.result}>
            <Text style={[styles.resultTitle, { color: item.correct ? tokens.color.correct : tokens.color.incorrect }]}>
              {index + 1}. {item.correct ? "正确" : "错误"}
            </Text>
            <Text style={styles.text}>你的答案：{String(item.user_answer || "未作答")}</Text>
            <Text style={styles.text}>正确答案：{String(item.correct_answer)}</Text>
            <Text style={styles.explanation}>{item.explanation}</Text>
            <Text style={styles.meta}>{item.book_source} · 难度 {item.difficulty}</Text>
            <Pressable
              accessibilityRole="button"
              onPress={() =>
                router.push({
                  pathname: "/practice",
                  params: {
                    session_id: report.session_id,
                    review: "1",
                    q: String(index + 1),
                  },
                })
              }
              style={[
                styles.reviewButton,
                layout.desktop && styles.buttonDesktop,
              ]}
            >
              <Text style={styles.reviewButtonText}>查看原题</Text>
            </Pressable>
          </View>
        ))}
        <Pressable
          onPress={() => router.replace("/")}
          style={[styles.primaryButton, layout.desktop && styles.buttonDesktop]}
        >
          <Text style={styles.primaryButtonText}>返回首页</Text>
        </Pressable>
        </View>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: tokens.color.pageBackground },
  center: { alignItems: "center" },
  shell: { width: "100%", maxWidth: tokens.web.maxContentWidth, paddingHorizontal: tokens.spacing.pageX, paddingVertical: tokens.spacing.section },
  contentColumn: { width: "100%", alignSelf: "center" },
  title: { color: tokens.color.primaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.pageTitle, fontWeight: "600" },
  bank: { color: tokens.color.secondaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.body, marginTop: tokens.spacing.listGap },
  score: { color: tokens.color.primaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.pageTitle, marginTop: tokens.spacing.section },
  meta: { color: tokens.color.secondaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.auxiliary, marginTop: tokens.spacing.listGap },
  sectionTitle: { color: tokens.color.primaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.sectionTitle, fontWeight: "600", marginTop: tokens.spacing.section },
  row: { flexDirection: "row", justifyContent: "space-between", borderBottomWidth: tokens.border.width, borderBottomColor: tokens.color.divider, paddingVertical: tokens.spacing.listGap },
  text: { color: tokens.color.primaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.body, lineHeight: tokens.font.sizes.body * tokens.font.lineHeight.ui, marginTop: tokens.spacing.listGap },
  value: { color: tokens.color.primaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.body },
  result: { borderTopWidth: tokens.border.width, borderTopColor: tokens.color.divider, paddingTop: tokens.spacing.cardPadding, marginTop: tokens.spacing.section },
  resultTitle: { fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.subheading, fontWeight: "600" },
  explanation: { color: tokens.color.primaryText, fontFamily: tokens.font.passageFamily.web, fontSize: tokens.font.sizes.body, lineHeight: tokens.font.sizes.body * tokens.font.lineHeight.passage, marginTop: tokens.spacing.listGap },
  reviewButton: { minHeight: tokens.control.touchTargetMin, borderWidth: tokens.border.width, borderColor: tokens.color.secondaryBorder, borderRadius: tokens.radius.medium, justifyContent: "center", alignItems: "center", marginTop: tokens.spacing.listGap, paddingHorizontal: tokens.spacing.cardPadding },
  reviewButtonText: { color: tokens.color.primaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.body },
  buttonDesktop: {
    height: tokens.web_desktop.buttonHeight,
    minHeight: tokens.web_desktop.buttonHeight,
  },
  primaryButton: { minHeight: tokens.control.primaryButtonHeightMin, backgroundColor: tokens.color.primaryButtonBackground, borderRadius: tokens.radius.medium, alignItems: "center", justifyContent: "center", marginTop: tokens.spacing.section, paddingHorizontal: tokens.spacing.cardPadding },
  primaryButtonText: { color: tokens.color.primaryButtonText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.body },
});
