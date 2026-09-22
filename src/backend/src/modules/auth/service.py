# Standard Libraries
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime, timezone, timedelta

# Third-party Libraries
from fastapi import BackgroundTasks, status

# Local Libraries
from src.core import security, exceptions
from src.shared import utils, constants, email_service
from src.modules.auth.schemas import UserRegisterRequest, UserResponse, UserLoginRequest, TokenResponse, ResetPasswordRequest
from src.modules.auth.repository import AuthRepository


class AuthService:
    def __init__(self, repo: AuthRepository):
        self.repo = repo

    def _generate_tokens(self, user_id: str | ObjectId, role: str, email: str) -> TokenResponse:
        access_token = security.jwt_service.create_access_token({
            'sub': str(user_id),
            'role': role,
            'email': email
        })
        refresh_token = security.jwt_service.create_refresh_token({
            'sub': str(user_id)
        })
        return TokenResponse(access_token=access_token, refresh_token=refresh_token)

    def _generate_token_and_qr_code(self, user_id: str | ObjectId, email: str, background_tasks: BackgroundTasks):
        # Generate Token & QR Code
        verification_token = security.jwt_service.create_verification_token({
            'sub': str(user_id),
            'email': email
        })

        verify_link = email_service.get_verify_link(verification_token)
        qr_base64 = email_service.generate_qr_base64(verify_link)

        background_tasks.add_task(
            email_service.send_verification_email,
            email,
            verification_token,
            qr_base64
        )

    """
    Register
    """
    async def register(self, user_data: UserRegisterRequest, background_tasks: BackgroundTasks) -> UserResponse:
        # Existence check
        if await self.repo.check_user_exists(user_data.email, user_data.username):
            raise exceptions.CustomException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Username or Email already registered",
                error_code=constants.ErrorCode.BAD_REQUEST,
            )

        now_timestamp = datetime.now(timezone.utc).timestamp()

        # Create user doc
        new_user_doc = {
            "username": user_data.username,
            "email": user_data.email,
            "gender": user_data.gender,
            "date": user_data.date,
            "number": user_data.number,
            "fullName": user_data.fullName,
            "role": "user",
            "avatar": None,
            "is_verified": False,
            "created_at": now_timestamp
        }
        user_id = await self.repo.create_user(new_user_doc)

        # Create linked account
        linked_account_doc = {
            "user_id": user_id,
            "provider": "local",
            "provider_id": user_data.email,
            "password": user_data.password,
            "created_at": now_timestamp
        }
        await self.repo.create_linked_account(linked_account_doc)

        # Generate Token & QR Code
        self._generate_token_and_qr_code(user_id, user_data.email, background_tasks)

        created_user = await self.repo.get_user_by_id(user_id)
        created_user['_id'] = str(created_user['_id'])

        return UserResponse(**created_user)

    """
    Login
    """
    async def login(self, data: UserLoginRequest) -> TokenResponse:
        # Find users
        user = await self.repo.get_user_by_login_identifier(data.username)
        if not user:
            raise exceptions.CustomException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect account or password",
                error_code=constants.ErrorCode.UNAUTHORIZED
            )

        # Email verification
        if not user.get('is_verified', True):
            raise exceptions.CustomException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Your account has not been verified. Please check your email",
                error_code=constants.ErrorCode.FORBIDDEN
            )

        # Check password
        is_valid_password = False

        if user.get('password'):
            is_valid_password = (data.password == user['password']) 
        else:
            account = await self.repo.get_local_linked_account(user['_id'])
            if account and (data.password == account['password']):
                is_valid_password = True

        if not is_valid_password:
            raise exceptions.CustomException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect account or password",
                error_code=constants.ErrorCode.UNAUTHORIZED
            )

        # Generate token
        return self._generate_tokens(
            user_id=user['_id'],
            role=user.get('role', 'user'),
            email=user['email']
        )

    """
    Refresh Token
    """
    async def refresh_token(self, refresh_token: str) -> TokenResponse:
        # Verify the validity of the token
        payload = security.jwt_service.verify_token(refresh_token)
        if not payload or payload.get('type') != 'refresh':
            raise exceptions.CustomException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired token",
                error_code=constants.ErrorCode.UNAUTHORIZED,
            )

        try:
            user_id = ObjectId(payload['sub'])
        except InvalidId:
            raise exceptions.CustomException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token format",
                error_code=constants.ErrorCode.UNAUTHORIZED,
            )

        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise exceptions.CustomException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="The account no longer exists",
                error_code=constants.ErrorCode.UNAUTHORIZED,
            )

        # Generate new token
        return self._generate_tokens(
            user_id=user['_id'],
            role=user.get('role', 'user'),
            email=user['email']
        )

    """
    Google
    """
    async def process_google_login(self, user_info: dict) -> TokenResponse:
        google_email = user_info.get('email')
        google_sub = user_info.get('sub')
        google_name = user_info.get('name')
        google_picture = user_info.get('picture')

        now_timestamp = datetime.now(timezone.utc).timestamp()

        # Check the user in the system
        existing_user = await self.repo.get_user_by_login_identifier(google_email)

        if not existing_user:
            new_user_doc = {
                "username": google_name,
                "email": google_email,
                "gender": None,
                "date": None,
                "number": None,
                "fullName": google_name,
                "role": "user",
                "avatar": google_picture,
                "is_verified": True,
                "created_at": now_timestamp
            }

            user_id = await self.repo.create_user(new_user_doc)
            
            await self.repo.create_linked_account({
                'user_id': user_id,
                'provider': 'google',
                'provider_id': google_sub,
                'created_at': now_timestamp
            })

            return self._generate_tokens(
                user_id,
                "user",
                google_email
            )

        # The user already exists
        user_id = existing_user['_id']
        role = existing_user.get('role', 'user')

        linked_acc = await self.repo.get_linked_account(user_id, 'google')

        if linked_acc:
            return self._generate_tokens(
                user_id,
                role,
                google_email
            )

        await self.repo.create_linked_account({
            'user_id': user_id,
            'provider': 'google',
            'provider_id': google_sub,
            'created_at': now_timestamp
        })

        update_data = {}
        if not existing_user.get('avatar'):
            update_data['avatar'] = google_picture
        if not existing_user.get('is_verified'):
            update_data['is_verified'] = True

        if update_data:
            await self.repo.update_user(user_id, update_data)

        return self._generate_tokens(
            user_id,
            role,
            google_email
        )

    """
    Verify User Accounts Via Email
    """
    async def verify_email_and_login(self, token: str) -> TokenResponse:
        payload = security.jwt_service.verify_token(token)
        if not payload or payload.get('type') != 'verification':
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="The verification code is invalid or has expired",
                error_code=constants.ErrorCode.BAD_REQUEST
            )

        try:
            user_id = ObjectId(payload['sub'])
        except InvalidId:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid authentication code format",
                error_code=constants.ErrorCode.BAD_REQUEST
            )

        # Get user information
        user = await self.repo.get_user_by_id(user_id)
        if not user:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Account not found",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        if user.get('is_verified'):
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Your account has been previously verified. Please log in",
                error_code=constants.ErrorCode.BAD_REQUEST
            )

        await self.repo.update_user(user_id, {'is_verified': True})

        return self._generate_tokens(
            user_id=user['_id'],
            role=user.get('role', 'user'),
            email=user['email']
        )

    """
    Resend Verification Email
    """
    async def resend_verification_email(self, email: str, background_tasks: BackgroundTasks) -> None:
        user = await self.repo.get_user_by_email(email)
        if not user:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account found with this email address",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        if user.get('is_verified', True):
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This account has been previously verified",
                error_code=constants.ErrorCode.BAD_REQUEST
            )

        self._generate_token_and_qr_code(user['_id'], email, background_tasks)

    """
    Request New OTP
    """
    async def request_new_otp_verification(self, email: str, background_tasks: BackgroundTasks) -> None:
        user = await self.repo.get_user_by_email(email)
        if not user:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account found with this email address",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        if user.get('is_verified', True):
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="This account has been previously verified",
                error_code=constants.ErrorCode.BAD_REQUEST
            )

        otp_code = utils.generate_otp(6)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        await self.repo.update_user_otp(user['_id'], otp_code, expires_at.timestamp())

        background_tasks.add_task(
            email_service.send_otp, 
            email_to=user['email'], 
            otp=otp_code
        )

    """
    Forgot Password
    """
    async def process_forgot_password(self, email: str, background_tasks: BackgroundTasks) -> None:
        user = await self.repo.get_user_by_email(email)

        if not user:
            return

        if not user.get('is_verified', True):
            raise exceptions.CustomException(
                status_code=status.HTTP_403_FORBIDDEN, 
                detail="Your account has not been verified. Please verify your email first",
                error_code=constants.ErrorCode.FORBIDDEN
            )

        otp_code = utils.generate_otp(6)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=5)

        await self.repo.update_user_otp(user['_id'], otp_code, expires_at.timestamp())

        background_tasks.add_task(
            email_service.send_otp,
            email_to=user['email'],
            otp=otp_code
        )

    """
    Verify OTP To Reset Password
    """
    async def verify_otp_for_password_reset(self, email: str, otp: str) -> str:
        user = await self.repo.get_user_by_email(email)
        if not user:
            raise exceptions.CustomException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="No account found with this email address",
                error_code=constants.ErrorCode.NOT_FOUND
            )

        stored_otp = user.get("otp")
        otp_expiry = user.get("createAtOTP")

        if not stored_otp or stored_otp != otp:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="Invalid OTP code",
                error_code=constants.ErrorCode.BAD_REQUEST
            )

        now = datetime.now(timezone.utc).timestamp()
        if now > otp_expiry:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST, 
                detail="The OTP code has expired. Please request a new code",
                error_code=constants.ErrorCode.BAD_REQUEST
            )

        await self.repo.clear_user_otp(user['_id'])

        reset_token = security.jwt_service.create_reset_token({
            'sub': str(user['_id']),
            'email': email
        })

        return reset_token

    """
    Reset Password With Token
    """
    async def reset_password_with_token(self, payload: ResetPasswordRequest) -> None:
        if payload.new_password != payload.confirm_password:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="The verification password does not match. Please try again",
                error_code=constants.ErrorCode.BAD_REQUEST
            )

        decoded = security.jwt_service.verify_token(payload.token)

        if not decoded or decoded.get('type') != 'reset':
            raise exceptions.CustomException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="The verification code is invalid or has expired",
                error_code=constants.ErrorCode.UNAUTHORIZED
            )

        try:
            user_id = ObjectId(decoded['sub'])
        except InvalidId:
            raise exceptions.CustomException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect authentication code format",
                error_code=constants.ErrorCode.BAD_REQUEST
            )

        await self.repo.update_password(user_id, payload.new_password)
