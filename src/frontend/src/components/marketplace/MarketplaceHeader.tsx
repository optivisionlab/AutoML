"use client";

import React from "react";

interface MarketplaceHeaderProps {
  title?: string;
  description?: string;
  searchValue: string;
  onSearchChange: (value: string) => void;
  onCreate?: () => void;
}

export default function MarketplaceHeader({
  title = "Marketplace",
  description = "Khám phá các Mô hình AI, lấy API Key và bắt đầu tích hợp",
  searchValue,
  onSearchChange,
}: MarketplaceHeaderProps) {
  return (
    <div className="border-b bg-white">
      <div className="max-w-8xl mx-auto px-10 py-5">
        {/* Title */}
        <h1 className="text-2xl font-semibold text-gray-900">{title}</h1>

        {/* Description + Actions */}
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mt-2">
          <p className="text-sm text-gray-500">{description}</p>

          <div className="flex items-center gap-3">
            {/* Search */}
            <input
              type="text"
              placeholder="Tìm kiếm mô hình AI..."
              value={searchValue}
              onChange={(e) => onSearchChange(e.target.value)}
              className="w-64 px-3 py-2 text-sm border rounded-md focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
          </div>
        </div>
      </div>
    </div>
  );
}
