import { useEffect, useState } from "react";
import {
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";

import { tokens } from "../theme/tokens";

type MaintenanceDialogProps = {
  visible: boolean;
  title: string;
  intro: string;
  onCancel: () => void;
  loadPreview: (adminToken: string) => Promise<string>;
  onConfirm: (adminToken: string) => Promise<void>;
};

export function MaintenanceDialog({
  visible,
  title,
  intro,
  onCancel,
  loadPreview,
  onConfirm,
}: MaintenanceDialogProps) {
  const [token, setToken] = useState("");
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!visible) {
      setToken("");
      setPreview("");
      setError("");
      setBusy(false);
    }
  }, [visible]);

  async function readPreview() {
    if (!token.trim()) {
      setError("请输入本机管理口令。");
      return;
    }
    setBusy(true);
    setError("");
    try {
      setPreview(await loadPreview(token));
    } catch (reason) {
      setError(String(reason));
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    setBusy(true);
    setError("");
    try {
      await onConfirm(token);
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
        <View style={styles.dialog} testID="maintenance-dialog">
          <Text style={styles.title}>{title}</Text>
          <Text style={styles.body}>{intro}</Text>
          <Text style={styles.label}>本机管理口令</Text>
          <TextInput
            value={token}
            onChangeText={setToken}
            secureTextEntry
            autoCapitalize="none"
            autoCorrect={false}
            style={styles.input}
            testID="maintenance-admin-token"
            placeholder="仅用于本次本机校验"
            placeholderTextColor={tokens.color.tertiaryText}
          />
          {preview ? (
            <Text style={styles.preview} testID="maintenance-preview">
              {preview}
            </Text>
          ) : null}
          {error ? <Text style={styles.error}>{error}</Text> : null}
          <View style={styles.actions}>
            <Pressable
              accessibilityRole="button"
              disabled={busy}
              onPress={onCancel}
              style={styles.secondaryButton}
              testID="maintenance-cancel"
            >
              <Text style={styles.secondaryText}>取消</Text>
            </Pressable>
            {preview ? (
              <Pressable
                accessibilityRole="button"
                disabled={busy}
                onPress={confirm}
                style={[styles.dangerButton, busy && styles.disabled]}
                testID="maintenance-confirm"
              >
                <Text style={styles.dangerText}>
                  {busy ? "正在执行" : "确认，此操作不可恢复"}
                </Text>
              </Pressable>
            ) : (
              <Pressable
                accessibilityRole="button"
                disabled={busy}
                onPress={readPreview}
                style={[styles.primaryButton, busy && styles.disabled]}
                testID="maintenance-load-preview"
              >
                <Text style={styles.primaryText}>
                  {busy ? "正在读取" : "读取实际条数"}
                </Text>
              </Pressable>
            )}
          </View>
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
    maxWidth: tokens.web_desktop.mobileMaxWidth,
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
  body: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    lineHeight: tokens.font.sizes.body * tokens.font.lineHeight.ui,
    marginTop: tokens.spacing.listGap,
  },
  label: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    marginTop: tokens.spacing.section,
  },
  input: {
    minHeight: tokens.control.primaryButtonHeightMin,
    borderWidth: tokens.border.width,
    borderColor: tokens.color.secondaryBorder,
    borderRadius: tokens.radius.medium,
    color: tokens.color.primaryText,
    backgroundColor: tokens.color.cardBackground,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    marginTop: tokens.spacing.listGap,
    paddingHorizontal: tokens.spacing.listGap,
  },
  preview: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    lineHeight: tokens.font.sizes.body * tokens.font.lineHeight.ui,
    marginTop: tokens.spacing.cardPadding,
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
  dangerButton: {
    minHeight: tokens.control.touchTargetMin,
    borderWidth: tokens.border.width,
    borderColor: tokens.color.incorrect,
    borderRadius: tokens.radius.medium,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: tokens.spacing.cardPadding,
  },
  dangerText: {
    color: tokens.color.incorrect,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
  disabled: {
    backgroundColor: tokens.color.disabled,
    borderColor: tokens.color.disabled,
  },
  error: {
    color: tokens.color.incorrect,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    marginTop: tokens.spacing.listGap,
  },
});
