import React from "react";
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
import { useSelector } from "react-redux";
import { RootState } from "@/redux/store";

const ViewBlog = ({ postId }: { postId: string }) => {

  const post = useSelector((state: RootState) => 
    state.posts.posts.find((post) => post.id === postId)
  )

  return (
    <Dialog>
      <DialogTrigger asChild>
        <Button className="float-right bg-blue-700 ml-5">
          View Detail
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>View Detail</DialogTitle>
          <DialogDescription>View detail of this blog</DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="name" className="text-right">
              Title
            </Label>
            <Input
              id="blogTitle"
              className="col-span-3  cursor-not-allowed"
              placeholder="Title"
              value={post?.title}
              readOnly     
            />
          </div>
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="username" className="text-right">
              Body
            </Label>
            <Textarea
              id="blogBody"
              className="col-span-3 min-h-[200px] cursor-not-allowed"
              placeholder="Type your blog body here"
              value={post?.body}
              readOnly
            />
          </div>
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="submit">
              Cancel
            </Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
};

export default ViewBlog;
