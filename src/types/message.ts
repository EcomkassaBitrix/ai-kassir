export interface Message {
  id: string;
  type: 'user' | 'agent' | 'preview';
  content: string;
  timestamp: Date;
  receiptData?: any;
  receiptUuid?: string;
  receiptPermalink?: string;
  previewData?: any;
  hasError?: boolean;
  errorMessage?: string;
  paymentLink?: string;
  qrCode?: string;
}