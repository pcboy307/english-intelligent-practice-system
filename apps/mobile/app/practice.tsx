import { router, useLocalSearchParams } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import { Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import {
  getPractice,
  getPracticeReview,
  saveAnswer,
  submitPractice,
  type PracticeSession,
  type PracticeReview,
  type ReviewItem,
  type SessionItem,
} from "../src/api/client";
import { getSession, setReport, setSession } from "../src/sessionStore";
import { tokens } from "../src/theme/tokens";
import { useResponsiveLayout } from "../src/theme/useResponsiveLayout";

type PassageGroup = {
  passageGroupId: string;
  passage: string;
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
    groups.push({
      passageGroupId: item.passage_group_id,
      passage: item.passage,
      items: [item],
    });
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
  const [groupIndex, setGroupIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [remaining, setRemaining] = useState(0);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!reviewRequested || !routeSessionId) return;
    getPracticeReview(routeSessionId)
      .then((review) => {
        setReviewSession(review);
        setReviewMode(true);
        setAnswers(
          Object.fromEntries(
            review.items
              .filter((item) => item.saved_answer != null)
              .map((item) => [item.question_id, String(item.saved_answer)]),
          ),
        );
      })
      .catch((reason) => setError(String(reason)));
  }, [reviewRequested, routeSessionId]);

  useEffect(() => {
    if (!session) return;
    const draft = window.localStorage.getItem(draftKey(session.session_id));
    if (draft) {
      const parsed = JSON.parse(draft) as {
        answers?: Record<string, string>;
        groupIndex?: number;
      };
      setAnswers(parsed.answers || {});
      setGroupIndex(parsed.groupIndex || 0);
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
    if (!session) return;
    window.localStorage.setItem(
      draftKey(session.session_id),
      JSON.stringify({ answers, groupIndex }),
    );
  }, [answers, groupIndex, session?.session_id]);

  const activeSession = reviewSession || session;
  const groups = useMemo(
    () => groupPassages(activeSession?.items || []),
    [activeSession],
  );
  const group = groups[groupIndex];
  const reviewById = useMemo(
    () =>
      new Map<string, ReviewItem>(
        (reviewSession?.items || []).map((item) => [item.question_id, item]),
      ),
    [reviewSession],
  );
  const answered = Object.keys(answers).length;
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const timeText = `${minutes}:${String(seconds).padStart(2, "0")}`;
  const groupStart = groups
    .slice(0, groupIndex)
    .reduce((total, current) => total + current.items.length, 0);
  const requestedQuestionId = useMemo(() => {
    if (!reviewSession || !params.q) return null;
    const requestedIndex = Math.max(
      0,
      Math.min(reviewSession.items.length - 1, Number(params.q) - 1),
    );
    return reviewSession.items[requestedIndex]?.question_id || null;
  }, [params.q, reviewSession]);

  const progressWidth = useMemo(() => {
    if (!activeSession) return "0%";
    return `${Math.round((answered / activeSession.items.length) * 100)}%` as `${number}%`;
  }, [activeSession, answered]);

  useEffect(() => {
    if (!requestedQuestionId) return;
    const targetGroupIndex = groups.findIndex((item) =>
      item.items.some((question) => question.question_id === requestedQuestionId),
    );
    if (targetGroupIndex >= 0 && targetGroupIndex !== groupIndex) {
      setGroupIndex(targetGroupIndex);
      return;
    }
    const timer = window.setTimeout(() => {
      document
        .querySelector(`[data-testid="question-${requestedQuestionId}"]`)
        ?.scrollIntoView({ block: "start" });
    }, 0);
    return () => window.clearTimeout(timer);
  }, [groupIndex, groups, requestedQuestionId]);

  async function choose(item: SessionItem, answer: string) {
    if (!session || reviewMode) return;
    setAnswers((current) => ({ ...current, [item.question_id]: answer }));
    try {
      await saveAnswer(session.session_id, item.question_id, answer);
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
      const review = await getPracticeReview(session.session_id);
      setReviewSession(review);
      setReviewMode(true);
      setConfirming(false);
    } catch (reason) {
      setError(String(reason));
    }
  }

  const activeSessionId = reviewSession?.session_id || session?.session_id;
  const canViewReport =
    reviewMode ||
    session?.status === "submitted" ||
    session?.status === "expired" ||
    reviewSession?.status === "submitted" ||
    reviewSession?.status === "expired";

  if (!activeSession || !group) {
    return (
      <View
        testID="practice-shell"
        style={[styles.shell, { maxWidth: layout.contentMaxWidth }]}
      >
        <Text style={styles.meta}>没有进行中的练习。</Text>
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
        <View style={styles.topRow}>
          <Text style={styles.bank}>{activeSession.bank_name}</Text>
          <Text style={styles.timer}>{reviewMode ? "已交卷" : timeText}</Text>
        </View>
        <Pressable
          accessibilityRole="button"
          disabled={!canViewReport || !activeSessionId}
          onPress={() =>
            activeSessionId &&
            router.push({
              pathname: "/report",
              params: { session_id: activeSessionId },
            })
          }
          style={[
            styles.reportButton,
            layout.desktop && styles.buttonDesktop,
            !canViewReport && styles.reportButtonDisabled,
          ]}
        >
          <Text
            style={[
              styles.reportButtonText,
              !canViewReport && styles.reportButtonTextDisabled,
            ]}
          >
            {canViewReport ? "查看报告" : "交卷后可查看报告"}
          </Text>
        </Pressable>
        <View style={styles.progressTrack}>
          <View style={[styles.progressFill, { width: progressWidth }]} />
        </View>
        <Text style={styles.meta}>
          第 {groupIndex + 1} 篇 / 共 {groups.length} 篇 · 已答 {answered} 题
        </Text>

        <View
          testID="reading-column"
          style={[styles.readingColumn, { maxWidth: layout.bodyMaxWidth }]}
        >
          <Text style={styles.passage}>{group.passage}</Text>
          {group.items.map((item, itemIndex) => (
            <View
              key={item.question_id}
              testID={`question-${item.question_id}`}
              style={styles.questionBlock}
            >
              <Text style={styles.stem}>
                {groupStart + itemIndex + 1}. {item.stem}
              </Text>
              <View style={[styles.options, layout.desktop && styles.optionsDesktop]}>
                {(item.options || []).map((option, optionIndex) => {
                  const parsed = splitOption(option, optionIndex);
                  const selected = answers[item.question_id] === option;
                  return (
                    <Pressable
                      key={option}
                      accessibilityRole="button"
                      disabled={reviewMode}
                      onPress={() => choose(item, option)}
                      style={[
                        styles.option,
                        layout.desktop && styles.optionDesktop,
                        selected && styles.optionSelected,
                        reviewMode && styles.optionReadOnly,
                      ]}
                    >
                      <Text
                        style={[
                          styles.optionLabel,
                          layout.desktop && styles.optionTextDesktop,
                          selected && styles.optionTextSelected,
                        ]}
                      >
                        {parsed.label}
                      </Text>
                      <Text
                        style={[
                          styles.optionText,
                          layout.desktop && styles.optionTextDesktop,
                          selected && styles.optionTextSelected,
                        ]}
                      >
                        {parsed.text}
                      </Text>
                    </Pressable>
                  );
                })}
              </View>
              {reviewMode && reviewById.has(item.question_id) ? (
                <Text
                  style={[
                    styles.reviewResult,
                    {
                      color: reviewById.get(item.question_id)?.correct
                        ? tokens.color.correct
                        : tokens.color.incorrect,
                    },
                  ]}
                >
                  我的选择：{String(reviewById.get(item.question_id)?.saved_answer || "未作答")}
                  {" · "}
                  {reviewById.get(item.question_id)?.correct ? "正确" : "错误"}
                </Text>
              ) : null}
            </View>
          ))}
        </View>

        {error ? <Text style={styles.error}>{error}</Text> : null}
        <View style={styles.actions}>
          {reviewMode ? (
            <Pressable
              onPress={() =>
                activeSessionId &&
                router.push({
                  pathname: "/report",
                  params: { session_id: activeSessionId },
                })
              }
              style={[styles.primaryButton, layout.desktop && styles.buttonDesktop]}
            >
              <Text style={styles.primaryButtonText}>查看报告</Text>
            </Pressable>
          ) : groupIndex < groups.length - 1 ? (
            <Pressable
              onPress={() => setGroupIndex((value) => value + 1)}
              style={[styles.primaryButton, layout.desktop && styles.buttonDesktop]}
            >
              <Text style={styles.primaryButtonText}>下一篇</Text>
            </Pressable>
          ) : (
            <Pressable
              onPress={() => setConfirming(true)}
              style={[styles.primaryButton, layout.desktop && styles.buttonDesktop]}
            >
              <Text style={styles.primaryButtonText}>交卷</Text>
            </Pressable>
          )}
        </View>
        {confirming ? (
          <View style={styles.confirm}>
            <Text style={styles.confirmTitle}>确认交卷？</Text>
            <Text style={styles.meta}>未答题目将按空白计分。</Text>
            <View style={styles.actions}>
              <Pressable
                onPress={() => setConfirming(false)}
                style={[
                  styles.secondaryButton,
                  layout.desktop && styles.buttonDesktop,
                ]}
              >
                <Text style={styles.secondaryButtonText}>继续作答</Text>
              </Pressable>
              <Pressable
                onPress={submit}
                style={[styles.primaryButton, layout.desktop && styles.buttonDesktop]}
              >
                <Text style={styles.primaryButtonText}>确认交卷</Text>
              </Pressable>
            </View>
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
  topRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  bank: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.subheading,
    fontWeight: "600",
  },
  timer: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.subheading,
  },
  reportButton: {
    minHeight: tokens.control.primaryButtonHeightMin,
    borderWidth: tokens.border.width,
    borderColor: tokens.color.secondaryBorder,
    borderRadius: tokens.radius.medium,
    justifyContent: "center",
    alignItems: "center",
    marginTop: tokens.spacing.listGap,
    paddingHorizontal: tokens.spacing.cardPadding,
  },
  reportButtonDisabled: { backgroundColor: tokens.color.cardBackground },
  buttonDesktop: {
    height: tokens.web_desktop.buttonHeight,
    minHeight: tokens.web_desktop.buttonHeight,
  },
  reportButtonText: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
  },
  reportButtonTextDisabled: { color: tokens.color.tertiaryText },
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
  passage: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.passageFamily.web,
    fontSize: tokens.font.sizes.body,
    lineHeight: tokens.font.sizes.body * tokens.font.lineHeight.passage,
    marginTop: tokens.spacing.section,
  },
  questionBlock: {
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
  optionTextSelected: { color: tokens.color.primaryButtonText },
  optionTextDesktop: {
    fontSize: tokens.web_desktop.optionFontSize,
    lineHeight:
      tokens.web_desktop.optionFontSize * tokens.web_desktop.optionLineHeight,
  },
  reviewResult: {
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    marginTop: tokens.spacing.listGap,
    fontWeight: "600",
  },
  actions: {
    flexDirection: "row",
    gap: tokens.spacing.listGap,
    marginTop: tokens.spacing.section,
  },
  primaryButton: {
    minHeight: tokens.control.primaryButtonHeightMin,
    minWidth: tokens.control.touchTargetMin,
    backgroundColor: tokens.color.primaryButtonBackground,
    borderRadius: tokens.radius.medium,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: tokens.spacing.cardPadding,
    flex: 1,
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
    flex: 1,
  },
  secondaryButtonText: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
  },
  confirm: {
    borderTopWidth: tokens.border.width,
    borderColor: tokens.color.divider,
    marginTop: tokens.spacing.section,
    paddingTop: tokens.spacing.section,
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
