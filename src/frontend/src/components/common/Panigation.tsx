"use client";

import React from "react";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationNext,
  PaginationPrevious,
} from "@/components/ui/pagination";
import { Button } from "@/components/ui/button";

interface PaginationCustomProps {
  currentPage: number;
  totalPages: number;
  onPageChange: (page: number) => void;
}

const PaginationCustom: React.FC<PaginationCustomProps> = ({
  currentPage,
  totalPages,
  onPageChange,
}) => {
  if (totalPages <= 1) return null;

  const renderPages = (): React.ReactElement[] => {
    const pages: React.ReactElement[] = [];
    const maxVisible = 5;
    let startPage = Math.max(1, currentPage - 2);
    let endPage = Math.min(totalPages, startPage + maxVisible - 1);

    if (endPage - startPage < maxVisible - 1) {
      startPage = Math.max(1, endPage - maxVisible + 1);
    }

    // Trang đầu tiên + dấu ...
    if (startPage > 1) {
      pages.push(
        <PaginationItem key={1}>
          <Button
            variant="ghost"
            onClick={() => onPageChange(1)}
            className={`px-3 ${
              currentPage === 1
                ? "bg-white border border-gray-300 text-black"
                : ""
            }`}
          >
            1
          </Button>
        </PaginationItem>
      );

      if (startPage > 2) {
        pages.push(
          <PaginationItem key="start-ellipsis">
            <span className="px-2">...</span>
          </PaginationItem>
        );
      }
    }

    // Các trang ở giữa
    for (let i = startPage; i <= endPage; i++) {
      pages.push(
        <PaginationItem key={i}>
          <Button
            variant="ghost"
            onClick={() => onPageChange(i)}
            className={`px-3 ${
              currentPage === i
                ? "bg-white border border-gray-300 text-black"
                : ""
            }`}
          >
            {i}
          </Button>
        </PaginationItem>
      );
    }

    // Trang cuối cùng + dấu ...
    if (endPage < totalPages) {
      if (endPage < totalPages - 1) {
        pages.push(
          <PaginationItem key="end-ellipsis">
            <span className="px-2">...</span>
          </PaginationItem>
        );
      }

      pages.push(
        <PaginationItem key={totalPages}>
          <Button
            variant="ghost"
            onClick={() => onPageChange(totalPages)}
            className={`px-3 ${
              currentPage === totalPages
                ? "bg-white border border-gray-300 text-black"
                : ""
            }`}
          >
            {totalPages}
          </Button>
        </PaginationItem>
      );
    }

    return pages;
  };

  return (
    <Pagination className="mt-4 justify-center">
      <PaginationContent>
        {/* Prev Button */}
        <PaginationItem>
          <PaginationPrevious
            onClick={() => onPageChange(Math.max(currentPage - 1, 1))}
            className={
              currentPage === 1 ? "pointer-events-none opacity-50" : ""
            }
          />
        </PaginationItem>

        {renderPages()}

        {/* Next Button */}
        <PaginationItem>
          <PaginationNext
            onClick={() => onPageChange(Math.min(currentPage + 1, totalPages))}
            className={
              currentPage === totalPages ? "pointer-events-none opacity-50" : ""
            }
          />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  );
};

export default PaginationCustom;
