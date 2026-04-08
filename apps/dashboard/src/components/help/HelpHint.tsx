"use client";

import { useRef } from "react";

import { useI18n } from "@/components/i18n/I18nProvider";

type Props = Readonly<{
  /** Kurztext (z. B. Tooltip-Inhalt), Key in messages/*.json */
  briefKey: string;
  /** Optional: langer Text im Dialog */
  detailKey?: string;
  className?: string;
}>;

/**
 * Kompaktes ? mit ausklappbarem Kurztext und optionalem „Mehr erfahren“-Dialog.
 */
export function HelpHint({ briefKey, detailKey, className }: Props) {
  const { t } = useI18n();
  const dialogRef = useRef<HTMLDialogElement>(null);

  function openDialog(e: React.MouseEvent) {
    e.preventDefault();
    e.stopPropagation();
    dialogRef.current?.showModal();
  }

  function closeDialog() {
    dialogRef.current?.close();
  }

  return (
    <span className={className ? `help-hint ${className}` : "help-hint"}>
      <details className="help-hint-pop">
        <summary
          className="help-hint-q"
          title={t(briefKey)}
          aria-label={t("help.ariaExpand")}
        >
          ?
        </summary>
        <div className="help-hint-brief">
          <p>{t(briefKey)}</p>
          {detailKey ? (
            <button
              type="button"
              className="help-hint-learn"
              onClick={openDialog}
            >
              {t("help.learnMore")}
            </button>
          ) : null}
        </div>
      </details>
      {detailKey ? (
        <dialog
          ref={dialogRef}
          className="help-hint-dialog"
          onCancel={closeDialog}
          aria-labelledby="help-hint-dialog-title"
        >
          <div className="help-hint-dialog-inner">
            <h2 id="help-hint-dialog-title" className="help-hint-dialog-title">
              {t("help.dialogTitle")}
            </h2>
            <div className="help-hint-dialog-body">{t(detailKey)}</div>
            <button
              type="button"
              className="public-btn primary help-hint-dialog-close"
              onClick={closeDialog}
            >
              {t("help.close")}
            </button>
          </div>
        </dialog>
      ) : null}
    </span>
  );
}
