"use client";

import { Progress } from "@/components/ui/progress";
import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";

export default function TopLoader() {
  const [progress, setProgress] = useState(0);
  const pathname = usePathname();

  useEffect(() => {
    // Reset và mô phỏng loading mỗi khi pathname thay đổi
    setProgress(20);
    const timeout1 = setTimeout(() => setProgress(60), 200);
    const timeout2 = setTimeout(() => setProgress(100), 400);
    const timeout3 = setTimeout(() => setProgress(0), 700);
    // Dọn dẹp timeout khi component unmount hoặc pathname thay đổi

    return () => {
      clearTimeout(timeout1);
      clearTimeout(timeout2);
      clearTimeout(timeout3);
    };
  }, [pathname]);

  return (
    <div className="absolute top-[60px] left-0 w-full z-50">
      {progress > 0 && (
        <Progress value={progress} className="h-1 bg-transparent [&_[role=progressbar]]:bg-[#3a6df4]!important">
          {/* Progress của shadcn/ui tự xử lý fill ở đây */}
        </Progress>
      )}
    </div>
  );
}
