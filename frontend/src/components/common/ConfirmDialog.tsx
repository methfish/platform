import { AlertTriangle, X } from 'lucide-react';
import { useEffect } from 'react';

interface ConfirmDialogProps {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: 'danger' | 'warning' | 'info';
  onConfirm: () => void;
  onCancel: () => void;
}

const VARIANT_STYLES = {
  danger: {
    icon: 'text-red-400 bg-red-500/15',
    button: 'bg-red-600 hover:bg-red-700 text-white',
  },
  warning: {
    icon: 'text-yellow-400 bg-yellow-500/15',
    button: 'bg-yellow-600 hover:bg-yellow-700 text-white',
  },
  info: {
    icon: 'text-blue-400 bg-blue-500/15',
    button: 'btn-primary',
  },
};

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = 'Confirm',
  cancelLabel = 'Cancel',
  variant = 'info',
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  useEffect(() => {
    if (open) {
      const handler = (e: KeyboardEvent) => {
        if (e.key === 'Escape') onCancel();
      };
      document.addEventListener('keydown', handler);
      return () => document.removeEventListener('keydown', handler);
    }
  }, [open, onCancel]);

  if (!open) return null;

  const styles = VARIANT_STYLES[variant];

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={onCancel} />
      <div className="relative bg-surface-raised border border-surface-border rounded-xl shadow-2xl max-w-md w-full mx-4 p-6">
        <button
          onClick={onCancel}
          className="absolute top-4 right-4 text-gray-500 hover:text-gray-300 transition-colors"
        >
          <X className="h-5 w-5" />
        </button>

        <div className="flex items-start gap-4">
          <div className={`p-2.5 rounded-lg shrink-0 ${styles.icon}`}>
            <AlertTriangle className="h-5 w-5" />
          </div>
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-semibold text-gray-100 mb-2">{title}</h3>
            <p className="text-sm text-gray-400 leading-relaxed">{message}</p>
          </div>
        </div>

        <div className="flex justify-end gap-3 mt-6">
          <button onClick={onCancel} className="btn-secondary text-sm">
            {cancelLabel}
          </button>
          <button onClick={onConfirm} className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${styles.button}`}>
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
