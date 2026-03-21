"use client";

import { useRouter } from "next/navigation";
import toSlug from "@/utils/toSlug";
import React from "react";
import Image from "next/image";

export interface MarketplaceModel {
  id: number;
  name: string;
  img: string;
  description: string;
  category: string;
  price: string;
  provider: string;
}

interface Props {
  model: MarketplaceModel;
  onViewDetail?: (model: MarketplaceModel) => void;
}

export default function MarketplaceCard({ model, onViewDetail }: Props) {
  const router = useRouter();

  return (
    <div
      onClick={() => {
        router.push(`/market-place/${toSlug(model.name)}`);
        console.log(model.name);
      }}
      className="relative group flex bg-white border rounded-lg p-5 hover:shadow-md transition cursor-pointer"
    >
      {/* Icon */}
      <div className="w-12 h-12 border rounded-sm text-xs text-gray-400">
        <Image
          src={model.img}
          width={10}
          height={10}
          className="w-10 h-10"
          alt={model.name}
        />
      </div>

      {/* Content */}
      <div className="ml-4 flex flex-col flex-1">
        <div className="text-xs text-gray-500 mb-1">{model.provider}</div>

        <h3 className="text-lg font-semibold text-gray-900">{model.name}</h3>

        <p className="text-sm text-gray-600 mt-1 line-clamp-2">
          {model.description}
        </p>

        <div className="flex justify-between items-center mt-3 text-xs">
          <span className="px-2 py-1 rounded bg-gray-100 text-gray-600">
            {model.category.toUpperCase()}
          </span>
          <span className="text-blue-600 font-medium">{model.price}</span>
        </div>
      </div>

      {/* Hover Detail Bubble */}
      <div
        className="
                absolute left-1/2 top-full mt-3 -translate-x-1/2
                w-72 bg-white border rounded-lg shadow-lg p-4
                opacity-0 scale-95
                group-hover:opacity-100 group-hover:scale-100
                transition-all duration-200
                pointer-events-none
                z-20
        "
      >
        {/* Arrow */}
        <div
          className="
                absolute -top-2 left-1/2 -translate-x-1/2
                w-4 h-4 bg-white
                border-l border-t
                rotate-45
        "
        />

        <h4 className="text-sm font-semibold text-gray-900">
          Thông tin chi tiết
        </h4>

        <p className="text-xs text-gray-600 mt-2">{model.description}</p>

        <div className="mt-3 space-y-1 text-xs text-gray-700">
          <div>
            <span className="font-medium">Nhà cung cấp:</span> {model.provider}
          </div>
          <div>
            <span className="font-medium">Danh mục:</span>{" "}
            {model.category.toUpperCase()}
          </div>
          <div>
            <span className="font-medium">Giá:</span> {model.price}
          </div>
        </div>
      </div>
    </div>
  );
}
