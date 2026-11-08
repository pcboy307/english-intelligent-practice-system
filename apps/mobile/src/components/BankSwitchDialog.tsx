import * as DocumentPicker from "expo-document-picker";
import { useEffect, useState } from "react";
import {
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  View,
} from "react-native";

import {
  activateBank,
  deleteBank,
  exportBank,
  getSwitchableBanks,
  importBank,
  previewDeleteBank,
  type BankDeletePreview,
  type BankImportPackage,
  type BankImportResult,
  type SwitchableBank,
  type SwitchableBanks,
} from "../api/client";
import { tokens } from "../theme/tokens";

type BankSwitchDialogProps = {
  visible: boolean;
  onCancel: () => void;
  onSwitched: () => Promise<void> | void;
};

type DeleteDraft = {
  bank: SwitchableBank;
  preview: BankDeletePreview;
};

const STATUS_LABELS: Record<string, string> = {
  active: "当前启用",
  ready: "就绪",
  archived: "历史归档",
};

function reasonText(reason: unknown): string {
  return reason instanceof Error ? reason.message : String(reason);
}

function exportFileName(bank: SwitchableBank): string {
  const safeName = bank.name
    .replace(/[\\/:*?"<>|\s]+/g, "-")
    .replace(/^-+|-+$/g, "");
  const date = new Date().toISOString().slice(0, 10);
  return `${safeName || "question-bank"}-${date}.json`;
}

export function BankSwitchDialog({
  visible,
  onCancel,
  onSwitched,
}: BankSwitchDialogProps) {
  const [data, setData] = useState<SwitchableBanks | null>(null);
  const [selected, setSelected] = useState<SwitchableBank | null>(null);
  const [importResult, setImportResult] = useState<BankImportResult | null>(null);
  const [deleteDraft, setDeleteDraft] = useState<DeleteDraft | null>(null);
  const [deleteConfirmReady, setDeleteConfirmReady] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busy, setBusy] = useState(false);
  const [busyLabel, setBusyLabel] = useState("");

  async function loadBanks() {
    const next = await getSwitchableBanks();
    setData(next);
    return next;
  }

  useEffect(() => {
    if (!visible) {
      setData(null);
      setSelected(null);
      setImportResult(null);
      setDeleteDraft(null);
      setDeleteConfirmReady(false);
      setError("");
      setNotice("");
      setBusy(false);
      setBusyLabel("");
      return;
    }
    setBusy(true);
    setBusyLabel("正在读取题库");
    loadBanks()
      .catch((reason) => setError(reasonText(reason)))
      .finally(() => {
        setBusy(false);
        setBusyLabel("");
      });
  }, [visible]);

  useEffect(() => {
    if (!deleteDraft) {
      setDeleteConfirmReady(false);
      return;
    }
    const delay = setTimeout(() => setDeleteConfirmReady(true), 1500);
    return () => clearTimeout(delay);
  }, [deleteDraft]);

  const current = data?.banks.find((bank) => bank.is_current) || null;

  function resetTransientViews() {
    setSelected(null);
    setImportResult(null);
    setDeleteDraft(null);
    setDeleteConfirmReady(false);
    setError("");
  }

  async function executeSwitch() {
    if (!selected) return;
    setBusy(true);
    setBusyLabel("正在切换题库");
    setError("");
    try {
      await activateBank(selected.bank_id);
      await onSwitched();
      onCancel();
    } catch (reason) {
      setError(reasonText(reason));
    } finally {
      setBusy(false);
      setBusyLabel("");
    }
  }

  async function chooseImportFile() {
    setError("");
    setNotice("");
    try {
      const fileResult = await DocumentPicker.getDocumentAsync({
        type: "application/json",
        copyToCacheDirectory: true,
        multiple: false,
      });
      if (fileResult.canceled) return;
      const asset = fileResult.assets[0];
      if (asset.size && asset.size > 15 * 1024 * 1024) {
        throw new Error("导入文件不能超过 15 MB");
      }
      const raw = asset.file
        ? await asset.file.text()
        : await fetch(asset.uri).then((response) => response.text());
      const parsed: unknown = JSON.parse(raw);
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        throw new Error("导入文件的顶层必须是 JSON 对象");
      }
      const packageDetail = parsed as BankImportPackage;
      const bankName =
        typeof packageDetail.name === "string"
          ? packageDetail.name.trim()
          : "";
      if (!bankName) {
        throw new Error("题库名称不能为空");
      }
      if (
        data?.banks.some(
          (bank) =>
            bank.name.trim().toLocaleLowerCase() ===
            bankName.toLocaleLowerCase(),
        )
      ) {
        throw new Error("题库名称已存在，请换一个名称");
      }
      setBusy(true);
      setBusyLabel(`正在导入「${bankName}」`);
      const importResult = await importBank(packageDetail, false);
      await onSwitched();
      await loadBanks();
      setImportResult(importResult);
    } catch (reason) {
      setError(reasonText(reason));
    } finally {
      setBusy(false);
      setBusyLabel("");
    }
  }

  async function executeExport(bank: SwitchableBank) {
    setBusy(true);
    setBusyLabel(`正在导出「${bank.name}」`);
    setError("");
    setNotice("");
    try {
      const packageDetail = await exportBank(bank.bank_id);
      if (typeof document === "undefined") {
        throw new Error("当前环境不支持下载 JSON 文件");
      }
      const blob = new Blob(
        [`${JSON.stringify(packageDetail, null, 2)}\n`],
        { type: "application/json;charset=utf-8" },
      );
      const downloadUrl = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = downloadUrl;
      anchor.download = exportFileName(bank);
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      URL.revokeObjectURL(downloadUrl);
      setNotice(
        `已导出「${bank.name}」：${packageDetail.passages.length} 篇 / ${packageDetail.target_size} 题。`,
      );
    } catch (reason) {
      setError(reasonText(reason));
    } finally {
      setBusy(false);
      setBusyLabel("");
    }
  }

  async function prepareDelete(bank: SwitchableBank) {
    if (bank.is_current) return;
    setError("");
    setNotice("");
    setBusy(true);
    setBusyLabel("正在统计将删除的数据");
    try {
      const preview = await previewDeleteBank(bank.bank_id);
      setSelected(null);
      setImportResult(null);
      setDeleteDraft({ bank, preview });
    } catch (reason) {
      setError(reasonText(reason));
    } finally {
      setBusy(false);
      setBusyLabel("");
    }
  }

  async function executeDelete() {
    if (!deleteDraft) return;
    setBusy(true);
    setBusyLabel("正在永久删除题库");
    setError("");
    try {
      await deleteBank(deleteDraft.bank.bank_id);
      await loadBanks();
      await onSwitched();
      setNotice(`已永久删除「${deleteDraft.bank.name}」及其全部历史数据。`);
      setDeleteDraft(null);
      setDeleteConfirmReady(false);
    } catch (reason) {
      setError(reasonText(reason));
    } finally {
      setBusy(false);
      setBusyLabel("");
    }
  }

  function renderListView() {
    return (
      <>
        <View style={styles.headerRow}>
          <View style={styles.headerCopy}>
            <Text style={styles.title}>切换题库</Text>
            <Text style={styles.intro}>
              选择要启用的题库；当前题库不可重复选择，也不可删除。
            </Text>
          </View>
          <View style={styles.headerActions}>
            <Pressable
              accessibilityRole="button"
              disabled={busy}
              onPress={chooseImportFile}
              style={[styles.toolbarButton, busy && styles.disabledOutline]}
              testID="bank-import-open"
            >
              <Text style={styles.toolbarButtonText}>导入题库</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              disabled={busy}
              onPress={onCancel}
              style={[styles.toolbarButton, busy && styles.disabledOutline]}
              testID="bank-switch-cancel"
            >
              <Text style={styles.toolbarButtonText}>关闭</Text>
            </Pressable>
          </View>
        </View>

        <ScrollView style={styles.list}>
          {data?.banks.map((bank) => (
            <View key={bank.bank_id} style={styles.bankRow}>
              <Pressable
                accessibilityRole="button"
                disabled={bank.is_current || busy}
                onPress={() => {
                  setError("");
                  setNotice("");
                  setDeleteDraft(null);
                  setImportResult(null);
                  setSelected(bank);
                }}
                style={styles.bankMain}
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
                <Text
                  style={[
                    styles.currentMark,
                    bank.is_current && styles.currentMarkActive,
                  ]}
                >
                  {bank.is_current ? "✓ 当前" : "选择"}
                </Text>
              </Pressable>
              <View style={styles.rowActions}>
                <Pressable
                  accessibilityRole="button"
                  disabled={busy}
                  onPress={() => executeExport(bank)}
                  style={[styles.exportRowButton, busy && styles.disabledOutline]}
                  testID={`bank-export-${bank.bank_id}`}
                >
                  <Text style={styles.exportRowText}>导出</Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  disabled={bank.is_current || busy}
                  onPress={() => prepareDelete(bank)}
                  style={[
                    styles.deleteRowButton,
                    bank.is_current && styles.deleteRowButtonDisabled,
                  ]}
                  testID={`bank-delete-${bank.bank_id}`}
                >
                  <Text
                    style={[
                      styles.deleteRowText,
                      bank.is_current && styles.deleteRowTextDisabled,
                    ]}
                  >
                    {bank.is_current ? "当前库不可删除" : "删除"}
                  </Text>
                </Pressable>
              </View>
            </View>
          ))}
        </ScrollView>

        {notice ? (
          <Text style={styles.notice} testID="bank-notice">
            {notice}
          </Text>
        ) : null}
        {error ? (
          <Text style={styles.error} testID="bank-error">
            {error}
          </Text>
        ) : null}
        {busy && busyLabel ? (
          <Text style={styles.loading}>{busyLabel}…</Text>
        ) : null}
      </>
    );
  }

  function renderSwitchView(bank: SwitchableBank) {
    return (
      <>
        <Text style={styles.title}>确认切换题库</Text>
        <Text style={styles.confirmText}>
          将从 {current?.name}（{current?.question_count} 题）切换到{" "}
          {bank.name}（{bank.question_count} 题）。
        </Text>
        <Text style={styles.confirmText}>
          覆盖统计的分母将变为 {bank.question_count} 题；已做过的相同题目仍计入做过。
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
            当前有 {data.in_progress_count} 个未完成的练习，切换后仍可用原题库继续交卷，
            新开始的练习将使用新题库。
          </Text>
        ) : null}
        {error ? <Text style={styles.error}>{error}</Text> : null}
        <View style={styles.actions}>
          <Pressable
            accessibilityRole="button"
            disabled={busy}
            onPress={resetTransientViews}
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
              {busy ? busyLabel : "确认切换"}
            </Text>
          </Pressable>
        </View>
      </>
    );
  }

  function renderImportResult(result: BankImportResult) {
    const audit = result.semantic_audit;
    return (
      <>
        <Text style={styles.title}>题库已导入并启用</Text>
        <Text style={styles.importName}>{result.name}</Text>
        <Text style={styles.confirmText}>
          {result.summary.passages} 篇 · {result.summary.questions} 题
        </Text>
        <Text style={styles.detailText}>
          {audit
            ? `独立审题 ${audit.audited_passages ?? 0} 篇`
            : "已按原始内容直接落盘"}
        </Text>
        <View style={styles.actions}>
          <Pressable
            accessibilityRole="button"
            onPress={onCancel}
            style={styles.primaryButton}
            testID="bank-import-done"
          >
            <Text style={styles.primaryText}>完成</Text>
          </Pressable>
        </View>
      </>
    );
  }

  function renderDeleteView(draft: DeleteDraft) {
    const preview = draft.preview;
    const blocked = !preview.can_delete;
    return (
      <>
        <Text style={styles.title}>永久删除题库</Text>
        <Text style={styles.importName}>{preview.name}</Text>
        <Text style={styles.confirmText}>
          将永久删除 {preview.passages} 篇、{preview.questions} 题，以及
          {" "}{preview.sessions} 次会话、{preview.reports} 份报告、
          {" "}{preview.attempts} 条作答记录、{preview.mistakes} 道错题。
        </Text>
        <Text style={styles.detailText}>
          作用域：该题库的全部题目、历史报告、作答记录和错题关联。
        </Text>
        <Text style={styles.warning}>此操作不可恢复。</Text>
        {blocked ? (
          <Text style={styles.error}>
            暂不能删除：{preview.blocking_reason || "题库正在使用"}
          </Text>
        ) : null}
        {error ? (
          <Text style={styles.error} testID="bank-delete-error">
            {error}
          </Text>
        ) : null}
        <View style={styles.actions}>
          <Pressable
            accessibilityRole="button"
            disabled={busy}
            onPress={() => {
              setDeleteDraft(null);
              setError("");
            }}
            style={styles.secondaryButton}
            testID="bank-delete-cancel"
          >
            <Text style={styles.secondaryText}>取消</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            disabled={busy || blocked || !deleteConfirmReady}
            onPress={executeDelete}
            style={[
              styles.dangerButton,
              (busy || blocked || !deleteConfirmReady) && styles.disabled,
            ]}
            testID="bank-delete-confirm"
          >
            <Text style={styles.dangerText}>
              {busy
                ? busyLabel
                : blocked
                  ? "当前不可删除"
                  : deleteConfirmReady
                    ? "确认，此操作不可恢复"
                    : "请稍候…"}
            </Text>
          </Pressable>
        </View>
      </>
    );
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
          <ScrollView contentContainerStyle={styles.content}>
            {importResult
              ? renderImportResult(importResult)
              : deleteDraft
                ? renderDeleteView(deleteDraft)
                : selected
                  ? renderSwitchView(selected)
                  : renderListView()}
          </ScrollView>
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
    maxWidth: 620,
    maxHeight: "86%",
    borderWidth: tokens.border.width,
    borderColor: tokens.color.secondaryBorder,
    borderRadius: tokens.radius.large,
    backgroundColor: tokens.color.pageBackground,
  },
  content: {
    padding: tokens.spacing.cardPadding,
  },
  headerRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    justifyContent: "space-between",
    alignItems: "flex-start",
    gap: tokens.spacing.cardPadding,
  },
  headerCopy: {
    flex: 1,
  },
  headerActions: {
    flexDirection: "row",
    gap: tokens.web_desktop.optionGap,
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
    lineHeight: tokens.font.sizes.auxiliary * tokens.font.lineHeight.ui,
    marginTop: tokens.spacing.listGap,
  },
  toolbarButton: {
    minHeight: tokens.control.touchTargetMin,
    borderWidth: tokens.border.width,
    borderColor: tokens.color.secondaryBorder,
    borderRadius: tokens.radius.medium,
    justifyContent: "center",
    alignItems: "center",
    paddingHorizontal: tokens.spacing.cardPadding,
  },
  toolbarButtonText: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    fontWeight: "600",
  },
  disabledOutline: {
    borderColor: tokens.color.disabled,
  },
  list: {
    marginTop: tokens.spacing.cardPadding,
    maxHeight: 430,
  },
  bankRow: {
    minHeight: tokens.control.touchTargetMin,
    flexDirection: "row",
    alignItems: "center",
    borderTopWidth: tokens.border.width,
    borderTopColor: tokens.color.divider,
    paddingVertical: tokens.spacing.listGap,
  },
  bankMain: {
    minHeight: tokens.control.touchTargetMin,
    flex: 1,
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    gap: tokens.spacing.listGap,
  },
  bankText: {
    flex: 1,
  },
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
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    paddingHorizontal: tokens.spacing.listGap,
  },
  currentMarkActive: {
    color: tokens.color.accent,
  },
  rowActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: tokens.web_desktop.optionGap,
  },
  exportRowButton: {
    minHeight: tokens.control.touchTargetMin,
    borderWidth: tokens.border.width,
    borderColor: tokens.color.secondaryBorder,
    borderRadius: tokens.radius.medium,
    justifyContent: "center",
    paddingHorizontal: tokens.spacing.listGap,
  },
  exportRowText: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
  deleteRowButton: {
    minHeight: tokens.control.touchTargetMin,
    justifyContent: "center",
    paddingHorizontal: tokens.spacing.listGap,
  },
  deleteRowButtonDisabled: {
    maxWidth: 116,
  },
  deleteRowText: {
    color: tokens.color.incorrect,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
  },
  deleteRowTextDisabled: {
    color: tokens.color.disabled,
  },
  importName: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.subheading,
    fontWeight: "600",
    marginTop: tokens.spacing.cardPadding,
  },
  confirmText: {
    color: tokens.color.primaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.body,
    lineHeight: tokens.font.sizes.body * tokens.font.lineHeight.ui,
    marginTop: tokens.spacing.listGap,
  },
  detailText: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
    lineHeight: tokens.font.sizes.auxiliary * tokens.font.lineHeight.ui,
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
  loading: {
    color: tokens.color.secondaryText,
    fontFamily: tokens.font.uiFamily.web,
    fontSize: tokens.font.sizes.auxiliary,
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
    lineHeight: tokens.font.sizes.auxiliary * tokens.font.lineHeight.ui,
    marginTop: tokens.spacing.listGap,
  },
});
