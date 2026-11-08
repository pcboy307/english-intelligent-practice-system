import { router } from "expo-router";
import { useEffect, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import {
  clearMistakes,
  getMistakes,
  previewClearMistakes,
  type MistakeBankGroup,
  type MistakeEntry,
  type MistakeList,
} from "../src/api/client";
import { MaintenanceDialog } from "../src/components/MaintenanceDialog";
import { tokens } from "../src/theme/tokens";
import { useResponsiveLayout } from "../src/theme/useResponsiveLayout";

const TYPE_LABELS: Record<string, string> = {
  cloze: "完形填空",
  grammar: "语法填空",
  reading: "阅读理解",
  seven: "七选五",
};

function countLabel(count: number) {
  return count === 1 ? "1 题" : `${count} 题`;
}

export default function MistakesScreen() {
  const layout = useResponsiveLayout();
  const [mistakes, setMistakes] = useState<MistakeList | null>(null);
  const [expandedHistory, setExpandedHistory] = useState<Record<string, boolean>>({});
  const [error, setError] = useState("");
  const [clearVisible, setClearVisible] = useState(false);

  useEffect(() => {
    getMistakes()
      .then(setMistakes)
      .catch((reason) => setError(String(reason)));
  }, []);

  function renderBankGroup(group: MistakeBankGroup, history: boolean) {
    return (
      <View
        key={`${history ? "history" : "current"}-${group.bank_id}`}
        style={styles.group}
        testID={history ? "mistake-history-group" : "mistake-current-group"}
      >
        <Pressable
          accessibilityRole="button"
          disabled={!history}
          onPress={() =>
            setExpandedHistory((current) => ({
              ...current,
              [group.bank_id]: !current[group.bank_id],
            }))
          }
          style={styles.groupHeader}
        >
          <Text style={styles.groupTitle}>
            {history ? "历史题库" : "当前题库"} · {group.bank_name}
          </Text>
          <Text style={styles.groupCount}>
            {countLabel(group.count)}
            {history ? (expandedHistory[group.bank_id] ? " · 收起" : " · 展开") : ""}
          </Text>
        </Pressable>
        {(!history || expandedHistory[group.bank_id]) &&
          group.passages.map((passage) => (
            <Pressable
              accessibilityRole="button"
              key={passage.passage_id}
              onPress={() =>
                router.push({
                  pathname: "/mistake-review",
                  params: { passage_id: passage.passage_id },
                })
              }
              style={styles.passage}
              testID={`mistake-passage-${passage.passage_id}`}
            >
              <View style={styles.passageHeader}>
                <Text style={styles.passageTitle}>
                  {TYPE_LABELS[passage.question_type] || passage.question_type}
                </Text>
                <Text style={styles.reviewLink}>进入重做</Text>
              </View>
              {passage.items.map((item: MistakeEntry) => (
                <Text key={item.question_id} style={styles.item}>
                  {item.label} · 错过 {item.wrong_count} 次
                </Text>
              ))}
            </Pressable>
          ))}
        {group.count === 0 ? (
          <Text style={styles.emptyGroup}>当前题库暂无待订正题目。</Text>
        ) : null}
      </View>
    );
  }

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.center}>
      <MaintenanceDialog
        visible={clearVisible}
        title="清空错题本"
        intro="先读取当前题库的实际错题条数；历史题库的错题会保留。"
        onCancel={() => setClearVisible(false)}
        loadPreview={async (token) => {
          const preview = await previewClearMistakes(token);
          return `将清空当前题库（${preview.bank_name}）的 ${preview.count} 道错题。历史题库的 ${preview.history_count} 道错题会保留。此操作不可恢复。`;
        }}
        onConfirm={async (token) => {
          await clearMistakes(token);
          setMistakes(await getMistakes());
          setClearVisible(false);
        }}
      />
      <View
        testID="mistakes-shell"
        style={[styles.shell, { maxWidth: layout.contentMaxWidth }]}
      >
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>错题本</Text>
            <Text style={styles.meta}>
              当前待订正 {mistakes?.total_open ?? 0} 题
            </Text>
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => router.replace("/")}
            style={styles.button}
          >
            <Text style={styles.buttonText}>返回首页</Text>
          </Pressable>
        </View>
        {error ? <Text style={styles.error}>{error}</Text> : null}
        {!mistakes && !error ? (
          <Text style={styles.loading}>正在加载错题…</Text>
        ) : null}
        {mistakes && mistakes.total_open === 0 ? (
          <Text style={styles.empty} testID="mistakes-empty">
            暂时没有需要订正的题目
          </Text>
        ) : null}
        {mistakes ? (
          <View style={[styles.body, { maxWidth: layout.bodyMaxWidth }]}>
            {renderBankGroup(mistakes.current_bank, false)}
            {mistakes.history_banks.map((group) => renderBankGroup(group, true))}
            <Pressable
              accessibilityRole="button"
              onPress={() => setClearVisible(true)}
              style={styles.clearButton}
              testID="clear-mistakes-button"
            >
              <Text style={styles.clearText}>清空错题本</Text>
            </Pressable>
          </View>
        ) : null}
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
    alignItems: "flex-start",
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
  body: { width: "100%", alignSelf: "center" },
  group: {
    borderTopWidth: tokens.border.width,
    borderTopColor: tokens.color.divider,
    marginTop: tokens.spacing.section,
    paddingTop: tokens.spacing.cardPadding,
  },
  groupHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: tokens.spacing.listGap,
  },
  groupTitle: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.subheading,
    fontWeight: "600",
  },
  groupCount: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
  passage: {
    borderWidth: tokens.border.width,
    borderColor: tokens.color.secondaryBorder,
    borderRadius: tokens.radius.medium,
    marginTop: tokens.spacing.listGap,
    padding: tokens.spacing.cardPadding,
  },
  passageHeader: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: tokens.spacing.listGap,
  },
  passageTitle: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    fontWeight: "600",
  },
  reviewLink: {
    color: tokens.color.accent,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
  item: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    marginTop: tokens.spacing.listGap,
  },
  empty: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    marginTop: tokens.spacing.section,
  },
  emptyGroup: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    marginTop: tokens.spacing.listGap,
  },
  loading: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    marginTop: tokens.spacing.section,
  },
  button: {
    minHeight: tokens.control.touchTargetMin,
    borderWidth: tokens.border.width,
    borderColor: tokens.color.secondaryBorder,
    borderRadius: tokens.radius.medium,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: tokens.spacing.cardPadding,
  },
  buttonText: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
  error: {
    color: tokens.color.incorrect,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    marginTop: tokens.spacing.section,
  },
  clearButton: {
    alignSelf: "flex-start",
    minHeight: tokens.control.touchTargetMin,
    marginTop: tokens.spacing.section,
    paddingHorizontal: tokens.spacing.listGap,
    justifyContent: "center",
  },
  clearText: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
});
