"use client";

import { useState } from "react";
import type { ManufacturingQuote, DFMResult } from "@/types";
import { ShieldCheck } from "lucide-react";

interface Props {
  quote: ManufacturingQuote;
  dfm: DFMResult;
  onApprove: (quantity: number, totalPrice: number) => void;
  disabled: boolean;
}

export default function OrderPanel({ quote, dfm, onApprove, disabled }: Props) {
  const [quantity, setQuantity] = useState(5);
  // Manufacturer prices are quoted for a standard 5-board prototype batch
  // (small-batch PCB fab pricing is roughly flat, not linear per unit), so
  // scale relative to that reference batch size rather than multiplying
  // price-per-unit directly by quantity.
  const total = Math.round(((quote.price_usd * quantity) / 5) * 100) / 100;

  return (
    <div className="rounded-2xl border border-base-700 bg-base-900/60 p-6 fade-in-up">
      <h3 className="text-lg font-semibold text-white mb-1">Prototype manufacturing request</h3><p className="mb-4 text-xs text-base-500">Supplier prices and lead times are planning estimates. A saved request does not place an order with a factory.</p>

      <div className="grid sm:grid-cols-2 gap-4 mb-4">
        <div>
          <label className="text-xs text-base-600 uppercase tracking-wide">Illustrative supplier</label>
          <div className="text-white font-medium mt-1">{quote.manufacturer_name}</div>
        </div>
        <div>
          <label className="text-xs text-base-600 uppercase tracking-wide">Estimated lead time</label>
          <div className="text-white font-medium mt-1">{quote.lead_time_days} days</div>
        </div>
        <div>
          <label className="text-xs text-base-600 uppercase tracking-wide">Quantity</label>
          <input
            type="number"
            min={1}
            max={1000}
            value={quantity}
            onChange={(e) => setQuantity(Math.min(1000, Math.max(1, Number(e.target.value) || 1)))}
            className="mt-1 w-full rounded-lg bg-base-850 border border-base-700 px-3 py-2 text-white font-mono focus:outline-none focus:border-accent-500"
          />
        </div>
        <div>
          <label className="text-xs text-base-600 uppercase tracking-wide">Total</label>
          <div className="text-2xl font-semibold text-accent-400 font-mono mt-1">${total.toFixed(2)}</div>
        </div>
      </div>

      <div className="flex items-center gap-2 text-xs text-base-600 mb-4">
        <ShieldCheck className="h-3.5 w-3.5" />
        DFM status: <span className="font-semibold text-base-300">{dfm.status}</span>
      </div>

      <button
        onClick={() => onApprove(quantity, total)}
        disabled={disabled}
        className="w-full rounded-xl bg-accent-500 hover:bg-accent-400 disabled:opacity-50 disabled:cursor-not-allowed text-base-950 font-semibold py-3 transition-colors"
      >
        {disabled ? "Submitting request..." : "Continue with request"}
      </button>
      <p className="mt-2 text-center text-xs text-base-600">Razorpay Test Mode opens when configured. Otherwise, PCB Forge saves a demo request without charging.</p>
    </div>
  );
}



