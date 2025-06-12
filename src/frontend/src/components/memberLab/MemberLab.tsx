"use client"

import React from "react"
import Image from "next/image"
import { Card, CardContent } from "@/components/ui/card"
import {
  Carousel,
  CarouselContent,
  CarouselItem,
  CarouselNext,
  CarouselPrevious,
} from "@/components/ui/carousel"

const MemberLab = () => {
  const members = [
    {
      name: "Đỗ Mạnh Quang",
      position: "AI Engineer",
      image: "/lab-members/image.png",
    },
    {
      name: "Nguyễn Thị Mỹ Khánh",
      position: "Frontend Developer",
      image: "/lab-members/z6692141262592_ea51456266918a25bc972e863afa5bab.jpg",
    },
    {
      name: "Nguyễn Thanh Long",
      position: "Backend Developer",
      image: "/lab-members/z6682145384171_dae66d654815c5ce4a45835767ad2670.jpg",
    },
    {
      name: "Nguyễn Thị Minh",
      position: "Backend Developer",
      image: "/lab-members/Nguyen Thi Minh.JPG",
    },
    {
      name: "Chử Thị Ánh",
      position: "Backend Developer",
      image: "/lab-members/LeVanAnh.jpg",
    },
    {
      name: "Ngọ Công Bình",
      position: "Backend Developer",
      image: "/lab-members/TKL00076.jpeg",
    },
    {
      name: "Bùi Huy Nam",
      position: "AI Engineer",
      image: "/lab-members/BuiHuyNam.jpg",
    },
    {
      name: "Phan Đại Cương",
      position: "AI Engineer",
      image: "/lab-members/PhanDaiCuong.jpg",
    },
    {
      name: "Lê Văn Anh",
      position: "Backend Developer",
      image: "/lab-members/LeVanAnh.jpg",
    },
    {
      name: "Nguyễn Quỳnh :v ????",
      position: "Backend Developer",
      image: "/lab-members/z6684553307085_268e1622168024729862855303cd6ee7.jpg",
    },
  ]

  return (
    <Carousel opts={{ align: "start" }}>
      <CarouselContent>
        {members.map((member, index) => (
          <CarouselItem key={index} className="md:basis-1/2 lg:basis-1/3">
            <div className="p-4">
              <Card className="overflow-hidden rounded-xl shadow-md transition hover:shadow-lg">
                <CardContent className="p-0">
                  <Image
                    src={member.image}
                    alt={member.name}
                    width={400}
                    height={300}
                    className="w-full h-60 object-cover"
                  />
                  <div className="p-4 text-center">
                    <h3 className="text-lg font-semibold">{member.name}</h3>
                    <p className="text-sm text-muted-foreground">{member.position}</p>
                  </div>
                </CardContent>
              </Card>
            </div>
          </CarouselItem>
        ))}
      </CarouselContent>
      <CarouselPrevious />
      <CarouselNext />
    </Carousel>
  )
}

export default MemberLab
