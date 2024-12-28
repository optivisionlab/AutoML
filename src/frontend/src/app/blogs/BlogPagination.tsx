import React, { useState } from "react";
import {
  Pagination,
  PaginationContent,
  PaginationItem,
  PaginationLink,
  PaginationPrevious,
  PaginationNext,
  PaginationEllipsis,
} from "@/components/ui/pagination";

// eslint-disable-next-line @typescript-eslint/no-explicit-any
const BlogPagination = ({ totalPosts, rowsPerPage, onPageChange }: any) => {
  const totalPages = Math.ceil(totalPosts / rowsPerPage);
  const [currentPage, setCurrentPage] = useState(1);

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
    onPageChange(page);
  };

  const getPageNumbers = () => {
    const pages = [1]; 

    if (totalPages > 1) {
      if (currentPage <= 2) {
        pages.push(2, 3);
        if (totalPages > 3) pages.push("...");
      } else if (currentPage >= totalPages - 1) {
        if (totalPages > 3) pages.push("...");
        pages.push(totalPages - 2, totalPages - 1);
      } else {
        pages.push("...", currentPage - 1, currentPage, currentPage + 1, "...");
      }

      if (totalPages > 1) pages.push(totalPages); 
    }

    return pages;
  };

  const pagesToShow = getPageNumbers();

  return (
    <Pagination className="mb-8">
      <PaginationContent>
        <PaginationItem>
          <PaginationPrevious
            href="#"
            className={currentPage === 1 ? "pointer-events-none opacity-50" : ""}
            onClick={() => handlePageChange(currentPage - 1)}
          />
        </PaginationItem>

        {pagesToShow.map((page, index) =>
          page === "..." ? (
            <PaginationItem key={`ellipsis-${index}`}>
              <PaginationEllipsis />
            </PaginationItem>
          ) : (
            <PaginationItem key={`page-${page}`}>
              <PaginationLink
                href="#"
                isActive={currentPage === page}
                onClick={() => handlePageChange(page as number)}
              >
                {page}
              </PaginationLink>
            </PaginationItem>
          )
        )}

        <PaginationItem>
          <PaginationNext
            href="#"
            className={
              currentPage === totalPages ? "pointer-events-none opacity-50" : ""
            }
            onClick={() => handlePageChange(currentPage + 1)}
          />
        </PaginationItem>
      </PaginationContent>
    </Pagination>
  );
};

export default BlogPagination;
