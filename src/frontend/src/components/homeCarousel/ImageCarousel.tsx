"use client";

import * as React from "react";
import Image from "next/image";
import { Carousel, CarouselContent, CarouselItem } from "@/components/ui/carousel";
import Autoplay from "embla-carousel-autoplay";
import { FaChevronLeft, FaChevronRight } from "react-icons/fa";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ArrowRight } from "lucide-react";
import { useSession } from "next-auth/react";

const images = [
  "/lab-carousel/t77503.jpg",
  "/lab-carousel/lab1.jpg",
  "/lab-carousel/background.png",
];

export default function ImageCarousel() {
  const { data: session } = useSession();
  const plugin = React.useRef(
    Autoplay({ delay: parseInt(process.env.NEXT_PUBLIC_TIMEOUT_CAROUSEL || "10000", 10), stopOnInteraction: false })
  );

  const [api, setApi] = React.useState<any>(null);

  return (
    <div className="relative w-full h-[60vh] sm:h-[70vh] md:h-[90vh]">
      <Carousel
        plugins={[plugin.current]}
        className="w-full h-full"
        opts={{ align: "start", loop: true }}
        setApi={setApi}
      >
        <CarouselContent>
          {images.map((src, index) => (
            <CarouselItem key={index}>
              <div className="relative w-full h-[60vh] sm:h-[70vh] md:h-[90vh]">
                <Image
                  src={src}
                  alt={`Slide ${index + 1}`}
                  fill
                  style={{ objectFit: "cover" }}
                  className="z-0"
                />
              </div>
            </CarouselItem>
          ))}
        </CarouselContent>
      </Carousel>

      {/* Custom nút trái */}
      <button
        onClick={() => api?.scrollPrev()}
        className="absolute left-4 top-1/2 -translate-y-1/2 z-20 bg-black/50 hover:bg-black/70 text-white p-3 rounded-full"
      >
        <FaChevronLeft size={20} />
      </button>

      {/* Custom nút phải */}
      <button
        onClick={() => api?.scrollNext()}
        className="absolute right-4 top-1/2 -translate-y-1/2 z-20 bg-black/50 hover:bg-black/70 text-white p-3 rounded-full"
      >
        <FaChevronRight size={20} />
      </button>

      {/* Overlay chữ */}
      <div className="absolute inset-0 bg-black/40 flex items-center justify-center px-4 text-center z-10">
        <div className="text-white font-semibold space-y-4 flex flex-col items-center">
          <div className="text-[7vw] sm:text-[5vw] md:text-[3.5vw] lg:text-[2.8vw] leading-tight">
            MỞ TÀI KHOẢN ĐỂ TRẢI NGHIỆM DÙNG THỬ MIỄN PHÍ
          </div>
          <div className="text-[5vw] sm:text-[3.5vw] md:text-[2.5vw] lg:text-[2vw] leading-tight font-normal">
            HAUTOML - MÃ NGUỒN MỞ TUYỆT VỜI CHO QUY TRÌNH TỰ ĐỘNG HÓA HỌC MÁY
          </div>

          {!session?.user?.id && (
            <Link href="/register">
              <Button
                variant="ghost"
                className="group mt-4 px-6 py-6 text-white border border-white bg-transparent hover:bg-transparent hover:text-white flex items-center text-[4vw] sm:text-[2vw] md:text-[1.5vw] lg:text-[1.2vw] group"
              >
                DÙNG THỬ MIỄN PHÍ
                <ArrowRight className="ml-2 w-5 h-5 transition-transform duration-300 group-hover:translate-x-1" />
              </Button>
            </Link>
          )}
        </div>
      </div>
    </div>
  );
}
