import type { Metadata } from "next";
import Script from "next/script";
import "./globals.css";
import Providers from "./providers";

export const metadata: Metadata = {
  title: "PCB Forge | PCB Ecosystem",
  description: "PCB design analysis, manufacturing planning, and quality inspection.",
};

const revealGate = `(() => {
  try {
    const params = new URLSearchParams(window.location.search);
    const requested = params.get("forgeTransition") === "1" || window.location.hash === "#forgeTransition=1";
    const firstVisit = !sessionStorage.getItem("pcb-forge-intro-v2-seen");
    if (requested || firstVisit) {
      document.documentElement.dataset.pcbForgeReveal = "active";
      sessionStorage.setItem("pcb-forge-intro-v2-seen", "1");
    }
  } catch (_) {
    if (new URLSearchParams(window.location.search).get("forgeTransition") === "1" || window.location.hash === "#forgeTransition=1") {
      document.documentElement.dataset.pcbForgeReveal = "active";
    }
  }
})();`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-base-950 font-sans antialiased">
        <Script id="pcb-forge-reveal-gate" strategy="beforeInteractive">{revealGate}</Script>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}


