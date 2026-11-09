import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import {
  getPractice,
  getPracticeReview,
  getReport,
  abandonPractice,
  saveAnswer,
  submitPractice,
  type PracticeReview,
  type PracticeSession,
  type SessionItem,
} from "../src/api/client";
import { getSession, setReport, setSession } from "../src/sessionStore";
import { tokens } from "../src/theme/tokens";
import { useResponsiveLayout } from "../src/theme/useResponsiveLayout";

const QUESTION_TYPE_LABELS = {
  cloze: "完形填空",
  grammar_fill: "语法填空",
  reading: "阅读理解",
  gap_fill: "七选五",
} as const;

type PassageGroup = {
  passageGroupId: string;
  items: SessionItem[];
};

function draftKey(sessionId: string) {
  return `practice-draft:${sessionId}`;
}

function groupPassages(items: SessionItem[]): PassageGroup[] {
  const groups: PassageGroup[] = [];
  for (const item of items) {
    const previous = groups[groups.length - 1];
    if (previous?.passageGroupId === item.passage_group_id) {
      previous.items.push(item);
      continue;
    }
    groups.push({ passageGroupId: item.passage_group_id, items: [item] });
  }
  return groups;
}

function splitOption(option: string, index: number) {
  const match = option.match(/^([A-G])\.\s*(.*)$/);
  return {
    label: match?.[1] || String.fromCharCode(65 + index),
    text: match?.[2] || option,
  };
}

function isCorrectOption(
  option: string,
  index: number,
  correctAnswer: string | string[],
) {
  const parsed = splitOption(option, index);
  const answers = Array.isArray(correctAnswer)
    ? correctAnswer
    : [correctAnswer];
  return answers.some((answer) => {
    const normalized = String(answer).trim().toLocaleLowerCase();
    return (
      option.trim().toLocaleLowerCase() === normalized ||
      parsed.text.trim().toLocaleLowerCase() === normalized ||
      parsed.label.trim().toLocaleLowerCase() === normalized
    );
  });
}

export default function PracticeScreen() {
  const layout = useResponsiveLayout();
  const params = useLocalSearchParams<{
    session_id?: string;
    review?: string;
    q?: string;
  }>();
  const routeSessionId = Array.isArray(params.session_id)
    ? params.session_id[0]
    : params.session_id;
  const reviewRequested = params.review === "1";
  const [session, setLocalSession] = useState<PracticeSession | null>(getSession());
  const [reviewSession, setReviewSession] = useState<PracticeReview | null>(null);
  const [reviewMode, setReviewMode] = useState(reviewRequested);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [remaining, setRemaining] = useState(0);
  const [error, setError] = useState("");
  const [dialogMode, setDialogMode] = useState<"submit" | "exit" | null>(null);

  useEffect(() => {
    if (!reviewRequested || !routeSessionId) return;
    Promise.all([
      getPracticeReview(routeSessionId),
      getReport(routeSessionId),
    ])
      .then(([review, report]) => {
        const correctAnswers = new Map(
          report.question_results.map((result) => [
            result.question_id,
            result.correct_answer,
          ]),
        );
        const reviewWithAnswers = {
          ...review,
          items: review.items.map((reviewItem) => ({
            ...reviewItem,
            correct_answer:
              reviewItem.correct_answer ??
              correctAnswers.get(reviewItem.question_id) ??
              "",
          })),
        };
        const requestedIndex = params.q
          ? Math.max(
              0,
              Math.min(review.items.length - 1, Number(params.q) - 1),
            )
          : 0;
        setReviewSession(reviewWithAnswers);
        setReviewMode(true);
        setCurrentIndex(requestedIndex);
        setAnswers(
          Object.fromEntries(
            review.items
              .filter((item) => item.saved_answer != null)
              .map((item) => [item.question_id, String(item.saved_answer)]),
          ),
        );
      })
      .catch((reason) => setError(String(reason)));
  }, [params.q, reviewRequested, routeSessionId]);

  useEffect(() => {
    if (!session) return;
    const draft = window.localStorage.getItem(draftKey(session.session_id));
    if (draft) {
      const parsed = JSON.parse(draft) as {
        answers?: Record<string, string>;
        currentIndex?: number;
      };
      setAnswers(parsed.answers || {});
      setCurrentIndex(parsed.currentIndex || 0);
    }
    const deadline = new Date(session.deadline).getTime();
    const serverNow = new Date(session.server_time).getTime();
    const offset = serverNow - Date.now();
    const update = () =>
      setRemaining(Math.max(0, Math.floor((deadline - Date.now() - offset) / 1000)));
    update();
    const timer = window.setInterval(update, 1000);
    const visibility = () => {
      if (document.visibilityState !== "visible") return;
      getPractice(session.session_id)
        .then((fresh) => {
          setSession(fresh);
          setLocalSession(fresh);
        })
        .catch((reason) => setError(String(reason)));
    };
    document.addEventListener("visibilitychange", visibility);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", visibility);
    };
  }, [session?.session_id]);

  useEffect(() => {
    if (!session || reviewMode) return;
    window.localStorage.setItem(
      draftKey(session.session_id),
      JSON.stringify({ answers, currentIndex }),
    );
  }, [answers, currentIndex, reviewMode, session?.session_id]);

  const activeSession = reviewSession || session;
  const items = activeSession?.items || [];
  const item = items[currentIndex];
  const groups = useMemo(() => groupPassages(items), [items]);
  const passageIndex = groups.findIndex((group) =>
    group.items.some((question) => question.question_id === item?.question_id),
  );
  const answered = Object.keys(answers).length;
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const timeText = `${minutes}:${String(seconds).padStart(2, "0")}`;
  const reviewItem = reviewSession?.items.find(
    (question) => question.question_id === item?.question_id,
  );
  const canViewReport =
    reviewMode ||
    session?.status === "submitted" ||
    session?.status === "expired" ||
    reviewSession?.status === "submitted" ||
    reviewSession?.status === "expired";

  const progressWidth = useMemo(() => {
    if (!activeSession) return "0%";
    return `${Math.round((answered / activeSession.items.length) * 100)}%` as `${number}%`;
  }, [activeSession, answered]);

  async function choose(answer: string) {
    if (!session || !item || reviewMode) return;
    setAnswers((current) => ({ ...current, [item.question_id]: answer }));
    try {
      await saveAnswer(session.session_id, item.question_id, answer);
      if (currentIndex < items.length - 1) {
        setCurrentIndex(currentIndex + 1);
      }
    } catch (reason) {
      setError(String(reason));
    }
  }

  async function submit() {
    if (!session) return;
    try {
      const key =
        window.localStorage.getItem(`submit:${session.session_id}`) ||
        crypto.randomUUID();
      window.localStorage.setItem(`submit:${session.session_id}`, key);
      const report = await submitPractice(session.session_id, key);
      setReport(report);
      window.localStorage.removeItem(draftKey(session.session_id));
      const submittedSession = { ...session, status: "submitted" as const };
      setSession(submittedSession);
      setLocalSession(submittedSession);
      setReviewMode(true);
      setDialogMode(null);
      router.replace({
        pathname: "/report",
        params: { session_id: session.session_id },
      });
    } catch (reason) {
      setError(String(reason));
    }
  }

  async function abandon() {
    if (!session) return;
    try {
      await abandonPractice(session.session_id);
      window.localStorage.removeItem(draftKey(session.session_id));
      window.localStorage.removeItem(`submit:${session.session_id}`);
      setSession(null);
      setLocalSession(null);
      router.replace("/");
    } catch (reason) {
      setError(String(reason));
    }
  }

  const reportHref = (activeSession?.session_id || routeSessionId) as string | undefined;
  const atFirst = currentIndex === 0;
  const atLast = currentIndex >= items.length - 1;
  const actionStyle = [styles.actionButton, layout.desktop && styles.actionDesktop];
  const actionTextStyle = [
    styles.actionText,
    layout.desktop && styles.actionTextDesktop,
  ];

  if (!activeSession || !item) {
    return (
      <View style={[styles.shell, { maxWidth: layout.contentMaxWidth }]}>
        <Text style={styles.meta}>{error || "没有进行中的练习。"}</Text>
        <Pressable style={styles.primaryButton} onPress={() => router.replace("/")}>
          <Text style={styles.primaryButtonText}>返回首页</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.center}>
      <View
        testID="practice-shell"
        style={[styles.shell, { maxWidth: layout.contentMaxWidth }]}
      >
        <View style={styles.header}>
          <View>
            <Text style={styles.bank}>
              {QUESTION_TYPE_LABELS[item.type] ?? "英语练习"}
            </Text>
            <Text style={styles.meta}>
              {reviewMode ? "已交卷" : timeText} · 已答 {answered} 题
            </Text>
          </View>
          <View style={styles.headerActions}>
            <Pressable
              accessibilityRole="button"
              disabled={atFirst || dialogMode !== null}
              onPress={() => setCurrentIndex((value) => Math.max(0, value - 1))}
              style={[actionStyle, (atFirst || dialogMode !== null) && styles.actionDisabled]}
            >
              <Text
                style={[
                  actionTextStyle,
                  (atFirst || dialogMode !== null) && styles.actionTextDisabled,
                ]}
              >
                上一题
              </Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              disabled={atLast || dialogMode !== null}
              onPress={() =>
                setCurrentIndex((value) => Math.min(items.length - 1, value + 1))
              }
              style={[actionStyle, (atLast || dialogMode !== null) && styles.actionDisabled]}
            >
              <Text
                style={[
                  actionTextStyle,
                  (atLast || dialogMode !== null) && styles.actionTextDisabled,
                ]}
              >
                下一题
              </Text>
            </Pressable>
            {canViewReport ? (
              <Pressable
                accessibilityRole="button"
                disabled={!reportHref}
                onPress={() =>
                  reportHref &&
                  router.push({
                    pathname: "/report",
                    params: {
                      session_id: reportHref,
                      anchor: String(currentIndex + 1),
                    },
                  })
                }
                style={actionStyle}
              >
                <Text style={actionTextStyle}>查看报告</Text>
              </Pressable>
            ) : (
              <Pressable
                accessibilityRole="button"
                onPress={() => setDialogMode("submit")}
                style={actionStyle}
              >
                <Text style={actionTextStyle}>交卷</Text>
              </Pressable>
            )}
            {!reviewMode ? (
              <Pressable
                accessibilityRole="button"
                onPress={() => setDialogMode("exit")}
                style={actionStyle}
              >
                <Text style={actionTextStyle}>退出</Text>
              </Pressable>
            ) : null}
          </View>
        </View>

        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: progressWidth }]} />
        </View>
        <Text style={styles.meta}>
          第 {currentIndex + 1} 题 / 共 {items.length} 题 · 第 {passageIndex + 1} 篇 / 共 {groups.length} 篇
        </Text>

        <View
          testID="reading-column"
          style={styles.readingColumn}
        >
          <View
            testID="passage-column"
            style={[
              styles.passageColumn,
              { maxWidth: layout.passageMaxWidth },
            ]}
          >
            <Text style={styles.passage}>{item.passage}</Text>
          </View>
          <View
            testID={`question-${item.question_id}`}
            style={[
              styles.questionBlock,
              { maxWidth: layout.bodyMaxWidth },
            ]}
          >
            <Text style={styles.stem}>
              {currentIndex + 1}. {item.stem}
            </Text>
            <View style={[styles.options, layout.desktop && styles.optionsDesktop]}>
              {(item.options || []).map((option, optionIndex) => {
                const parsed = splitOption(option, optionIndex);
                const selected = answers[item.question_id] === option;
                const correct =
                  reviewMode &&
                  reviewItem != null &&
                  isCorrectOption(
                    option,
                    optionIndex,
                    reviewItem.correct_answer,
                  );
                return (
                  <Pressable
                    key={option}
                    testID={
                      correct
                        ? `correct-option-${item.question_id}`
                        : undefined
                    }
                    accessibilityRole="button"
                    disabled={reviewMode}
                    onPress={() => choose(option)}
                    style={[
                      styles.option,
                      layout.desktop && styles.optionDesktop,
                      selected && styles.optionSelected,
                      correct && styles.optionCorrect,
                      reviewMode && styles.optionReadOnly,
                    ]}
                  >
                    <Text
                      style={[
                        styles.optionLabel,
                        layout.desktop && styles.optionTextDesktop,
                        selected && styles.optionTextSelected,
                        correct && styles.optionTextCorrect,
                      ]}
                    >
                      {parsed.label}
                    </Text>
                    <Text
                      style={[
                        styles.optionText,
                        layout.desktop && styles.optionTextDesktop,
                        selected && styles.optionTextSelected,
                        correct && styles.optionTextCorrect,
                      ]}
                    >
                      {parsed.text}
                    </Text>
                  </Pressable>
                );
              })}
            </View>
            {reviewMode && reviewItem ? (
              <>
                <Text
                  style={[
                    styles.reviewResult,
                    {
                      color: reviewItem.correct
                        ? tokens.color.correct
                        : tokens.color.incorrect,
                    },
                  ]}
                >
                  我的选择：{String(reviewItem.saved_answer || "未作答")} ·{" "}
                  {reviewItem.correct ? "正确" : "错误"}
                </Text>
                <Text style={styles.reviewExplanation}>
                  解析：{reviewItem.explanation}
                </Text>
              </>
            ) : null}
          </View>
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}
      </View>
      <Modal
        visible={dialogMode !== null}
        transparent
        animationType="fade"
        onRequestClose={() => setDialogMode(null)}
      >
        <View style={styles.modalBackdrop}>
          <View style={styles.modalCard}>
            <Text style={styles.confirmTitle}>
              {dialogMode === "exit" ? "退出本次练习？" : "确认交卷？"}
            </Text>
            <Text style={styles.meta}>
              {dialogMode === "exit"
                ? "退出后会删除本次题目和已答记录，不会保存报告。"
                : "未答题目将按空白计分，交卷后仍可查看报告。"}
            </Text>
            <View style={styles.modalActions}>
              <Pressable
                accessibilityRole="button"
                onPress={() => setDialogMode(null)}
                style={[styles.secondaryButton, layout.desktop && styles.actionDesktop]}
              >
                <Text style={actionTextStyle}>继续作答</Text>
              </Pressable>
              <Pressable
                accessibilityRole="button"
                onPress={dialogMode === "exit" ? abandon : submit}
                style={[styles.primaryButton, layout.desktop && styles.actionDesktop]}
              >
                <Text
                  style={[
                    styles.primaryButtonText,
                    layout.desktop && styles.actionTextDesktop,
                  ]}
                >
                  {dialogMode === "exit" ? "确认退出" : "确认交卷"}
                </Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
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
  headerActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    alignItems: "center",
    flexWrap: "wrap",
    gap: tokens.web_desktop.optionGap,
    marginLeft: "auto",
  },
  bank: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.subheading,
    fontWeight: "600",
  },
  actionButton: {
    minHeight: tokens.control.touchTargetMin,
    minWidth: tokens.control.touchTargetMin,
    borderWidth: tokens.border.width,
    borderColor: tokens.color.secondaryBorder,
    borderRadius: tokens.radius.medium,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: tokens.spacing.listGap,
  },
  actionDesktop: {
    height: tokens.web_desktop.buttonHeight,
    minHeight: tokens.web_desktop.buttonHeight,
  },
  actionDisabled: {
    backgroundColor: tokens.color.cardBackground,
    borderColor: tokens.color.divider,
  },
  actionText: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
  actionTextDesktop: { fontSize: tokens.web_desktop.optionFontSize },
  actionTextDisabled: { color: tokens.color.tertiaryText },
  progressTrack: {
    height: tokens.border.width,
    backgroundColor: tokens.color.divider,
    marginTop: tokens.spacing.listGap,
  },
  progressFill: {
    height: tokens.border.width,
    backgroundColor: tokens.color.accent,
  },
  meta: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    marginTop: tokens.spacing.listGap,
  },
  readingColumn: { width: "100%", alignSelf: "center" },
  passageColumn: { width: "100%", alignSelf: "center" },
  passage: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.passageFamily.web,
    fontSize: tokens.font.sizes.body,
    lineHeight: tokens.font.sizes.body * tokens.font.lineHeight.passage,
    marginTop: tokens.spacing.section,
  },
  questionBlock: {
    width: "100%",
    alignSelf: "center",
    borderTopWidth: tokens.border.width,
    borderTopColor: tokens.color.divider,
    marginTop: tokens.spacing.section,
    paddingTop: tokens.spacing.cardPadding,
  },
  stem: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    lineHeight: tokens.font.sizes.body * tokens.font.lineHeight.ui,
    fontWeight: "600",
  },
  options: { gap: tokens.spacing.listGap, marginTop: tokens.spacing.listGap },
  optionsDesktop: {
    gap: tokens.web_desktop.optionGap,
    marginTop: tokens.web_desktop.optionGap,
  },
  option: {
    minHeight: tokens.control.touchTargetMin,
    flexDirection: "row",
    alignItems: "center",
    borderWidth: tokens.border.width,
    borderColor: tokens.color.secondaryBorder,
    borderRadius: tokens.radius.medium,
    paddingHorizontal: tokens.spacing.cardPadding,
    paddingVertical: tokens.spacing.listGap,
    backgroundColor: tokens.color.pageBackground,
  },
  optionDesktop: {
    height: tokens.web_desktop.optionHeight,
    minHeight: tokens.web_desktop.optionHeight,
    paddingHorizontal: tokens.web_desktop.optionPadding,
    paddingVertical: 0,
  },
  optionSelected: {
    borderColor: tokens.color.primaryText,
    backgroundColor: tokens.color.primaryButtonBackground,
  },
  optionCorrect: {
    borderColor: tokens.color.correct,
    backgroundColor: tokens.color.correct,
  },
  optionReadOnly: { opacity: 0.9 },
  optionLabel: {
    width: 24,
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    fontWeight: "600",
  },
  optionText: {
    flex: 1,
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
  },
  optionTextDesktop: {
    fontSize: tokens.web_desktop.optionFontSize,
    lineHeight:
      tokens.web_desktop.optionFontSize * tokens.web_desktop.optionLineHeight,
  },
  optionTextSelected: { color: tokens.color.primaryButtonText },
  optionTextCorrect: { color: tokens.color.primaryButtonText },
  reviewResult: {
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    marginTop: tokens.spacing.listGap,
    fontWeight: "600",
  },
  reviewExplanation: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.passageFamily.web,
    fontSize: tokens.font.sizes.body,
    lineHeight: tokens.font.sizes.body * tokens.font.lineHeight.passage,
    marginTop: tokens.spacing.listGap,
  },
  primaryButton: {
    minHeight: tokens.control.primaryButtonHeightMin,
    minWidth: tokens.control.touchTargetMin,
    backgroundColor: tokens.color.primaryButtonBackground,
    borderRadius: tokens.radius.medium,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: tokens.spacing.cardPadding,
  },
  primaryButtonText: {
    color: tokens.color.primaryButtonText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
  },
  secondaryButton: {
    minHeight: tokens.control.primaryButtonHeightMin,
    minWidth: tokens.control.touchTargetMin,
    borderWidth: tokens.border.width,
    borderColor: tokens.color.secondaryBorder,
    backgroundColor: tokens.color.pageBackground,
    borderRadius: tokens.radius.medium,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: tokens.spacing.cardPadding,
  },
  modalBackdrop: {
    flex: 1,
    backgroundColor: tokens.color.modalBackdrop,
    justifyContent: "center",
    alignItems: "center",
    padding: tokens.spacing.pageX,
  },
  modalCard: {
    width: "100%",
    maxWidth: tokens.web_desktop.mobileMaxWidth,
    backgroundColor: tokens.color.pageBackground,
    borderWidth: tokens.border.width,
    borderColor: tokens.color.secondaryBorder,
    borderRadius: tokens.radius.large,
    padding: tokens.spacing.cardPadding,
  },
  modalActions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: tokens.web_desktop.optionGap,
    marginTop: tokens.spacing.section,
  },
  confirmTitle: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.sectionTitle,
  },
  error: {
    color: tokens.color.incorrect,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    marginTop: tokens.spacing.listGap,
  },
});
