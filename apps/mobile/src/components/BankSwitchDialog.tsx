import { useEffect, useState } from "react";
import { Modal, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import {
  activateBank,
  getSwitchableBanks,
  type SwitchableBank,
  type SwitchableBanks,
} from "../api/client";
import { tokens } from "../theme/tokens";

type BankSwitchDialogProps = {
  visible: boolean;
  onCancel: () => void;
  onSwitched: () => Promise<void> | void;
};

const STATUS_LABELS: Record<string, string> = {
  active: "当前启用",
  ready: "就绪",
  archived: "历史归档",
};

export function BankSwitchDialog({
  visible,
  onCancel,
  onSwitched,
}: BankSwitchDialogProps) {
  const [data, setData] = useState<SwitchableBanks | null>(null);
  const [selected, setSelected] = useState<SwitchableBank | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!visible) {
      setData(null);
      setSelected(null);
      setError("");
      setBusy(false);
      return;
    }
    getSwitchableBanks()
      .then(setData)
      .catch((reason) => setError(String(reason)));
  }, [visible]);

  const current = data?.banks.find((bank) => bank.is_current) || null;

  async function executeSwitch() {
    if (!selected) return;
    setBusy(true);
    setError("");
    try {
      await activateBank(selected.bank_id);
      await onSwitched();
      onCancel();
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      animationType="fade"
      transparent
      visible={visible}
      onRequestClose={onCancel}
    >
      <View style={styles.backdrop}>
        <View style={styles.dialog} testID="bank-switch-dialog">
          {!selected ? (
            <>
              <Text style={styles.title}>切换题库</Text>
              <Text style={styles.intro}>选择要启用的题库；当前题库不可重复选择。</Text>
              <ScrollView style={styles.list}>
                {data?.banks.map((bank) => (
                  <Pressable
                    accessibilityRole="button"
                    disabled={bank.is_current}
                    key={bank.bank_id}
                    onPress={() => setSelected(bank)}
                    style={[
                      styles.bankRow,
                      bank.is_current && styles.currentBank,
                    ]}
                    testID={`bank-option-${bank.bank_id}`}
                  >
                    <View style={styles.bankText}>
                      <Text style={styles.bankName}>
                        {bank.name} · v{bank.version}
                      </Text>
                      <Text style={styles.bankMeta}>
                        {bank.question_count} 题 ·{" "}
                        {STATUS_LABELS[bank.status] || bank.status}
                      </Text>
                    </View>
                    <Text style={styles.currentMark}>
                      {bank.is_current ? "✓ 当前" : "选择"}
                    </Text>
                  </Pressable>
                ))}
              </ScrollView>
              {error ? <Text style={styles.error}>{error}</Text> : null}
              <View style={styles.actions}>
                <Pressable
                  accessibilityRole="button"
                  onPress={onCancel}
                  style={styles.secondaryButton}
                  testID="bank-switch-cancel"
                >
                  <Text style={styles.secondaryText}>取消</Text>
                </Pressable>
              </View>
            </>
          ) : (
            <>
              <Text style={styles.title}>确认切换题库</Text>
              <Text style={styles.confirmText}>
                将从 {current?.name}（{current?.question_count} 题）切换到{" "}
                {selected.name}（{selected.question_count} 题）。
              </Text>
              <Text style={styles.confirmText}>
                覆盖统计的分母将变为 {selected.question_count} 题；已做过的相同题目仍计入做过。
              </Text>
              <Text style={styles.confirmText}>
                {current?.name} 的错题将移入错题本的“历史题库”分组，不会丢失。
              </Text>
              <Text style={styles.confirmText}>历史报告不受影响。</Text>
              <Text style={styles.warning}>
                此操作会改变当前题库，确认后立即生效。
              </Text>
              {data && data.in_progress_count > 0 ? (
                <Text style={styles.notice}>
                  当前有 {data.in_progress_count} 个未完成的练习，切换后仍可用原题库继续交卷，新开始的练习将使用新题库。
                </Text>
              ) : null}
              {error ? <Text style={styles.error}>{error}</Text> : null}
              <View style={styles.actions}>
                <Pressable
                  accessibilityRole="button"
                  onPress={onCancel}
                  style={styles.secondaryButton}
                  testID="bank-switch-confirm-cancel"
                >
                  <Text style={styles.secondaryText}>取消</Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  disabled={busy}
                  onPress={executeSwitch}
                  style={[styles.primaryButton, busy && styles.disabled]}
                  testID="bank-switch-confirm"
                >
                  <Text style={styles.primaryText}>
                    {busy ? "正在切换" : "确认切换"}
                  </Text>
                </Pressable>
              </View>
            </>
          )}
        </View>
      </View>
    </Modal>
  );
}

const styles = StyleSheet.create({
  backdrop: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: tokens.color.modalBackdrop,
    padding: tokens.spacing.pageX,
  },
  dialog: {
    width: "100%",
    maxWidth: 560,
    maxHeight: "82%",
    borderWidth: tokens.border.width,
    borderColor: tokens.color.secondaryBorder,
    borderRadius: tokens.radius.large,
    backgroundColor: tokens.color.pageBackground,
    padding: tokens.spacing.cardPadding,
  },
  title: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.sectionTitle,
    fontWeight: "600",
  },
  intro: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    marginTop: tokens.spacing.listGap,
  },
  list: { marginTop: tokens.spacing.cardPadding },
  bankRow: {
    minHeight: tokens.control.touchTargetMin,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: tokens.spacing.listGap,
    borderTopWidth: tokens.border.width,
    borderTopColor: tokens.color.divider,
    paddingVertical: tokens.spacing.listGap,
  },
  currentBank: { opacity: 0.7 },
  bankText: { flex: 1 },
  bankName: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    fontWeight: "600",
  },
  bankMeta: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    marginTop: tokens.spacing.listGap,
  },
  currentMark: {
    color: tokens.color.accent,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
  confirmText: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    lineHeight: tokens.font.sizes.body * tokens.font.lineHeight.ui,
    marginTop: tokens.spacing.listGap,
  },
  warning: {
    color: tokens.color.incorrect,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    fontWeight: "600",
    marginTop: tokens.spacing.cardPadding,
  },
  notice: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    lineHeight: tokens.font.sizes.auxiliary * tokens.font.lineHeight.ui,
    marginTop: tokens.spacing.listGap,
  },
  actions: {
    flexDirection: "row",
    justifyContent: "flex-end",
    flexWrap: "wrap",
    gap: tokens.web_desktop.optionGap,
    marginTop: tokens.spacing.section,
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
  secondaryText: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
  primaryButton: {
    minHeight: tokens.control.touchTargetMin,
    borderRadius: tokens.radius.medium,
    justifyContent: "center",
    alignItems: "center",
    backgroundColor: tokens.color.primaryButtonBackground,
    paddingHorizontal: tokens.spacing.cardPadding,
  },
  primaryText: {
    color: tokens.color.primaryButtonText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
  disabled: { backgroundColor: tokens.color.disabled },
  error: {
    color: tokens.color.incorrect,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    marginTop: tokens.spacing.listGap,
  },
});
