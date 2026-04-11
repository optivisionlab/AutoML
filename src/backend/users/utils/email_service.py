# Standard Libraries
import os
import logging
import smtplib
import base64
import urllib.parse
from io import BytesIO
from pathlib import Path

# Third party Libraries
from dotenv import load_dotenv
import qrcode
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart


# Logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
if not logger.handlers:
    console_handler = logging.StreamHandler()
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

# Loads env
load_dotenv()

class GmailService:
    def __init__(self) -> None:
        self._sender_email: str | None = os.getenv("MAIL_USERNAME")
        self._app_password: str | None = os.getenv("MAIL_PASSWORD")
        self._frontend_url: str = os.getenv("FRONTEND_URL")
        self._logo: str = os.getenv("LOGO")

        if not self._sender_email or not self._app_password:
            logger.warning("MAIL_USERNAME or MAIL_PASSWORD is not set in environment variables")

        backend_dir = Path(__file__).resolve().parent.parent.parent

        self._template_email_for_verifications = backend_dir / "assets" / "verificationEmailForm.html"
        self._template_email_for_otp = backend_dir / "assets" / "otpEmailForm.html"

    def _get_verification_html(self, verify_link: str) -> str:
        try:
            with open(self._template_email_for_verifications, "r", encoding="utf-8") as file:
                html_content = file.read()

            html_content = html_content.replace("{{verify_link}}", verify_link)
            html_content = html_content.replace("{{logo_link}}", self._logo)

            return html_content
        except FileNotFoundError:
            logger.error(f"Not found file HTML template at: {self._template_email_for_verifications}")

            return f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eaeaea; border-radius: 10px;">
                <h2 style="color: #333;">Xin chào!</h2>
                <p style="color: #555; line-height: 1.5;">
                    Cảm ơn bạn đã đăng ký. Vui lòng nhấn vào nút bên dưới để xác thực địa chỉ email của bạn. 
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verify_link}" style="background-color: #000000; color: #ffffff; padding: 12px 24px; text-decoration: none; border-radius: 5px; font-weight: bold; display: inline-block;">
                        Xác thực tài khoản
                    </a>
                </div>
                
                <div style="text-align: center; margin-top: 20px;">
                    <p style="color: #666; font-size: 14px;">Hoặc quét mã QR dưới đây bằng điện thoại:</p>
                    <img src="cid:qr_code" alt="QR Code" style="width: 150px; height: 150px; border: 1px solid #ccc; border-radius: 10px;" />
                </div>
                
                <p style="color: #999; font-size: 12px; text-align: center;">
                    Liên kết này sẽ hết hạn trong 15 phút.
                </p>
            </div>
            """
    
    def _get_otp_html(self, otp: str) -> str:
        try:
            with open(self._template_email_for_otp, "r", encoding="utf-8") as file:
                html_content = file.read()

            html_content = html_content.replace("{{otpCode}}", otp)

            return html_content
        except FileNotFoundError:
            logger.error(f"Not found file HTML template at: {self._template_email_for_otp}")

            return f"""
            <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto; padding: 20px; border: 1px solid #eaeaea; border-radius: 10px;">
                <h2 style="color: #333;">Xin chào!</h2>
                <p style="color: #555; line-height: 1.5;">
                    Chúng tôi đã nhận được yêu cầu đặt lại mật khẩu cho tài khoản của bạn tại HAutoML.
                    Vui lòng sử dụng mã xác minh (OTP) dưới đây để tiếp tục quá trình.
                </p>
                <div style="text-align: center; margin: 30px 0;">
                    {otp}
                </div>
                
                <div style="color: #777; font-size: 14px; line-height: 1.6">
                    <span style="font-weight: bold;">Lưu ý:</span>
                    <ul>
                        <li >Mã này có hiệu lực trong vòng 5 phút.</li>
                        <li >
                            Nếu bạn không thực hiện yêu cầu này, vui lòng bỏ qua email này
                            hoặc liên hệ với bộ phận.
                        </li>
                        <li>
                            Tuyệt đối không chia sẻ mã này với bất kỳ ai.
                        </li>
                    </ul>
                </div>
            </div>
            """
    
    def send_verification_email(self, email_to: str, token: str, qr_base64: str = None) -> bool:
        if not self._sender_email or not self._app_password:
            logger.error("Cannot send email: Credentials missing.")
            return False

        verify_link = self.get_verify_link(token)

        if not qr_base64:
            qr_base64 = self.generate_qr_base64(verify_link)

        # Email structure
        msg = MIMEMultipart('related')
        msg['From'] = f"HAutoML Teams <{self._sender_email}>"
        msg['To'] = email_to
        msg['Subject'] = "Kích hoạt tài khoản HAutoML"

        html_content = self._get_verification_html(verify_link)
        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)
        msg_alternative.attach(MIMEText(html_content, 'html'))

        try:
            img_data = base64.b64decode(qr_base64)
            image_part = MIMEImage(img_data, name="qrcode.png")

            image_part.add_header('Content-ID', '<qr_code>')
            image_part.add_header('Content-Disposition', 'inline', filename='qrcode.png')
            msg.attach(image_part)
        except Exception as e:
            logger.error(f"Error attaching QR Code image: {str(e)}")
        
        try:
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self._sender_email, self._app_password)
                server.send_message(msg)

            logger.info(f"Verification email sent successfully to {email_to} via Gmail")
            return True
        except Exception as e:
            logger.error(f"Error sending verification email to {email_to}: {str(e)}", exc_info=True)
            return False

    def send_otp(self, email_to: str, otp: str) -> bool:
        if not self._sender_email or not self._app_password:
            logger.error("Cannot send email: Credentials missing.")
            return False

        # Email structure
        msg = MIMEMultipart('related')
        msg['From'] = f"HAutoML Teams <{self._sender_email}>"
        msg['To'] = email_to
        msg['Subject'] = "Yêu cầu đặt lại mật khẩu"

        html_content = self._get_otp_html(otp)
        msg_alternative = MIMEMultipart('alternative')
        msg.attach(msg_alternative)
        msg_alternative.attach(MIMEText(html_content, 'html'))
        
        try:
            with smtplib.SMTP('smtp.gmail.com', 587) as server:
                server.starttls()
                server.login(self._sender_email, self._app_password)
                server.send_message(msg)

            logger.info(f"Verification email sent successfully to {email_to} via Gmail")
            return True
        except Exception as e:
            logger.error(f"Error sending verification email to {email_to}: {str(e)}", exc_info=True)
            return False
 
    def get_verify_link(self, token: str) -> str:
        safe_token = urllib.parse.quote(token)
        return f"{self._frontend_url}/verify-email?token={safe_token}"

    def generate_qr_base64(self, link: str) -> str:
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(link)
        qr.make(fit=True)

        img = qr.make_image(fill_color="black", back_color="white")
        
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        
        img_str = base64.b64encode(buffered.getvalue()).decode("utf-8")
        return img_str


# Khởi tạo instance
email_service = GmailService()