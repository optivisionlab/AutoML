"use client";
import React, { useState } from "react";
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
import { useDispatch } from "react-redux";
import { addPostAsync } from "@/redux/slices/postsSlice";
import { AppDispatch } from "@/redux/store";

const CreateBlog = () => {
  const [title, setTitle] = useState<string>("");
  const [body, setBody] = useState<string>("");

  const dispatch = useDispatch<AppDispatch>();

  const handleCreateNew = async () => {
    if (!title || !body) {
      return;
    }

    const newPost = {
      userId: 1,
      title: title,
      body: body,
    };

    await dispatch(addPostAsync(newPost));
    setTitle("");
    setBody("");
  };

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button variant="default" className="float-right bg-purple-500">
          + Add new
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Create new blog</DialogTitle>
          <DialogDescription>
            Create your new blog here. Click save when you are done.
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
              onChange={(e) => setTitle(e.target.value)}
            />
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="username" className="text-right">
              Body
            </Label>
            <Textarea
              id="blogBody"
              className="col-span-3 min-h-[150px]"
              placeholder="Type your blog body here"
              onChange={(e) => setBody(e.target.value)}
            />
          </div>
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button onClick={() => handleCreateNew()} type="submit">
              Create new
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default CreateBlog;
