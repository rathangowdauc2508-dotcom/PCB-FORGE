import type { ReactNode } from 'react';

export default function PageLayout({ children }: { children: ReactNode }) {
  return (
    <main className="page-layout">
      {children}
    </main>
  );
}
