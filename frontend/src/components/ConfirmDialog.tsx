import { useCallback, useState } from "react";

import { AlertTriangle, X } from "lucide-react";

type Confirmation = {
  title: string;
  description: string;
  confirmLabel: string;
  resolve: (confirmed: boolean) => void;
};

export function useConfirmDialog() {
  const [confirmation, setConfirmation] = useState<Confirmation | null>(null);

  const requestConfirmation = useCallback((options: Omit<Confirmation, "resolve">) => (
    new Promise<boolean>((resolve) => setConfirmation({ ...options, resolve }))
  ), []);

  const close = useCallback((confirmed: boolean) => {
    setConfirmation((current) => {
      current?.resolve(confirmed);
      return null;
    });
  }, []);

  const confirmDialog = confirmation ? (
    <div className="modal-backdrop" role="presentation" onMouseDown={() => close(false)}>
      <section aria-describedby="confirm-dialog-description" aria-modal="true" aria-labelledby="confirm-dialog-title" className="modal-dialog confirm-dialog" role="alertdialog" onMouseDown={(event) => event.stopPropagation()}>
        <div className="modal-dialog-header">
          <div className="confirm-dialog-title"><span><AlertTriangle size={18} /></span><div><h2 id="confirm-dialog-title">{confirmation.title}</h2><p id="confirm-dialog-description">{confirmation.description}</p></div></div>
          <button className="icon-btn" onClick={() => close(false)} title="关闭" type="button"><X size={16} /></button>
        </div>
        <div className="modal-dialog-footer">
          <button className="btn btn-secondary" onClick={() => close(false)} type="button">取消</button>
          <button className="btn btn-danger" onClick={() => close(true)} type="button">{confirmation.confirmLabel}</button>
        </div>
      </section>
    </div>
  ) : null;

  return { requestConfirmation, confirmDialog };
}
