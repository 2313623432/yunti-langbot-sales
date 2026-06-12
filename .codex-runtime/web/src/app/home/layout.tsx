import HomeSidebar from '@/app/home/components/home-sidebar/HomeSidebar';
import SurveyWidget from '@/app/home/components/survey/SurveyWidget';
import React, { useCallback, useMemo, useEffect, Suspense } from 'react';
import { SidebarChildVO } from '@/app/home/components/home-sidebar/HomeSidebarChild';
import { SidebarDataProvider } from '@/app/home/components/home-sidebar/SidebarDataContext';
import {
  userInfo,
  initializeUserInfo,
  initializeSystemInfo,
} from '@/app/infra/http';
import { useLocation } from 'react-router-dom';
import { SidebarInset, SidebarProvider } from '@/components/ui/sidebar';
import {
  PluginInstallTaskProvider,
  PluginInstallProgressDialog,
} from '@/app/home/plugins/components/plugin-install-task';

export default function HomeLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  // Initialize user info if not already initialized
  useEffect(() => {
    if (!userInfo) {
      initializeUserInfo();
    }
  }, []);

  // Auto-redirect to wizard on first visit (wizard not yet completed on this instance)
  useEffect(() => {
    const checkWizard = async () => {
      try {
        // Always re-fetch to ensure we have the latest wizard_status from backend
        await initializeSystemInfo();
      } catch {
        // If fetching system info fails, don't redirect
      }
    };
    checkWizard();
  }, []);

  return (
    <SidebarDataProvider>
      <PluginInstallTaskProvider>
        <HomeLayoutInner>{children}</HomeLayoutInner>
        <PluginInstallProgressDialog />
      </PluginInstallTaskProvider>
    </SidebarDataProvider>
  );
}

function HomeLayoutInner({ children }: { children: React.ReactNode }) {
  const location = useLocation();
  const pathname = location.pathname;
  const onSelectedChangeAction = useCallback(
    (_child: SidebarChildVO) => {},
    [],
  );

  // Memoize the main content area to prevent re-renders when sidebar state changes
  const mainContent = useMemo(() => children, [children]);

  const isSalesRoute =
    pathname === '/home/sales' ||
    pathname.startsWith('/home/sales/') ||
    pathname === '/home/sales-chat' ||
    pathname.startsWith('/home/sales-chat/') ||
    pathname === '/home/products' ||
    pathname.startsWith('/home/products/');
  const isSalesBuilderRoute =
    pathname === '/home/ai-agents' ||
    pathname.startsWith('/home/ai-agents/') ||
    pathname === '/home/workflows' ||
    pathname.startsWith('/home/workflows/');
  const contentClassName =
    isSalesRoute || isSalesBuilderRoute
      ? 'flex-1 min-h-0 min-w-0 overflow-hidden'
      : 'flex-1 min-h-0 min-w-0 overflow-hidden p-4';

  return (
    <SidebarProvider
      style={{ '--sidebar-width': '15rem' } as React.CSSProperties}
    >
      <Suspense fallback={<div />}>
        <HomeSidebar onSelectedChangeAction={onSelectedChangeAction} />
      </Suspense>

      <SidebarInset>
        <div className={contentClassName}>{mainContent}</div>

        <SurveyWidget />
      </SidebarInset>
    </SidebarProvider>
  );
}
