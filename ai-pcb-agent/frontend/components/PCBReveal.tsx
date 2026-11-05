"use client";

import { useEffect, useState } from "react";

type Phase = "entering" | "leaving";

export default function PCBReveal() {
  const [visible, setVisible] = useState(true);
  const [phase, setPhase] = useState<Phase>("entering");

  useEffect(() => {
    const root = document.documentElement;
    if (root.dataset.pcbForgeReveal !== "active") return;

    const url = new URL(window.location.href);
    if (url.searchParams.has("forgeTransition") || url.hash === "#forgeTransition=1") {
      url.searchParams.delete("forgeTransition");
      url.hash = "";
      window.history.replaceState({}, "", url.pathname + url.search);
    }

    let closeTimer: number;
    const finish = () => {
      setPhase("leaving");
      closeTimer = window.setTimeout(() => {
        root.removeAttribute("data-pcb-forge-reveal");
        setVisible(false);
      }, 620);
    };
    const timer = window.setTimeout(finish, 3400);
    return () => {
      window.clearTimeout(timer);
      window.clearTimeout(closeTimer);
    };
  }, []);

  if (!visible) return null;

  return (
    <div className={`forge-reveal${phase === "leaving" ? " forge-reveal--leaving" : ""}`} role="dialog" aria-modal="true" aria-label="Entering PCB Forge">
      <div className="forge-reveal-grid" aria-hidden="true" />
      <div className="forge-reveal-content">
        <div className="forge-reveal-scene" aria-hidden="true">
          <div className="forge-orbit forge-orbit--outer" />
          <div className="forge-orbit forge-orbit--inner" />
          <div className="forge-board-shadow" />
          <svg className="forge-reveal-board" viewBox="0 0 420 280" role="img" aria-label="A circuit board powering on">
            <defs>
              <linearGradient id="forge-board-face" x1="0" y1="0" x2="1" y2="1">
                <stop stopColor="#254a38" /><stop offset=".55" stopColor="#153326" /><stop offset="1" stopColor="#0c1d15" />
              </linearGradient>
              <linearGradient id="forge-board-edge" x1="0" y1="0" x2="0" y2="1">
                <stop stopColor="#d99656" /><stop offset="1" stopColor="#754322" />
              </linearGradient>
              <radialGradient id="forge-board-glow"><stop stopColor="#ffb45f" stopOpacity=".35" /><stop offset="1" stopColor="#ffb45f" stopOpacity="0" /></radialGradient>
            </defs>
            <path d="M50 23h289l34 34v172l-34 31H51l-28-29V53z" fill="url(#forge-board-edge)" opacity=".9" transform="translate(0 9)" />
            <path d="M50 18h289l34 34v172l-34 31H51l-28-29V48z" fill="url(#forge-board-face)" stroke="#e4a15f" strokeWidth="2" />
            <path d="M60 28h273l29 29v161l-29 27H61l-27-27V52z" fill="none" stroke="#719078" strokeOpacity=".32" />
            <ellipse cx="208" cy="147" rx="168" ry="119" fill="url(#forge-board-glow)" />
            <g className="forge-copper" fill="none" stroke="#db9555" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
              <path d="M66 65h70v27h38m-108 12h45v31h38m-76 47h70v-26h43" />
              <path d="M350 69h-63v34h-37m101 21h-58v27h-29m72 44h-72v-27h-40" />
              <path d="M187 41v35h23m-1 123v39m-69-96h34m45 15h34" />
              <path d="M103 157v28m205-100v25m-112 77h-25m85-67h-24" />
            </g>
            <g fill="#e7ba73" stroke="#ffe0a0" strokeWidth="1">
              <circle cx="49" cy="48" r="7" /><circle cx="338" cy="48" r="7" /><circle cx="49" cy="224" r="7" /><circle cx="338" cy="224" r="7" />
              <circle cx="135" cy="92" r="4" /><circle cx="174" cy="104" r="4" /><circle cx="251" cy="103" r="4" /><circle cx="288" cy="127" r="4" />
              <circle cx="139" cy="181" r="4" /><circle cx="246" cy="176" r="4" /><circle cx="308" cy="184" r="4" />
            </g>
            <g fill="#d9a75e">
              {Array.from({ length: 10 }, (_, i) => <rect key={`pin-${i}`} x={84 + i * 27} y="34" width="9" height="5" rx="2" />)}
              {Array.from({ length: 10 }, (_, i) => <rect key={`pinb-${i}`} x={84 + i * 27} y="226" width="9" height="5" rx="2" />)}
            </g>
            <rect x="166" y="102" width="86" height="75" rx="9" fill="#101a15" stroke="#e9bc77" strokeWidth="2" />
            <rect x="178" y="114" width="62" height="51" rx="5" fill="#1c2b22" stroke="#647e68" />
            <path d="M195 127h28v24h-28zm14 0v24m-14-12h28" fill="none" stroke="#e8a05c" strokeWidth="2" />
            <circle className="forge-board-led" cx="293" cy="83" r="5" fill="#a3ec9a" />
          </svg>
          <div className="forge-scanline" />
        </div>
        <div className="forge-reveal-copy">
          <div className="forge-reveal-kicker"><span className="forge-status-led" /> PCB ENGINEERING WORKSPACE</div>
          <div className="forge-reveal-brand">PCB Forge</div>
          <div className="forge-reveal-caption">DESIGN <i /> FABRICATION <i /> QUALITY</div>
          <button className="forge-reveal-enter" onClick={() => { setPhase("leaving"); window.setTimeout(() => { document.documentElement.removeAttribute("data-pcb-forge-reveal"); setVisible(false); }, 620); }}>Enter workspace <span aria-hidden="true">↗</span></button>
          <div className="forge-loading-track" aria-hidden="true"><span /></div>
        </div>
      </div>
    </div>
  );
}



