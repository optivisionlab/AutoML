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
      name: "Đỗ Mạnh Quang (Founder)",
      position: "Lecturer at Department of Computer Science, SICT, HaUI",
      image: "/lab-members/quang.png",
    },
    {
      name: "Nguyễn Thị Lan",
      position: "PQA at NTQ Solution JSC",
      image: "/lab-members/nguyenlan.jpg",
    },
    {
      name: "Nguyễn Thị Mỹ Khánh",
      position: "BA/Frontend Developer at OptiVisionLab, SICT, HaUI",
      image: "/lab-members/mykhanh.jpg",
    },
    {
      name: "Nguyễn Thanh Long",
      position: "BrSE/AI Enginner at FPT Software",
      image: "/lab-members/thanhlong.jpg",
    },
    {
      name: "Nguyễn Thị Minh",
      position: "BA/Backend Developer at FPT Telecom",
      image: "/lab-members/nguyenminh.JPG",
    },
    {
      name: "Chử Thị Ánh",
      position: "Data Engineer at Samsung R&D Vietnam",
      image: "/lab-members/chuanh.jpg",
    },
    {
      name: "Ngọ Công Bình",
      position: "Backend Developer at Samsung Vietnam",
      image: "/lab-members/binh.jpeg",
    },
    {
      name: "Bùi Huy Nam",
      position: "BrSE/Backend Developer at FPT Software",
      image: "/lab-members/BuiHuyNam.jpg",
    },
    {
      name: "Phan Đại Cương",
      position: "Student Research Assistant at OptiVisionLab, SICT, HaUI",
      image: "/lab-members/PhanDaiCuong.jpg",
    },
    {
      name: "Lê Văn Anh",
      position: "Student Research Assistant at OptiVisionLab, SICT, HaUI",
      image: "/lab-members/LeVanAnh.jpg",
    },
    {
      name: "Nguyễn Thị Hải Quỳnh",
      position: "Student Research Assistant at OptiVisionLab, SICT, HaUI",
      image: "/lab-members/haiquynh.jpg",
    },
    {
      name: "Nguyễn Khánh Ly",
      position: "Student Research Assistant at OptiVisionLab, SICT, HaUI",
      image: "/lab-members/khanhly.jpg",
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
