"use client";
import React, { useEffect, useState } from "react";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useDispatch, useSelector } from "react-redux";
import { updatePostAsync } from "@/redux/slices/postsSlice";
import { AppDispatch, RootState } from "@/redux/store";

const EditBlog = ({ postId }: { postId: string }) => {
  const post = useSelector((state: RootState) =>
    state.posts.posts.find((post) => post.id === postId)
  );

  const dispatch = useDispatch<AppDispatch>();

  const [title, setTitle] = useState<string>("");
  const [body, setBody] = useState<string>("");

  // Cập nhật title và body khi post thay đổi
  useEffect(() => {
    if (post) {
      setTitle(post.title);
      setBody(post.body);
    }
  }, [post]);

  const handeUpdateBlog = async () => {
    if (!post?.title || !post?.body) {
      return;
    }

    const updatedPost = {
      userId: 1,
      id: postId,
      title: title,
      body: body,
    };

    await dispatch(updatePostAsync(updatedPost));
  };

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button className="float-right bg-green-700 ml-5">Edit</Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Update blog</DialogTitle>
          <DialogDescription>
            Update blog here. Click save when you are done.
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="name" className="text-right">
              Title
            </Label>
            <Input
              id="blogTitle"
              className="col-span-3"
              placeholder="Title"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="username" className="text-right">
              Body
            </Label>
            <Textarea
              id="blogBody"
              className="col-span-3 min-h-[200px]"
              placeholder="Type your blog body here"
              value={body}
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button onClick={() => handeUpdateBlog()} type="submit">
              Save
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default EditBlog;
