import type { OrderResult } from "@/types";
import { ClipboardCheck } from "lucide-react";

export default function OrderConfirmation({ order }: { order: OrderResult }) {
  const isDemoRequest = order.payment_mode === "NOT_CHARGED";
  return (
    <div className="rounded-2xl border border-accent-500/40 bg-accent-500/5 p-6 fade-in-up shadow-glow" role="status">
      <div className="mb-4 flex items-center gap-2">
        <ClipboardCheck className="h-5 w-5 text-accent-400" />
        <h3 className="text-lg font-semibold text-white">{isDemoRequest ? "Razorpay (test) · Requested" : "Razorpay test payment confirmed"}</h3>
      </div>
      <div className="mb-4 grid sm:grid-cols-2 gap-4">
        <Field label="Request ID" value={order.order_id} mono />
        <Field label="Supplier estimate" value={order.manufacturer} />
        <Field label="Quantity" value={String(order.quantity)} />
        <Field label="Estimated total" value={`$${order.total_price.toFixed(2)}`} />
        <Field label="Status" value={order.status} />
        {order.payment_id && <Field label="Test payment ID" value={order.payment_id} mono />}
        <Field label="Payment" value={isDemoRequest ? "Test request · not charged" : "Razorpay Test Mode"} />
        <Field label="Estimated lead time" value={`${order.estimated_delivery_days} days`} />
      </div>
      <p className="rounded-lg border border-base-700 bg-base-850 p-3 text-xs leading-5 text-base-400">
        {isDemoRequest
          ? "Your request was recorded in PCB Forge test mode. No payment was processed and no factory was contacted."
          : "Razorpay verified this test payment. The supplier catalogue is illustrative; no factory received the request."}
      </p>
    </div>
  );
}

function Field({ label, value, mono }: { label: string; value: string; mono?: boolean }) {
  return <div><div className="text-xs uppercase tracking-wide text-base-600">{label}</div><div className={`mt-1 font-medium text-white ${mono ? "font-mono" : ""}`}>{value}</div></div>;
}
