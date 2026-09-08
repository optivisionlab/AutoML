import "./globals.css";
import { ReactNode } from "react";
import Providers from "@/core/store/Provider";
import ClientSessionProvider from "../pages/api/auth/ClientSessionProvider";
import { Metadata } from "next";
import { ThemeProvider } from "@/core/theme/ThemeProvider";
import AppShell from "@/shared/components/layout/AppShell";
import { getLocale } from "next-intl/server";
import { LanguageProvider } from "@/core/i18n/LanguageProvider";
import { AppLocale, defaultLocale, isAppLocale } from "@/core/i18n/config";

export const metadata: Metadata = {
  title: "HAutoML",
  description:
    "HAutoML Low code & No code - Mã nguồn mở tuyệt vời cho quy trình tự động hóa học máy",
  icons: {
    icon: "/favicon_io/favicon.ico",
    apple: "/favicon_io/apple-touch-icon.png",
    shortcut: "/favicon_io/favicon-32x32.png",
  },
  openGraph: {
    title: "HAutoML",
    description:
      "HAutoML Low code & No code - Mã nguồn mở tuyệt vời cho quy trình tự động hóa học máy",
    url: "https://optivisionlab.fit-haui.edu.vn",
    siteName: "HAutoML",
    images: [
      {
        url: "https://optivisionlab.fit-haui.edu.vn/image.png",
        width: 1200,
        height: 630,
        alt: "HAutoML Preview Image",
      },
    ],
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "HAutoML",
    description:
      "HAutoML Low code & No code - Mã nguồn mở tuyệt vời cho quy trình tự động hóa học máy",
    images: ["https://optivisionlab.fit-haui.edu.vn/image.png"],
  },
};

interface IProps {
  children: ReactNode;
}

export default async function RootLayout({ children }: IProps) {
  const requestLocale = await getLocale();
  const locale: AppLocale = isAppLocale(requestLocale)
    ? requestLocale
    : defaultLocale;

  return (
    <html lang={locale} suppressHydrationWarning>
      <body>
        <LanguageProvider initialLocale={locale}>
          <ThemeProvider
            attribute="class"
            defaultTheme="system"
            enableSystem
            disableTransitionOnChange
          >
            <ClientSessionProvider>
              <Providers>
                <AppShell>{children}</AppShell>
              </Providers>
            </ClientSessionProvider>
          </ThemeProvider>
        </LanguageProvider>
      </body>
    </html>
  );
}
