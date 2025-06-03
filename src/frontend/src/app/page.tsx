import Image from "next/image";
import "./HomePage.scss";
import { Card } from "@/components/ui/card";

export default function Home() {
  const aboutImages = ["/lab1.jpg", "/lab2.jpg", "/lab4.jpg"];

  return (
    <>
      {/* Header Section */}
      <section className="slider-container">
        <div className="container">
          <div className="relative flex-1">
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
      </section>

      {/* Introduction Section */}
      <section className="introduction-container">
        <div className="container">
          <h2 className="introduction-title">Giới thiệu</h2>

          {/* Block 1 */}
          <div className="introduction-content">
            <div className="introduction-component animate-fade-up">
              <div className="introduction-image">
                <Image
                  src="/computer_image.png"
                  alt="ảnh máy tính"
                  width={280}
                  height={280}
                  className="rounded-lg object-cover shadow-md"
                />
              </div>
              <div className="introduction-text">
                <h3>Hệ thống HAutoML</h3>
                <p>
                  HAutoML là viết tắt của{" "}
                  <strong className="font-semibold text-blue-600">
                    Hyper-processor Automated Machine Learning
                  </strong>
                  . Đây là dự án nghiên cứu khoa học của sinh viên trường Công
                  nghệ thông tin và truyền thông, Đại học Công nghiệp Hà Nội.
                  Hệ thống được xây dựng nhằm mục tiêu phát triển một nền tảng
                  AutoML linh hoạt, hiện đại, phục vụ cho nhu cầu nghiên cứu và
                  ứng dụng trong môi trường học thuật.
                </p>
              </div>
            </div>
          </div>

          {/* Block 2 */}
          <div className="introduction-content">
            <div className="introduction-component flex-col-reverse md:flex-row">
              <div className="introduction-text">
                <h3>Xu hướng công nghệ mới</h3>
                <p>
                  Với sự phát triển mạnh mẽ của xu hướng{" "}
                  <strong className="font-semibold text-blue-600">
                    No-code và Low-code
                  </strong>
                  , hệ thống HAutoML mang đến một giải pháp giúp người dùng
                  không chuyên về công nghệ cũng có thể dễ dàng xây dựng và sử
                  dụng các mô hình học máy.
                </p>
              </div>
              <div className="introduction-image">
                <Image
                  src="/AI_image.png"
                  alt="ảnh AI"
                  width={280}
                  height={280}
                  className="rounded-lg object-cover shadow-md"
                />
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* About Us Section */}
      <section className="about-us-container">
        <div className="container">
          <div className="about-us-box-head">
            <h2 className="about-us-title">Về chúng tôi</h2>
            <div className="about-us-content">
              <p>
                OptivisionLab là phòng nghiên cứu tập trung vào trí tuệ nhân
                tạo, với sứ mệnh khám phá và phát triển các giải pháp công nghệ
                tiên tiến phục vụ cho giáo dục, y tế và công nghiệp. Chúng tôi
                kết nối nghiên cứu học thuật với ứng dụng thực tiễn nhằm tạo ra
                giá trị bền vững cho cộng đồng.
              </p>
            </div>
          </div>

          <div className="about-us-images">
            <div className="about-us-grid">
              {aboutImages.map((src, index) => (
                <Card
                  key={index}
                  className="overflow-hidden rounded-xl shadow-md transition-all hover:shadow-lg"
                >
                  <Image
                    src={src}
                    alt={`ảnh phòng lab ${index + 1}`}
                    width={1920}
                    height={1080}
                    className="h-full w-full object-cover transition-transform duration-300 hover:scale-105"
                  />
                </Card>
              ))}
            </div>
          </div>
        </div>
      </section>
    </>
  );
}