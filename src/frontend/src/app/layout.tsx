import "./globals.css";
import { ReactNode } from "react";
import Providers from "@/redux/Provider";
import ClientSessionProvider from "../pages/api/auth/ClientSessionProvider";
import { Metadata } from "next";
import Header from "@/components/header/Header";
import SideNav from "@/components/sideNav/SideNav";
import { Toaster } from "@/components/ui/toaster";
import { ThemeProvider } from "@/components/theme-provider";

export const metadata: Metadata = {
  title: "AutoML",
  description: "This is an AutoML system, created by OptivisionLab",
};

interface IProps {
  children: ReactNode;
}

export default function RootLayout({ children }: IProps) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ThemeProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
          <ClientSessionProvider>
            <Providers>
              <Header />
              <div className="flex">
                <SideNav />
                <div className="w-full overflow-x-auto">
                  <div className="sm:h-[calc(99vh-60px)] overflow-auto">
                    <div className="w-full flex justify-center mx-auto overflow-auto h-[calc(100vh-120px)] overflow-y-auto relative">
                      <div className="w-full">{children}</div>
                      <Toaster />
                    </div>
                  </div>
                </div>
              </div>
            </Providers>
          </ClientSessionProvider>
        </ThemeProvider>
      </body>
    </html>
  );
}
