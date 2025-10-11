import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";

export default function DialogForm({
  open,
  onOpenChange,
  title,
  description,
  canceltext = "Hủy",
  actionText,
  onCancle,
  onConfirm,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  canceltext: string;
  actionText: string;
  onCancle?: () => void;
  onConfirm: () => void;
}) {
  return (
    <AlertDialog open={open} onOpenChange={onOpenChange}>
      <AlertDialogContent className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 bg-white shadow-xl p-6 rounded-xl w-full max-w-md">
        <AlertDialogHeader className="text-center space-y-2">
          <AlertDialogTitle className="text-xl font-semibold text-center">
            {title}
          </AlertDialogTitle>
          <AlertDialogDescription className="text-gray-600 text-center">
            {description}
          </AlertDialogDescription>
        </AlertDialogHeader>
        <AlertDialogFooter className=" flex !justify-center gap-4">
          <AlertDialogCancel
            onClick={() => onCancle}
            className="bg-red-600 w-20 text-white hover:bg-red-500 hover:text-white px-4 py-2 rounded-md"
          >
            {canceltext}
          </AlertDialogCancel>
          <AlertDialogAction
            onClick={onConfirm}
            className="bg-[#3a6df4] w-20 text-white hover:bg-[#5b85f7] px-4 py-2 rounded-md"
          >
            {actionText}
          </AlertDialogAction>
        </AlertDialogFooter>
      </AlertDialogContent>
    </AlertDialog>
  );
}
