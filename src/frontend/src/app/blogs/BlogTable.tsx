"use client";
import React, { useEffect, useState } from "react";
import { useDispatch, useSelector } from "react-redux";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import DeleteBlog from "@/app/blogs/DeleteBlog";
import CreateBlog from "@/app/blogs/CreateBlog";
import EditBlog from "@/app/blogs/EditBlog";
import ViewBlog from "@/app/blogs/ViewBlog";
import SearchBlog from "@/app/blogs/SearchBlog";
import {
  fetchPostsAsync,
  getPostsStatus,
  selectAllPosts,
} from "@/redux/slices/postsSlice";
import { AppDispatch } from "@/redux/store";
import BlogPagination from "@/app/blogs/BlogPagination";

const BlogTable = () => {
  const dispatch = useDispatch<AppDispatch>();

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  // dữ liệu gốc, các post lấy từ redux
  const posts = useSelector(selectAllPosts);
  const status = useSelector(getPostsStatus);

  // dữ liệu hiển thị trên bảng
  const [displayedPosts, setDisplayedPosts] = useState<IPost[]>([]);

  useEffect(() => {
    if (status === "idle") {
      dispatch(fetchPostsAsync());
    }
  }, [dispatch, status]);

  // console.log(">> display: ", displayedPosts);

  useEffect(() => {
    setDisplayedPosts(posts);
  }, [posts]);

  // pagination
  const rowsPerPage = 10;
  const [currentPage, setCurrentPage] = useState<number>(1);
  const totalPosts = posts.length;

  const startIndex = (currentPage - 1) * rowsPerPage;
  const endIndex = startIndex + rowsPerPage;

  return (
    <div>
      <h2 className="text-center mt-8 text-red-600 mb-12">Blog Page</h2>
      <div className="w-4/5 mx-auto">
        <SearchBlog posts={posts} setDisplayedPosts={setDisplayedPosts} />
        <CreateBlog />
        <Table className="mt-12 mb-8">
          <TableHeader>
            <TableRow>
              <TableHead className="w-[100px]">No</TableHead>
              <TableHead className="text-center">Title</TableHead>
              <TableHead className="text-center">Body</TableHead>
              <TableHead className="text-center">Action</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {displayedPosts.slice(startIndex, endIndex).map((post: IPost) => (
              <TableRow key={post.id}>
                <TableCell className="font-medium">{post.id}</TableCell>
                <TableCell>{post.title}</TableCell>
                <TableCell>{post.body}</TableCell>
                <TableCell className="flex">
                  <ViewBlog postId={post.id} />
                  <EditBlog postId={post.id} />
                  <DeleteBlog postId={post.id} />
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>

        <BlogPagination
          totalPosts={totalPosts}
          rowsPerPage={rowsPerPage}
          onPageChange={handlePageChange}
        />
      </div>
    </div>
  );
};

export default BlogTable;
