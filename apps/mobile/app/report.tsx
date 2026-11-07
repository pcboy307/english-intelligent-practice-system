import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { getReport, type Report } from "../src/api/client";
import { getStoredReport, getSession } from "../src/sessionStore";
import { tokens } from "../src/theme/tokens";

export default function ReportScreen() {
  const [report, setLocalReport] = useState<Report | null>(getStoredReport());
  const [error, setError] = useState("");

  useEffect(() => {
    if (report) return;
    const session = getSession();
    if (!session) return;
    getReport(session.session_id)
      .then(setLocalReport)
      .catch((reason) => setError(String(reason)));
  }, [report]);

  if (!report) {
    return (
      <View style={styles.shell}>
        <Text style={styles.text}>{error || "正在加载报告…"}</Text>
      </View>
    );
  }

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.center}>
      <View style={styles.shell}>
        <Text style={styles.title}>练习报告</Text>
        <Text style={styles.bank}>{report.bank_name}</Text>
        <Text style={styles.score}>{report.score} 分</Text>
        <Text style={styles.meta}>正确率 {Math.round(report.accuracy * 100)}% · 用时 {Math.round(report.duration_seconds / 60)} 分钟</Text>

        <Text style={styles.sectionTitle}>分题型正确率</Text>
        {Object.entries(report.type_scores).map(([type, score]) => (
          <View key={type} style={styles.row}>
            <Text style={styles.text}>{type}</Text>
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
          </View>
        ))}
        <Pressable onPress={() => router.replace("/")} style={styles.primaryButton}>
          <Text style={styles.primaryButtonText}>返回首页</Text>
        </Pressable>
      </View>
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: tokens.color.pageBackground },
  center: { alignItems: "center" },
  shell: { width: "100%", maxWidth: tokens.web.maxContentWidth, paddingHorizontal: tokens.spacing.pageX, paddingVertical: tokens.spacing.section },
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
  primaryButton: { minHeight: tokens.control.primaryButtonHeightMin, backgroundColor: tokens.color.primaryButtonBackground, borderRadius: tokens.radius.medium, alignItems: "center", justifyContent: "center", marginTop: tokens.spacing.section, paddingHorizontal: tokens.spacing.cardPadding },
  primaryButtonText: { color: tokens.color.primaryButtonText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.body },
});
