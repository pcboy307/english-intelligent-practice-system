import { useEffect, useRef, useState } from "react";
import {
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { tokens } from "../theme/tokens";

type MaintenanceDialogProps = {
  visible: boolean;
  title: string;
  intro: string;
  onCancel: () => void;
  loadPreview: () => Promise<string>;
  onConfirm: () => Promise<void>;
};

export function MaintenanceDialog({
  visible,
  title,
  intro,
  onCancel,
  loadPreview,
  onConfirm,
}: MaintenanceDialogProps) {
  const [preview, setPreview] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [confirmReady, setConfirmReady] = useState(false);
  const loaderRef = useRef(loadPreview);
  loaderRef.current = loadPreview;

  useEffect(() => {
    if (!visible) {
      setPreview("");
      setError("");
      setBusy(false);
      setConfirmReady(false);
      return;
    }
    let active = true;
    const delay = setTimeout(() => setConfirmReady(true), 1500);
    loaderRef
      .current()
      .then((text) => {
        if (active) setPreview(text);
      })
      .catch((reason) => {
        if (active) setError(String(reason));
      });
    return () => {
      active = false;
      clearTimeout(delay);
    };
  }, [visible]);

  async function confirm() {
    setBusy(true);
    setError("");
    try {
      await onConfirm();
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
          {preview ? (
            <Text style={styles.preview} testID="maintenance-preview">
              {preview}
            </Text>
          ) : !error ? (
            <Text style={styles.loading}>正在读取实际条数…</Text>
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
            <Pressable
              accessibilityRole="button"
              disabled={busy || !preview || !confirmReady}
              onPress={confirm}
              style={[
                styles.dangerButton,
                (busy || !preview || !confirmReady) && styles.disabled,
              ]}
              testID="maintenance-confirm"
            >
              <Text style={styles.dangerText}>
                {busy
                  ? "正在执行"
                  : confirmReady
                    ? "确认，此操作不可恢复"
                    : "请稍候…"}
              </Text>
            </Pressable>
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
  preview: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    lineHeight: tokens.font.sizes.body * tokens.font.lineHeight.ui,
    marginTop: tokens.spacing.cardPadding,
  },
  loading: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
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
