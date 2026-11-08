import { router, useLocalSearchParams } from "expo-router";
import { ReactNode, useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import {
  getMistakePassage,
  saveAnswer,
  startMistakeReview,
  submitPractice,
  type MistakeDetail,
  type MistakeDetailQuestion,
  type PracticeSession,
  type SessionItem,
} from "../src/api/client";
import { tokens } from "../src/theme/tokens";
import { useResponsiveLayout } from "../src/theme/useResponsiveLayout";

const TYPE_LABELS: Record<string, string> = {
  cloze: "完形填空",
  grammar: "语法填空",
  reading: "阅读理解",
  seven: "七选五",
};

function questionOrder(questionId: string) {
  const match = questionId.match(/(\d+)$/);
  return match ? Number(match[1]) : 0;
}

function markerFor(type: string, order: number) {
  if (type === "grammar_fill") return String.fromCharCode(0x2460 + order - 1);
  return `(${order})`;
}

export default function MistakeReviewScreen() {
  const layout = useResponsiveLayout();
  const params = useLocalSearchParams<{ passage_id?: string }>();
  const passageId = params.passage_id;
  const [detail, setDetail] = useState<MistakeDetail | null>(null);
  const [session, setSession] = useState<PracticeSession | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!passageId) return;
    Promise.all([
      getMistakePassage(passageId),
      startMistakeReview(passageId),
    ])
      .then(([nextDetail, nextSession]) => {
        setDetail(nextDetail);
        setSession(nextSession);
      })
      .catch((reason) => setError(String(reason)));
  }, [passageId]);

  const itemsByQuestion = useMemo(
    () =>
      new Map(
        (session?.items || []).map((item) => [item.question_id, item]),
      ),
    [session],
  );
  const questionsByOrder = useMemo(
    () =>
      new Map(
        (detail?.questions || []).map((question) => [
          questionOrder(question.question_id),
          question,
        ]),
      ),
    [detail],
  );
  const targetSet = useMemo(
    () => new Set(detail?.target_question_ids || []),
    [detail],
  );

  function blankNode(question: MistakeDetailQuestion): ReactNode {
    const active = targetSet.has(question.question_id);
    const marker = markerFor(question.type, questionOrder(question.question_id));
    if (!active) {
      return (
        <Text
          key={`locked-${question.question_id}`}
          style={styles.lockedBlank}
          testID={`review-locked-${question.question_id}`}
        >
          {marker} {String(question.answer)}
        </Text>
      );
    }
    return (
      <Text key={`active-${question.question_id}`} style={styles.activeBlank}>
        {marker} {answers[question.question_id] || "待选择"}
      </Text>
    );
  }

  function renderPassage() {
    if (!detail) return null;
    if (detail.question_type === "reading") {
      return <Text style={styles.passage}>{detail.passage}</Text>;
    }
    const segments: ReactNode[] = [];
    let cursor = 0;
    detail.questions.forEach((question) => {
      const order = questionOrder(question.question_id);
      const marker = markerFor(question.type, order);
      const escaped = marker.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const match = new RegExp(`${escaped}\\s*_{2,}`).exec(
        detail.passage.slice(cursor),
      );
      if (!match) return;
      const start = cursor + match.index;
      if (start > cursor) {
        segments.push(
          <Text key={`text-${cursor}`}>
            {detail.passage.slice(cursor, start)}
          </Text>,
        );
      }
      segments.push(blankNode(questionsByOrder.get(order) || question));
      cursor = start + match[0].length;
    });
    if (cursor < detail.passage.length) {
      segments.push(
        <Text key="passage-tail">{detail.passage.slice(cursor)}</Text>,
      );
    }
    return (
      <Text style={styles.passage} testID="review-passage">
        {segments}
      </Text>
    );
  }

  function choose(item: SessionItem, option: string) {
    setAnswers((current) => ({ ...current, [item.question_id]: option }));
  }

  async function submit() {
    if (!session || !detail || submitting) return;
    if (detail.target_question_ids.some((questionId) => !answers[questionId])) {
      setError("请先完成所有可作答错题。");
      return;
    }
    setSubmitting(true);
    setError("");
    try {
      for (const item of session.items) {
        await saveAnswer(
          session.session_id,
          item.question_id,
          answers[item.question_id],
        );
      }
      await submitPractice(session.session_id, crypto.randomUUID());
      router.replace({
        pathname: "/report",
        params: { session_id: session.session_id },
      });
    } catch (reason) {
      setError(String(reason));
    } finally {
      setSubmitting(false);
    }
  }

  if (error && (!detail || !session)) {
    return (
      <View style={styles.centered}>
        <Text style={styles.error}>{error}</Text>
        <Pressable style={styles.button} onPress={() => router.replace("/mistakes")}>
          <Text style={styles.buttonText}>返回错题本</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.center}>
      <View
        testID="review-shell"
        style={[styles.shell, { maxWidth: layout.contentMaxWidth }]}
      >
        <View style={styles.header}>
          <View>
            <Text style={styles.title}>错题重做</Text>
            <Text style={styles.meta}>
              {detail
                ? `${TYPE_LABELS[detail.question_type]} · ${detail.bank_name}`
                : "正在准备完整语篇…"}
            </Text>
          </View>
          <Pressable
            accessibilityRole="button"
            onPress={() => router.replace("/mistakes")}
            style={styles.button}
          >
            <Text style={styles.buttonText}>返回错题本</Text>
          </Pressable>
        </View>
        {loadingText(!detail || !session)}
        {detail ? renderPassage() : null}
        {detail && session ? (
          <View style={[styles.questions, { maxWidth: layout.bodyMaxWidth }]}>
            {detail.target_question_ids.map((questionId) => {
              const item = itemsByQuestion.get(questionId);
              const question = detail.questions.find(
                (candidate) => candidate.question_id === questionId,
              );
              if (!item || !question) return null;
              return (
                <View
                  key={questionId}
                  style={styles.question}
                  testID={`review-question-${questionId}`}
                >
                  <Text style={styles.stem}>
                    {question.label} · {item.stem}
                  </Text>
                  <View style={styles.options}>
                    {(item.options || []).map((option, index) => {
                      const value =
                        item.type === "gap_fill"
                          ? String.fromCharCode(65 + index)
                          : option;
                      const selected = answers[questionId] === value;
                      return (
                        <Pressable
                          accessibilityRole="button"
                          key={`${questionId}-${index}`}
                          onPress={() => choose(item, value)}
                          style={[
                            styles.option,
                            selected && styles.optionSelected,
                          ]}
                        >
                          <Text
                            style={[
                              styles.optionText,
                              selected && styles.optionTextSelected,
                            ]}
                          >
                            {String.fromCharCode(65 + index)}. {option}
                          </Text>
                        </Pressable>
                      );
                    })}
                  </View>
                </View>
              );
            })}
            {error ? <Text style={styles.error}>{error}</Text> : null}
            <Pressable
              accessibilityRole="button"
              disabled={submitting}
              onPress={submit}
              style={[styles.submit, submitting && styles.disabled]}
              testID="review-submit"
            >
              <Text style={styles.submitText}>
                {submitting ? "正在交卷" : "提交错题重做"}
              </Text>
            </Pressable>
          </View>
        ) : null}
      </View>
    </ScrollView>
  );
}

function loadingText(loading: boolean) {
  return loading ? <Text style={styles.loading}>正在加载…</Text> : null;
}

const styles = StyleSheet.create({
  page: { flex: 1, backgroundColor: tokens.color.pageBackground },
  center: { alignItems: "center" },
  centered: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: tokens.spacing.pageX,
    backgroundColor: tokens.color.pageBackground,
  },
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
  passage: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.passageFamily.web,
    fontSize: tokens.font.sizes.body,
    lineHeight: tokens.font.sizes.body * tokens.font.lineHeight.passage,
    marginTop: tokens.spacing.section,
  },
  lockedBlank: {
    color: tokens.color.tertiaryText,
    backgroundColor: tokens.color.cardBackground,
  },
  activeBlank: {
    color: tokens.color.accent,
    fontWeight: "600",
  },
  questions: { width: "100%", alignSelf: "center" },
  question: {
    borderTopWidth: tokens.border.width,
    borderTopColor: tokens.color.divider,
    marginTop: tokens.spacing.section,
    paddingTop: tokens.spacing.cardPadding,
  },
  stem: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    fontWeight: "600",
  },
  options: { gap: tokens.web_desktop.optionGap, marginTop: tokens.spacing.listGap },
  option: {
    minHeight: tokens.web_desktop.optionHeight,
    borderWidth: tokens.border.width,
    borderColor: tokens.color.secondaryBorder,
    borderRadius: tokens.radius.medium,
    justifyContent: "center",
    paddingHorizontal: tokens.web_desktop.optionPadding,
    paddingVertical: tokens.web_desktop.optionGap,
    backgroundColor: tokens.color.pageBackground,
  },
  optionSelected: {
    borderColor: tokens.color.primaryButtonBackground,
    backgroundColor: tokens.color.primaryButtonBackground,
  },
  optionText: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.web_desktop.optionFontSize,
    lineHeight:
      tokens.web_desktop.optionFontSize * tokens.web_desktop.optionLineHeight,
  },
  optionTextSelected: { color: tokens.color.primaryButtonText },
  submit: {
    minHeight: tokens.control.primaryButtonHeightMin,
    borderRadius: tokens.radius.medium,
    backgroundColor: tokens.color.primaryButtonBackground,
    justifyContent: "center",
    alignItems: "center",
    marginTop: tokens.spacing.section,
    paddingHorizontal: tokens.spacing.cardPadding,
  },
  submitText: {
    color: tokens.color.primaryButtonText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
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
  loading: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    marginTop: tokens.spacing.section,
  },
  disabled: { backgroundColor: tokens.color.disabled },
  error: {
    color: tokens.color.incorrect,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    marginTop: tokens.spacing.listGap,
  },
});
