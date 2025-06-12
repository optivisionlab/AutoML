"use client";

import * as React from "react";
import Image from "next/image";
import { Carousel, CarouselContent, CarouselItem } from "@/components/ui/carousel";
import Autoplay from "embla-carousel-autoplay";

const images = [
  "/lab-carousel/t77503.jpg",
  "/lab-carousel/lab1.jpg",
  "/lab-carousel/background.png",
];

export default function ImageCarousel() {
  const plugin = React.useRef(
    Autoplay({ delay: parseInt(process.env.NEXT_PUBLIC_TIMEOUT_CAROUSEL || "10000", 10), stopOnInteraction: false })
  );

  return (
    <div className="relative w-full h-[60vh] sm:h-[70vh] md:h-[90vh]">
      <Carousel
        plugins={[plugin.current]}
        className="w-full h-full"
        opts={{
          align: "start",
          loop: true, // Lặp vô hạn
        }}
      >
        <CarouselContent>
          {images.map((src, index) => (
            <CarouselItem key={index}>
              <div className="relative w-full h-[60vh] sm:h-[70vh] md:h-[90vh]">
                <Image
                  src={src}
                  alt={`Slide ${index + 1}`}
                  layout="fill"
                  objectFit="cover"
                  className="z-0"
                />
              </div>
            </CarouselItem>
          ))}
        </CarouselContent>
      </Carousel>
      <div className="absolute inset-0 bg-black/40 flex items-center justify-center px-4 text-center z-10">
        <div className="text-white font-semibold whitespace-nowrap text-[4.5vw] sm:text-[3vw] md:text-[2.5vw] lg:text-[2.5vw]">
          CHÚNG TÔI CUNG CẤP GIẢI PHÁP TỐT NHẤT CHO <br /> TỰ ĐỘNG HÓA HỌC MÁY
        </div>
      </div>
    </div>
  );
}