import "./globals.css";
import { ReactNode } from "react";
import Providers from "@/redux/Provider";
import ClientSessionProvider from "../pages/api/auth/ClientSessionProvider";
import { Metadata } from "next";
import Header from "@/components/header/Header";
import SideNav from "@/components/sideNav/SideNav";
import { Toaster } from "@/components/ui/toaster";
import { getServerSession } from "next-auth";
import { authOptions } from "@/pages/api/auth/[...nextauth]";

export const metadata: Metadata = {
  title: "AutoML",
  description: "This is a AutoML system, created by OptivisionLab",
};

interface IProps {
  children: ReactNode;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  // session: any;
}

export default async function RootLayout({ children }: IProps) {
  const session = await getServerSession(authOptions);

  console.log(">> check login session:", session);
  return (
    <html lang="en" suppressHydrationWarning>
      <body>
        <ClientSessionProvider session={session}>
          <Providers>
            <Header />
            <div className="flex">
              <SideNav />
              <div className="w-full overflow-x-auto">
                <div className="sm:h-[calc(99vh-60px)] overflow-auto ">
                  <div className="w-full flex justify-center mx-auto overflow-auto h-[calc(100vh - 120px)] overflow-y-auto relative">
                    <div className="w-full md:max-w-6xl">{children}</div>
                    <Toaster />
                  </div>
                </div>
              </div>
            </div>
          </Providers>
        </ClientSessionProvider>
      </body>
    </html>
  );
}
