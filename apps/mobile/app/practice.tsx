import { router } from "expo-router";
import { useEffect, useMemo, useState } from "react";
import {
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import {
  getPractice,
  saveAnswer,
  submitPractice,
  type PracticeSession,
} from "../src/api/client";
import { getSession, setReport, setSession } from "../src/sessionStore";
import { tokens } from "../src/theme/tokens";

function draftKey(sessionId: string) {
  return `practice-draft:${sessionId}`;
}

export default function PracticeScreen() {
  const [session, setLocalSession] = useState<PracticeSession | null>(getSession());
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [remaining, setRemaining] = useState(0);
  const [error, setError] = useState("");
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    if (!session) return;
    const draft = window.localStorage.getItem(draftKey(session.session_id));
    if (draft) {
      const parsed = JSON.parse(draft) as { answers?: Record<string, string>; index?: number };
      setAnswers(parsed.answers || {});
      setIndex(parsed.index || 0);
    }
    const deadline = new Date(session.deadline).getTime();
    const serverNow = new Date(session.server_time).getTime();
    const offset = serverNow - Date.now();
    const update = () => setRemaining(Math.max(0, Math.floor((deadline - Date.now() - offset) / 1000)));
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
      JSON.stringify({ answers, index }),
    );
  }, [answers, index, session?.session_id]);

  const item = session?.items[index];
  const answered = Object.keys(answers).length;
  const minutes = Math.floor(remaining / 60);
  const seconds = remaining % 60;
  const timeText = `${minutes}:${String(seconds).padStart(2, "0")}`;

  const progressWidth = useMemo(() => {
    if (!session) return "0%";
    return `${Math.round((answered / session.items.length) * 100)}%` as `${number}%`;
  }, [answered, session]);

  async function choose(answer: string) {
    if (!item || !session) return;
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
      const key = window.localStorage.getItem(`submit:${session.session_id}`) || crypto.randomUUID();
      window.localStorage.setItem(`submit:${session.session_id}`, key);
      const report = await submitPractice(session.session_id, key);
      setReport(report);
      window.localStorage.removeItem(draftKey(session.session_id));
      router.replace("/report");
    } catch (reason) {
      setError(String(reason));
    }
  }

  if (!session || !item) {
    return (
      <View style={styles.shell}>
        <Text style={styles.meta}>没有进行中的练习。</Text>
        <Pressable style={styles.primaryButton} onPress={() => router.replace("/")}>
          <Text style={styles.primaryButtonText}>返回首页</Text>
        </Pressable>
      </View>
    );
  }

  return (
    <ScrollView style={styles.page} contentContainerStyle={styles.center}>
      <View style={styles.shell}>
        <View style={styles.topRow}>
          <Text style={styles.bank}>{session.bank_name}</Text>
          <Text style={styles.timer}>{timeText}</Text>
        </View>
        <View style={styles.progressTrack}><View style={[styles.progressFill, { width: progressWidth }]} /></View>
        <Text style={styles.meta}>第 {index + 1} / {session.items.length} 题 · 已回答 {answered} 题</Text>
        <Text style={styles.passage}>{item.passage}</Text>
        <Text style={styles.stem}>{item.stem}</Text>
        {item.options ? (
          <View style={styles.options}>
            {item.options.map((option) => {
              const selected = answers[item.question_id] === option || answers[item.question_id] === option.slice(0, 1);
              return (
                <Pressable
                  key={option}
                  accessibilityRole="button"
                  onPress={() => choose(option)}
                  style={[styles.option, selected && styles.optionSelected]}
                >
                  <Text style={[styles.optionText, selected && styles.optionTextSelected]}>{option}</Text>
                </Pressable>
              );
            })}
          </View>
        ) : (
          <TextInput
            value={answers[item.question_id] || ""}
            onChangeText={choose}
            placeholder="输入答案"
            placeholderTextColor={tokens.color.tertiaryText}
            style={styles.input}
          />
        )}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <View style={styles.actions}>
          <Pressable
            disabled={index === 0}
            onPress={() => setIndex((value) => Math.max(0, value - 1))}
            style={[styles.secondaryButton, index === 0 && styles.disabled]}
          >
            <Text style={styles.secondaryButtonText}>上一题</Text>
          </Pressable>
          {index < session.items.length - 1 ? (
            <Pressable onPress={() => setIndex((value) => value + 1)} style={styles.primaryButton}>
              <Text style={styles.primaryButtonText}>下一题</Text>
            </Pressable>
          ) : (
            <Pressable onPress={() => setConfirming(true)} style={styles.primaryButton}>
              <Text style={styles.primaryButtonText}>交卷</Text>
            </Pressable>
          )}
        </View>
        {confirming ? (
          <View style={styles.confirm}>
            <Text style={styles.confirmTitle}>确认交卷？</Text>
            <Text style={styles.meta}>未答题目将按空白计分。</Text>
            <View style={styles.actions}>
              <Pressable onPress={() => setConfirming(false)} style={styles.secondaryButton}>
                <Text style={styles.secondaryButtonText}>继续作答</Text>
              </Pressable>
              <Pressable onPress={submit} style={styles.primaryButton}>
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
    maxWidth: tokens.web.maxContentWidth,
    paddingHorizontal: tokens.spacing.pageX,
    paddingVertical: tokens.spacing.section,
  },
  topRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  bank: { color: tokens.color.primaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.subheading, fontWeight: "600" },
  timer: { color: tokens.color.primaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.subheading },
  progressTrack: { height: tokens.border.width, backgroundColor: tokens.color.divider, marginTop: tokens.spacing.listGap },
  progressFill: { height: tokens.border.width, backgroundColor: tokens.color.accent },
  meta: { color: tokens.color.secondaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.auxiliary, marginTop: tokens.spacing.listGap },
  passage: { color: tokens.color.primaryText, fontFamily: tokens.font.passageFamily.web, fontSize: tokens.font.sizes.body, lineHeight: tokens.font.sizes.body * tokens.font.lineHeight.passage, marginTop: tokens.spacing.section },
  stem: { color: tokens.color.primaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.body, lineHeight: tokens.font.sizes.body * tokens.font.lineHeight.ui, marginTop: tokens.spacing.section, fontWeight: "600" },
  options: { gap: tokens.spacing.listGap, marginTop: tokens.spacing.listGap },
  option: { minHeight: tokens.control.touchTargetMin, borderWidth: tokens.border.width, borderColor: tokens.color.secondaryBorder, borderRadius: tokens.radius.medium, padding: tokens.spacing.cardPadding, backgroundColor: tokens.color.pageBackground },
  optionSelected: { borderColor: tokens.color.primaryText, backgroundColor: tokens.color.primaryButtonBackground },
  optionText: { color: tokens.color.primaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.body },
  optionTextSelected: { color: tokens.color.primaryButtonText },
  input: { minHeight: tokens.control.primaryButtonHeightMin, borderWidth: tokens.border.width, borderColor: tokens.color.secondaryBorder, borderRadius: tokens.radius.medium, paddingHorizontal: tokens.spacing.cardPadding, marginTop: tokens.spacing.listGap, color: tokens.color.primaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.body },
  actions: { flexDirection: "row", gap: tokens.spacing.listGap, marginTop: tokens.spacing.section },
  primaryButton: { minHeight: tokens.control.primaryButtonHeightMin, minWidth: tokens.control.touchTargetMin, backgroundColor: tokens.color.primaryButtonBackground, borderRadius: tokens.radius.medium, justifyContent: "center", alignItems: "center", paddingHorizontal: tokens.spacing.cardPadding, flex: 1 },
  primaryButtonText: { color: tokens.color.primaryButtonText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.body },
  secondaryButton: { minHeight: tokens.control.primaryButtonHeightMin, minWidth: tokens.control.touchTargetMin, borderWidth: tokens.border.width, borderColor: tokens.color.secondaryBorder, backgroundColor: tokens.color.pageBackground, borderRadius: tokens.radius.medium, justifyContent: "center", alignItems: "center", paddingHorizontal: tokens.spacing.cardPadding, flex: 1 },
  secondaryButtonText: { color: tokens.color.primaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.body },
  disabled: { backgroundColor: tokens.color.disabled },
  confirm: { borderTopWidth: tokens.border.width, borderColor: tokens.color.divider, marginTop: tokens.spacing.section, paddingTop: tokens.spacing.section },
  confirmTitle: { color: tokens.color.primaryText, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.sectionTitle },
  error: { color: tokens.color.incorrect, fontFamily: tokens.font.uiFamily.web, fontSize: tokens.font.sizes.auxiliary, marginTop: tokens.spacing.listGap },
});
