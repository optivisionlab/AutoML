import "./globals.css";
import AppBar from "@/components/appbar/AppBar";
import { ReactNode } from "react";
import Providers from "@/redux/Provider";
import ClientSessionProvider from "@/pages/api/auth/ClientSessionProvider";
import { Metadata } from "next";
import { ThemeProvider } from "@/components/ui/theme-provider";

export const metadata: Metadata = {
  title: "My Blog",
  description: "This is a blog app",
};

interface IProps {
  children: ReactNode;
  session: any;
}

export default function RootLayout({ children, session }: IProps) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ClientSessionProvider session={session}>
          <Providers>
            <ThemeProvider
              attribute="class"
              defaultTheme="system"
              enableSystem
              disableTransitionOnChange
            >
              <AppBar />
              <div>{children}</div>
            </ThemeProvider>
          </Providers>
        </ClientSessionProvider>
      </body>
    </html>
  );
}
