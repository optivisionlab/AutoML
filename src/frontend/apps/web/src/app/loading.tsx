import AppLoading from "@/shared/components/common/AppLoading";

export default function Loading() {
  return (
    <div className="flex w-full min-h-[60vh] items-center justify-center py-12">
      <AppLoading
        variant="section"
        className="w-full max-w-md border-none bg-transparent shadow-none dark:bg-transparent"
      />
    </div>
  );
}
