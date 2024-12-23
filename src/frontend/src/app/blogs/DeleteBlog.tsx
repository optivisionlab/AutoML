import React from "react";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
  AlertDialogTrigger,
} from "@/components/ui/alert-dialog";
import { Button } from "@/components/ui/button";
import { useDispatch } from "react-redux";
import { deletePostAsync } from "@/redux/slices/postsSlice";
import { AppDispatch } from "@/redux/store";

const DeleteBlog = ({ postId }: { postId: string }) => {
  const dispatch = useDispatch<AppDispatch>();

  const handleDelete = async () => {
    await dispatch(deletePostAsync(postId));
  };

  return (
    <AlertDialog>
      <AlertDialogTrigger asChild>
        <Button className="bg-red-600 ml-5">Delete</Button>
      </AlertDialogTrigger>
      <AlertDialogContent>
        <AlertDialogHeader>
          <AlertDialogTitle>Are you absolutely sure?</AlertDialogTitle>
          <AlertDialogDescription>
            This action cannot be undone. This will permanently delete this
            blog.
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter>
          <AlertDialogCancel>Cancel</AlertDialogCancel>
          <AlertDialogAction
            onClick={() => handleDelete()}
            className="bg-red-700"
          >
            Continue
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
};

export default DeleteBlog;
