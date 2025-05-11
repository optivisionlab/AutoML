"use client";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogOverlay,
  AlertDialogTitle,
  AlertDialogContent,
} from "@/components/ui/alert-dialog";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Skeleton } from "@/components/ui/skeleton";
import axios from "axios";
import {
  Calendar,
  Mail,
  Pencil,
  Phone,
  SquarePen,
  User2,
  UserIcon,
  VenetianMask,
} from "lucide-react";
import { z } from "zod";
import { useSession } from "next-auth/react";
import { useToast } from "@/hooks/use-toast";
import React, { useCallback, useEffect, useState } from "react";

interface User {
  _id: string;
  username: string;
  email: string;
  image: string;
  role: string;
  number: string;
  gender: string;
  date: string;
  fullName: string;
}

interface EditUser {
  email: string;
  gender: string;
  date: string;
  fullName: string;
  number: string;
}

type FormErrors = {
  fullName?: string;
  email?: string;
  date?: string;
  gender?: string;
  number?: string;
};

const formSchema = z.object({
  fullName: z.string().min(5, "Họ và tên có ít nhất 5 ký tự"),
  email: z.string().email("Email không hợp lệ"),
  date: z
    .string()
    .refine((val) => !isNaN(Date.parse(val)), "Ngày sinh không hợp lệ"),
  gender: z.enum(["male", "female"], {
    errorMap: () => ({ message: "Giới tính không hợp lệ" }),
  }),
  number: z.string().regex(/^0(3|5|7|8|9)[0-9]{8}$/, {
    message: "Số điện thoại không hợp lệ",
  }),
});

const Profile = () => {
  const { data: session, status } = useSession();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [avatarUrl, setAvatarUrl] = useState<string | null>(null);
  const [isEditing, setIsEditing] = useState<boolean>(false);
  const [editFormData, setEditFormData] = useState<EditUser | null>(null);
  const [isAlertDialogOpen, setIsAlertDialogOpen] = useState<boolean>(false);
  const [file, setFile] = useState<File | null>(null);
  const [originalAvatar, setOriginalAvatar] = useState<string | null>(null);
  const [formErrors, setFormErrors] = useState<FormErrors>({});
  const { toast } = useToast();

  const fetchUser = useCallback(async () => {
    try {
      const username = session?.user?.username;
      if (!username) return;

      const res = await axios.get(
        `http://10.100.200.119:9999/users/?username=${username}`,
        { headers: { accept: "application/json" } }
      );
      setUser(res.data);
      setEditFormData(res.data);

      const avatar = await axios.get(
        `http://10.100.200.119:9999/get_avatar/${username}`,
        { responseType: "blob" }
      );
      const url = URL.createObjectURL(avatar.data);
      setAvatarUrl(url);
      setOriginalAvatar(url);
    } catch (error) {
      console.error("❌ Lỗi khi lấy thông tin người dùng:", error);
    } finally {
      setLoading(false);
    }
  }, [session?.user?.username]);

  useEffect(() => {
    if (status === "authenticated") {
      fetchUser();
    } else if (status === "unauthenticated") {
      setLoading(false);
    }
  }, [fetchUser, status]);

  // Xử lý upload avatar và hiển thị ngay trong AvatarImage
  const handleAvatarChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = event.target.files?.[0];
    if (!selectedFile) return;
  
    const allowedTypes = ["image/jpeg", "image/png"];
  
    if (!allowedTypes.includes(selectedFile.type)) {
      toast({
        title: "Định dạng ảnh không hợp lệ",
        description: "Chỉ chấp nhận ảnh PNG hoặc JPEG.",
        variant: "destructive",
        duration: 3000,
      });
      return;
    }
  
    if (selectedFile && isEditing) {
      setFile(selectedFile);
      setAvatarUrl(URL.createObjectURL(selectedFile));
    }
  };
  

  useEffect(() => {
    if (!isEditing) {
      setFile(null);
      setAvatarUrl(originalAvatar);
    }
  }, [isEditing, originalAvatar]);

  const handleConfirmUpdate = async () => {
    if (!editFormData || !session?.user?.username) return;

    try {
      const username = session.user.username;

      if (file) {
        const formData = new FormData();
        formData.append("avatar", file);

        await axios.post(
          `http://10.100.200.119:9999/update_avatar?username=${username}`,
          formData,
          {
            headers: {
              "Content-Type": "multipart/form-data",
            },
          }
        );

        window.dispatchEvent(new Event("avatar-updated"));
      }

      console.log("editFormData", editFormData);

      await axios.put(
        `http://10.100.200.119:9999/update/${username}`,
        editFormData,
        {
          headers: {
            "Content-Type": "application/json",
          },
        }
      );

      toast({
        title: "Cập nhật thành công!",
        description: "Thông tin người dùng đã được cập nhật.",
        className:
          "bg-green-50 border border-green-300 text-green-700 [&>div>h3]:text-lg [&>div>h3]:font-semibold",
        duration: 3000,
      });

      await fetchUser();
      setIsEditing(false);
      setIsAlertDialogOpen(false);
    } catch (error) {
      console.log("❌ Lỗi cập nhật thông tin:", error);
      toast({
        title: "Cập nhật thất bại",
        description: "Đã xảy ra lỗi khi cập nhật.",
        variant: "destructive",
        duration: 3000,
      });
    }
  };

  const handleEditClick = () => {
    if (user) {
      const { email, gender, date, fullName, number } = user;

      // Tạo đối tượng theo interface EditUser
      const editUserData: EditUser = {
        email,
        gender,
        date,
        fullName,
        number,
      };

      setEditFormData(editUserData);
      setIsEditing(true);
    }
  };

  const handleValidateAndOpenDialog = () => {
    const result = formSchema.safeParse(editFormData);

    if (!result.success) {
      const formattedErrors = result.error.format();
      setFormErrors({
        fullName: formattedErrors.fullName?._errors[0],
        email: formattedErrors.email?._errors[0],
        date: formattedErrors.date?._errors[0],
        gender: formattedErrors.gender?._errors[0],
        number: formattedErrors.number?._errors[0],
      });
      setIsAlertDialogOpen(false);
      return;
    }

    setFormErrors({});
    setIsAlertDialogOpen(true); // chỉ mở dialog nếu hợp lệ
  };

  if (loading) {
    return (
      <Card className="w-[800px] mx-auto mt-10 p-4">
        <CardHeader className="space-y-4">
          <div className="flex justify-between items-center">
            <Skeleton className="h-6 w-40" />
            <Skeleton className="h-6 w-16" />
          </div>

          <div className="flex justify-center">
            <Skeleton className="w-24 h-24 rounded-full" />
          </div>

          <Skeleton className="h-5 w-1/3 mx-auto" />
        </CardHeader>

        <CardContent className="space-y-4">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-full" />
        </CardContent>
      </Card>
    );
  }

  const InfoRow = ({
    icon: Icon,
    label,
    value,
  }: {
    icon: any;
    label: string;
    value: string;
  }) => (
    <div className="flex items-start gap-4 p-4 border rounded-lg shadow-sm">
      <div className="flex-shrink-0 mt-1">
        <div className="bg-[#dbeafe] text-[#3c6df7] rounded-full p-2 flex items-center justify-center w-10 h-10">
          <Icon className="w-6 h-6" />
        </div>
      </div>
      <div className="flex flex-col">
        <Label className="text-sm text-muted-foreground">{label}</Label>
        <span className="text-base font-medium">{value}</span>
      </div>
    </div>
  );

  return (
    <>
      <Card className="w-[800px] mx-auto mt-10 p-4">
        <CardHeader className="space-y-4">
          <div className="flex justify-between items-center">
            <h1 className="text-xl font-semibold text-[#191919]">
              Thông tin cá nhân
            </h1>
            {!isEditing && (
              <button
                onClick={handleEditClick}
                className="flex items-center gap-1 text-[#3a6df4] hover:underline"
              >
                <SquarePen className="w-4 h-4" />
                <span>Sửa</span>
              </button>
            )}
          </div>

          {/* Avatar ở giữa */}
          <div className="flex justify-center">
            <div className="relative w-24 h-24">
              <Avatar className="w-full h-full cursor-pointer">
                <AvatarImage
                  src={avatarUrl ?? undefined}
                  alt="avatar"
                  className="object-cover"
                />
                <AvatarFallback className="bg-gray-100">
                  <User2 className="w-10 h-10" />
                </AvatarFallback>
              </Avatar>

              {isEditing && (
                <label className="absolute bottom-0 right-0 p-1 bg-white rounded-full shadow-md cursor-pointer">
                  <input
                    type="file"
                    accept="image/png, image/jpeg"
                    onChange={handleAvatarChange}
                    className="hidden"
                  />
                  <SquarePen className="w-5 h-5 text-[#3a6df4]" />
                </label>
              )}
            </div>
          </div>

          {/* Tên hiển thị */}
          <CardTitle className="text-center text-lg">
            {user?.fullName}
            <span className="block text-gray-800 opacity-70 text-sm">
              {user?.username}
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {isEditing && editFormData ? (
            <>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <Label>Họ và tên</Label>
                  <input
                    type="text"
                    value={editFormData.fullName}
                    onChange={(e) =>
                      setEditFormData({
                        ...editFormData,
                        fullName: e.target.value,
                      })
                    }
                    className="w-full border rounded px-3 py-2 mt-1"
                  />
                  {formErrors.fullName && (
                    <p className="text-red-500 text-sm mt-1">
                      {formErrors.fullName}
                    </p>
                  )}
                </div>
                <div>
                  <Label>Email</Label>
                  <input
                    type="email"
                    value={editFormData.email}
                    onChange={(e) =>
                      setEditFormData({
                        ...editFormData,
                        email: e.target.value,
                      })
                    }
                    className="w-full border rounded px-3 py-2 mt-1"
                  />
                  {formErrors.email && (
                    <p className="text-red-500 text-sm mt-1">
                      {formErrors.email}
                    </p>
                  )}
                </div>
                <div>
                  <Label>Ngày sinh</Label>
                  <input
                    type="date"
                    value={editFormData.date}
                    onChange={(e) =>
                      setEditFormData({ ...editFormData, date: e.target.value })
                    }
                    className="w-full border rounded px-3 py-2 mt-1"
                  />
                  {formErrors.date && (
                    <p className="text-red-500 text-sm mt-1">
                      {formErrors.date}
                    </p>
                  )}
                </div>
                <div>
                  <Label>Giới tính</Label>
                  <select
                    value={editFormData.gender}
                    onChange={(e) =>
                      setEditFormData({
                        ...editFormData,
                        gender: e.target.value,
                      })
                    }
                    className="w-full border rounded px-3 py-2 mt-1"
                  >
                    <option value="male">Nam</option>
                    <option value="female">Nữ</option>
                  </select>
                </div>
                <div className="col-span-2">
                  <Label>Số điện thoại</Label>
                  <input
                    type="text"
                    value={editFormData.number}
                    onChange={(e) =>
                      setEditFormData({
                        ...editFormData,
                        number: e.target.value,
                      })
                    }
                    className="w-full border rounded px-3 py-2 mt-1"
                  />
                  {formErrors.number && (
                    <p className="text-red-500 text-sm mt-1">
                      {formErrors.number}
                    </p>
                  )}
                </div>
              </div>

              <div className="flex justify-end gap-3">
                <Button variant="outline" onClick={() => setIsEditing(false)}>
                  Hủy
                </Button>

                <AlertDialog
                  open={isAlertDialogOpen}
                  onOpenChange={setIsAlertDialogOpen}
                >
                  <Button
                    onClick={handleValidateAndOpenDialog}
                    className="bg-[#3a6df4] text-white hover:bg-[#5b85f7]"
                  >
                    Lưu
                  </Button>

                  <AlertDialogOverlay className="fixed inset-0 bg-black/60 z-40" />

                  {/* Alert dialog xác nhận */}
                  <AlertDialogContent className="fixed top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 z-50 bg-white shadow-xl p-6 rounded-xl w-full max-w-md">
                    <AlertDialogHeader className="text-center space-y-2">
                      <AlertDialogTitle className="text-xl font-semibold text-center">
                        XÁC NHẬN
                      </AlertDialogTitle>
                      <AlertDialogDescription className="text-gray-600 text-center">
                        Bạn có chắc chắn muốn lưu các thay đổi này không?
                      </AlertDialogDescription>
                    </AlertDialogHeader>

                    <AlertDialogFooter className="mt-6 flex !justify-center gap-4">
                      <AlertDialogCancel className="bg-red-600 w-20 text-white hover:bg-red-500 hover:text-white px-4 py-2 rounded-md">
                        Hủy
                      </AlertDialogCancel>
                      <AlertDialogAction
                        onClick={handleConfirmUpdate}
                        className="bg-[#3a6df4] w-20 text-white hover:bg-[#5b85f7] px-4 py-2 rounded-md"
                      >
                        Đồng ý
                      </AlertDialogAction>
                    </AlertDialogFooter>
                  </AlertDialogContent>
                </AlertDialog>
              </div>
            </>
          ) : (
            <>
              <InfoRow
                icon={UserIcon}
                label="Tên người dùng"
                value={user?.username || ""}
              />
              <InfoRow
                icon={Pencil}
                label="Họ và tên"
                value={user?.fullName || ""}
              />
              <InfoRow icon={Mail} label="Email" value={user?.email || ""} />
              <InfoRow
                icon={Calendar}
                label="Ngày sinh"
                value={user?.date || ""}
              />
              <InfoRow
                icon={VenetianMask}
                label="Giới tính"
                value={
                  user?.gender === "male"
                    ? "Nam"
                    : user?.gender === "female"
                    ? "Nữ"
                    : "Khác"
                }
              />
              <InfoRow
                icon={Phone}
                label="Số điện thoại"
                value={user?.number || ""}
              />
            </>
          )}
        </CardContent>
      </Card>
    </>
  );
};

export default Profile;
