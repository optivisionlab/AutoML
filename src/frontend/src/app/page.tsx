import Image from "next/image";
import MemberLab from "@/components/memberLab/MemberLab";
import { Mail, MapPin } from "lucide-react";
import { FaFacebook, FaYoutube, FaLinkedin } from "react-icons/fa";
import Link from "next/link";
import ImageCarousel from "@/components/homeCarousel/ImageCarousel";


export default function Home() {


  return (
    <>
      {/* Header Section */}
      <section id="home" className="w-full relative">
        <ImageCarousel />
      </section>

      {/* Introduction Section */}
      <section
        id="introduction"
        className="py-16 px-4 sm:px-6 lg:px-8 max-w-7xl mx-auto"
      >
        <h2 className="text-3xl font-bold mb-10 text-center text-gray-900 dark:text-white">
          Giới thiệu
        </h2>

        {/* Video + Poem Block */}
        <div className="flex flex-col md:flex-row gap-8 md:gap-12 mb-20">
          {/* Poem */}
          <div className="w-full md:w-1/3 flex items-center justify-center md:justify-start text-center md:text-left text-gray-800 dark:text-gray-200">
            <div>
              <p className="text-xl leading-relaxed italic mb-4">
                "Không có việc gì khó<br />
                Chỉ sợ lòng không bền<br />
                Đào núi và lấp biển<br />
                Quyết chí ắt làm nên"
              </p>
              <p className="font-semibold">– Chủ tịch Hồ Chí Minh</p>
            </div>
          </div>

          {/* Video */}
          <div className="w-full md:w-2/3 aspect-video">
            <iframe
              className="w-full h-full rounded-lg shadow-md border-0"
              src="https://www.youtube.com/embed/lJ2YjlLCUcA?autoplay=1&mute=1"
              title="Hệ thống HAutoML - Giới thiệu"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share"
              referrerPolicy="strict-origin-when-cross-origin"
              allowFullScreen
            ></iframe>
          </div>
        </div>

        {/* Block 1 */}
        <div className="flex flex-col md:flex-row items-center gap-8 mb-16">
          <div className="flex-shrink-0">
            <Image
              src="/computer_image.png"
              alt="ảnh máy tính"
              width={280}
              height={280}
              className="rounded-lg object-cover shadow-md"
            />
          </div>
          <div className="text-justify text-gray-700 dark:text-gray-300">
            <h3 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
              Hệ thống HAutoML
            </h3>
            <p>
              HAutoML là viết tắt của{" "}
              <strong className="text-blue-600 dark:text-blue-400">
                HYPER-PROCESSOR AUTOMATED MACHINE LEARNING
              </strong>
              . Đây là dự án nghiên cứu khoa học của sinh viên trường Công nghệ
              thông tin và truyền thông, Đại học Công nghiệp Hà Nội. Hệ thống
              được xây dựng nhằm mục tiêu phát triển một nền tảng AutoML linh
              hoạt, hiện đại, phục vụ cho nhu cầu nghiên cứu và ứng dụng trong
              môi trường học thuật.
            </p>
          </div>
        </div>

        {/* Block 2 */}
        <div className="flex flex-col-reverse md:flex-row items-center gap-8">
          <div className="text-justify text-gray-700 dark:text-gray-300">
            <h3 className="text-2xl font-semibold mb-4 text-gray-900 dark:text-white">
              Xu hướng công nghệ mới
            </h3>
            <p>
              Với sự phát triển mạnh mẽ của xu hướng{" "}
              <strong className="text-blue-600 dark:text-blue-400">
                NO-CODE VÀ LOW-CODE
              </strong>
              , hệ thống HAutoML mang đến một giải pháp giúp người dùng không
              chuyên về công nghệ cũng có thể dễ dàng xây dựng và sử dụng các mô
              hình học máy.
            </p>
          </div>
          <div className="flex-shrink-0">
            <Image
              src="/AI_image.png"
              alt="ảnh AI"
              width={280}
              height={280}
              className="rounded-lg object-cover shadow-md"
            />
          </div>
        </div>
      </section>

      {/* About Us Section */}
      <section
        id="about-us"
        className="bg-gray-100 dark:bg-background py-16"
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <h2 className="text-3xl font-bold text-center mb-6 text-gray-900 dark:text-white">
            Về chúng tôi
          </h2>
          <p className="text-center max-w-3xl mx-auto mb-12 text-gray-700 dark:text-gray-300">
            OptivisionLab là phòng nghiên cứu tập trung vào trí tuệ nhân tạo,
            với sứ mệnh khám phá và phát triển các giải pháp công nghệ tiên
            tiến phục vụ cho giáo dục, y tế và công nghiệp. Chúng tôi kết nối
            nghiên cứu học thuật với ứng dụng thực tiễn nhằm tạo ra giá trị bền
            vững cho cộng đồng.
          </p>
          <MemberLab />
        </div>
      </section>

      <footer id="contact" className="py-12 bg-white dark:bg-background">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 grid grid-cols-1 md:grid-cols-2 gap-8">
          {/* Left column: Company Info */}
          <div className="flex flex-col justify-between">
            <div>
              <Image
                src="/textHAutoML-removebg-preview.png"
                priority
                width={120}
                height={80}
                alt="logo"
                className="mb-8 mt-5"
              />
              <div className="flex items-start text-sm text-gray-800 dark:text-gray-200 mb-2">
                <MapPin className="w-4 h-4 mt-0.5 mr-2" />
                <span>
                  Đại Học Công Nghiệp Hà Nội, Số 298 đường Cầu Diễn, phường Minh Khai, quận Bắc Từ Liêm, Hà Nội
                </span>
              </div>
              <div className="flex items-start text-sm text-orange-500 mb-4">
                <Mail className="w-4 h-4 mt-0.5 mr-2" />
                <a href="mailto:optivision.work@gmail.com" className="hover:underline">
                  optivision.work@gmail.com
                </a>
              </div>
            </div>

            <div className="flex items-center text-xs text-gray-600 dark:text-gray-400">
              <span>© 2025 OptivisionLab</span>
              <div className="flex items-center space-x-4 ml-5">
                <Link href="https://www.facebook.com/meoluoiai" className="text-blue-600" aria-label="Facebook">
                  <FaFacebook className="w-5 h-5" />
                </Link>
                <Link href="https://www.youtube.com/@meoluoiai" className="text-red-600" aria-label="YouTube">
                  <FaYoutube className="w-5 h-5" />
                </Link>
                {/* <Link href="#" className="text-blue-800" aria-label="LinkedIn">
                  <FaLinkedin className="w-5 h-5" />
                </Link> */}
              </div>
            </div>
          </div>

          {/* Right column: Google Map */}
          <div>
            <iframe
              title="OptivisionLab Location"
              width="100%"
              height="250"
              className="rounded-lg shadow"
              style={{ border: 0 }}
              loading="lazy"
              referrerPolicy="no-referrer-when-downgrade"
              src="https://www.google.com/maps/embed?pb=!1m18!1m12!1m3!1d3723.47378845151!2d105.73253187503212!3d21.05373098060188!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!3m3!1m2!1s0x31345457e292d5bf%3A0x20ac91c94d74439a!2zVHLGsOG7nW5nIMSQ4bqhaSBo4buNYyBDw7RuZyBuZ2hp4buHcCBIw6AgTuG7mWk!5e0!3m2!1svi!2s!4v1749670895769!5m2!1svi!2s"
            ></iframe>
          </div>
        </div>
      </footer>
    </>
  );
}