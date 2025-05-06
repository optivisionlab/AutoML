import Image from "next/image";
import "./HomePage.scss";
import { Card } from "@/components/ui/card";

export default function Home() {
  return (
    <>
      {/* Header image start */}
      <div className="slider-container">
        <div className="container">
          <div className="flex">
            <div className="flex-1">
              <Image
                src="/Chung-chi-PCI-DSS-04.png"
                alt="Nền"
                className="background-image"
                width={1920}
                height={1080}
              />

              <div className="text-wrapper">
                <div className="text-content">
                  Chúng tôi cung cấp giải pháp tốt nhất cho <br />
                  <span>Tự động hóa học máy</span>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      {/* Header image end */}

      {/* Introduction start */}
      <div className="introduction-container">
        <div className="container">
          <div className="introduction-title">
            <h2>Giới thiệu</h2>
          </div>

          <div className="introduction-content">
            <div className="introduction-content mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8 md:py-12">
              <div className="introduction-component animate-fade-up flex flex-col items-center justify-between gap-8 rounded-xl p-6 md:flex-row md:gap-12 md:p-8 lg:gap-16 lg:p-10">
                <div className="w-full shrink-0 md:w-auto">
                  <Image
                    src={"/computer_image.png"}
                    alt="ảnh máy tính"
                    width={280}
                    height={280}
                    className="rounded-lg object-cover shadow-md"
                  />
                </div>

                <div className="flex-1 space-y-4 text-center md:text-left">
                  <h3 className="text-2xl font-bold text-gray-900 sm:text-2xl md:text-2xl lg:text-2xl">
                    Hệ thống HAutoML
                  </h3>
                  <p className="text-base leading-relaxed text-gray-600 sm:text-lg md:text-base lg:text-lg">
                    HAutoML là viết tắt của{" "}
                    <strong className="font-semibold text-blue-600">
                      Hyper-processor Automated Machine Learning
                    </strong>
                    . Đây là dự án nghiên cứu khoa học của sinh viên trường Công
                    nghệ thông tin và truyền thông, Đại học Công nghiệp Hà Nội
                    thực hiện. Hệ thống được xây dựng nhằm mục tiêu phát triển
                    một nền tảng AutoML linh hoạt, hiện đại, phục vụ cho nhu cầu
                    nghiên cứu và ứng dụng trong môi trường học thuật.
                  </p>
                </div>
              </div>
            </div>

            <div className="introduction-content mx-auto max-w-7xl px-4 sm:px-6 lg:px-8 py-8 md:py-12">
              <div className="introduction-component flex flex-col items-center justify-between gap-8 rounded-xl p-6 md:flex-row md:gap-12 md:p-8 lg:gap-16 lg:p-10">
                <div className="flex-1 space-y-4 text-center md:text-left">
                  <h3 className="text-2xl font-bold text-gray-900 sm:text-2xl md:text-2xl lg:text-2xl">
                    Xu hướng công nghệ mới
                  </h3>
                  <p className="text-base leading-relaxed text-gray-600 sm:text-lg md:text-base lg:text-lg">
                    Với sự phát triển mạnh mẽ của xu hướng{" "}
                    <strong className="font-semibold text-blue-600">
                      No-code và Low-code
                    </strong>
                    , hệ thống HAutoML mang đến một giải pháp giúp người dùng
                    không chuyên về công nghệ cũng có thể dễ dàng xây dựng và sử
                    dụng các mô hình học máy.
                  </p>
                </div>

                <div className="w-full shrink-0 md:w-auto">
                  <Image
                    src={"/AI_image.png"}
                    alt="ảnh máy tính"
                    width={280}
                    height={280}
                    className="rounded-lg object-cover shadow-md"
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      {/* Introduction end */}

      {/* About us start */}
      <div className="about-us-container">
        <div className="container">
          <div className="about-us-box-head">
            <div className="about-us-title">
              <h2>Về chúng tôi</h2>
            </div>
            <div className="about-us-content mx-auto max-w-7xl px-4 sm:px-6">
              <p>
                OptivisionLab là phòng nghiên cứu tập trung vào trí tuệ nhân
                tạo, với sứ mệnh khám phá và phát triển các giải pháp công nghệ
                tiên tiến phục vụ cho giáo dục, y tế và công nghiệp. Chúng tôi
                kết nối nghiên cứu học thuật với ứng dụng thực tiễn nhằm tạo ra
                giá trị bền vững cho cộng đồng.
              </p>
            </div>
          </div>

          <div className="flex">
            <div className="about-us-images mx-auto max-w-7xl px-4 py-8 sm:px-6 sm:py-12 lg:px-8 lg:py-16">
              <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6 lg:gap-8">
                {/* Card 1 */}
                <Card className="overflow-hidden rounded-xl shadow-md transition-all hover:shadow-lg">
                  <Image
                    src="/lab1.jpg"
                    alt="ảnh phòng lab"
                    width={1920}
                    height={1080}
                    className="h-full w-full object-cover transition-transform duration-300 hover:scale-105"
                  />
                </Card>

                {/* Card 2 */}
                <Card className="overflow-hidden rounded-xl shadow-md transition-all hover:shadow-lg">
                  <Image
                    src="/lab2.jpg"
                    alt="ảnh phòng lab"
                    width={1920}
                    height={1080}
                    className="h-full w-full object-cover transition-transform duration-300 hover:scale-105"
                  />
                </Card>

                {/* Card 3 */}
                <Card className="overflow-hidden rounded-xl shadow-md transition-all hover:shadow-lg">
                  <Image
                    src="/lab4.jpg"
                    alt="ảnh phòng lab"
                    width={1920}
                    height={1080}
                    className="h-full w-full object-cover transition-transform duration-300 hover:scale-105"
                  />
                </Card>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* About us end */}

      {/* Contact section start */}
      {/* <div className="contact-container">
        <div className="contact-title">
          <h2>Liên hệ</h2>
        </div>
      </div> */}
      {/* Contact section end */}
    </>
  );
}
