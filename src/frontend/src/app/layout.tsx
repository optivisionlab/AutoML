import "./globals.css";
import { ReactNode } from "react";
import Providers from "@/redux/Provider";
import ClientSessionProvider from "../pages/api/auth/ClientSessionProvider";
import { Metadata } from "next";
import Header from "@/components/header/Header";
import SideNav from "@/components/sideNav/SideNav";
import { Toaster } from "@/components/ui/toaster";
import { ThemeProvider } from "@/components/theme-provider";
import TopLoader from "@/components/top-loader";

export const metadata: Metadata = {
  title: "HAutoML",
  description: "HAutoML Low code & No code - Mã nguồn mở tuyệt vời cho quy trình tự động hóa học máy",
  icons: {
    icon: "/favicon_io/favicon.ico",
    apple: "/favicon_io/apple-touch-icon.png",
    shortcut: "/favicon_io/favicon-32x32.png",
  },
  openGraph: {
    title: "HAutoML",
    description: "HAutoML Low code & No code - Mã nguồn mở tuyệt vời cho quy trình tự động hóa học máy",
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
    description: "HAutoML Low code & No code - Mã nguồn mở tuyệt vời cho quy trình tự động hóa học máy",
    images: ["https://optivisionlab.fit-haui.edu.vn/image.png"],
  },
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
              <TopLoader/>
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
