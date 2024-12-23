"use client";
import Link from "next/link";
import React from "react";
import styles from "./AppBar.module.scss";
import { signIn, signOut, useSession } from "next-auth/react";
import { ModeToggle } from "@/components/ui/mode-toggle";

const AppBar = () => {
  const { data: session } = useSession();

  return (
    <div className={styles["app-bar"]}>
      <Link href={"/"} className={styles["app-bar__home"]}>
        Home
      </Link>
      <Link href={"/blogs"} className={styles["app-bar__blogs"]}>
        Blogs
      </Link>
      <div className="ml-auto flex gap-2">
        <ModeToggle />
        {session?.user ? (
          <>
            <p className="text-center my-auto">{session.user?.name}</p>
            <button onClick={() => signOut()}>Sign Out</button>
          </>
        ) : (
          <>
            <button onClick={() => signIn()}>Sign In</button>
          </>
        )}
      </div>
    </div>
  );
};

export default AppBar;
