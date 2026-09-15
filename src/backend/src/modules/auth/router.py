# Third-party Libraries
from fastapi.responses import RedirectResponse
from authlib.integrations.starlette_client import OAuth
from pymongo.asynchronous.database import AsyncDatabase
from fastapi import Depends, BackgroundTasks, APIRouter, Response, Request, status

# Local Libraries
from src.shared.constants import ErrorCode
from src.config.database import get_db
from src.config.settings import settings
from src.core.responses import BaseResponse
from src.core.exceptions import CustomException
from src.core.cookies import refresh_token_cookie
from src.core.dependencies import get_current_user
from src.modules.auth.service import AuthService
from src.modules.auth.repository import AuthRepository
from src.modules.auth.schemas import UserRegisterRequest, UserResponse, UserLoginRequest, TokenResponse, RefreshRequest, VerifyEmailRequest, ResendEmailRequest, ForgotPasswordRequest, VerifyOtpRequest, ResetPasswordRequest


# Router
router = APIRouter(prefix="/auth", tags=["Authentication"])

def get_auth_service(db: AsyncDatabase = Depends(get_db)) -> AuthService:
    return AuthService(AuthRepository(db))


@router.post("/signup", response_model=BaseResponse[UserResponse])
async def register(
    user_data: UserRegisterRequest,
    background_tasks: BackgroundTasks,
    service: AuthService = Depends(get_auth_service)
):
    created_user = await service.register(user_data, background_tasks)

    return BaseResponse(
        message="Registration successful",
        data=created_user
    )


@router.post("/login", response_model=BaseResponse[TokenResponse])
async def login(
    request: UserLoginRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service)
):
    tokens = await service.login(request)

    refresh_token_cookie.set_token(response, tokens.refresh_token)

    return BaseResponse(
        message="Log in successfully",
        data=tokens
    )


@router.post("/refresh", response_model=BaseResponse[TokenResponse])
async def refresh_token(
    request: RefreshRequest,
    response: Response,
    service: AuthService = Depends(get_auth_service)
):
    tokens = await service.refresh_token(request.refresh_token)

    refresh_token_cookie.set_token(response, tokens.refresh_token)

    return BaseResponse(
        message="Token refresh successful",
        data=tokens
    )


@router.get("/me", response_model=BaseResponse[UserResponse])
async def me(
    current_user: dict = Depends(get_current_user)
):
    return BaseResponse(
        message="Account information retrieved successfully",
        data=current_user
    )


@router.post("/logout", dependencies=[Depends(get_current_user)], response_model=BaseResponse[None])
async def logout(
    response: Response, 
):
    refresh_token_cookie.delete_token(response)

    return BaseResponse(
        message="Signed out successfully",
        data=None
    )


# Initialize OAuth
oauth = OAuth()
oauth.register(
    name='google',
    client_id=settings.GOOGLE.CLIENT_ID,
    client_secret=settings.GOOGLE.CLIENT_SECRET,
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'}
)

@router.post("/google")
async def google_login(request: Request):
    redirect_uri = f"{settings.REDIRECT_URI}/api/v1/auth/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)

@router.get('/google/callback')
async def google_callback(
    request: Request,
    response: Response,
    service: AuthService = Depends(get_auth_service)
):
    token = await oauth.google.authorize_access_token(request)
    user_info = token.get('userinfo')

    if not user_info:
        raise CustomException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unable to retrieve information from Google",
            error_code=ErrorCode.BAD_REQUEST
        )

    tokens = await service.process_google_login(user_info)

    frontend_url = settings.FRONTEND_URL
    redirect_url = f"{frontend_url}/google?access_token={tokens.access_token}&refresh_token={tokens.refresh_token}&login_success=true"

    redirect_response = RedirectResponse(url=redirect_url)

    refresh_token_cookie.set_token(response, tokens.refresh_token)

    return redirect_response


@router.post("/verifications", response_model=BaseResponse[TokenResponse])
async def verify_user_email(
    request: VerifyEmailRequest, 
    response: Response,
    service: AuthService = Depends(get_auth_service)
):
    tokens = await service.verify_email_and_login(request.token)

    refresh_token_cookie.set_token(response, tokens.refresh_token)

    return BaseResponse(
        message="Account verification successful",
        data=tokens
    )


@router.post("/token/verifications", response_model=BaseResponse[None])
async def request_new_verification(
    request: ResendEmailRequest,
    background_tasks: BackgroundTasks,
    service: AuthService = Depends(get_auth_service)
):
    await service.resend_verification_email(request.email, background_tasks)

    return BaseResponse(
        message="The new verification link has been sent. Please check your inbox",
        data=None
    )


@router.post("/otp/verifications", response_model=BaseResponse[None])
async def request_new_otp_verification(
    request: ResendEmailRequest,
    background_tasks: BackgroundTasks,
    service: AuthService = Depends(get_auth_service)
):
    await service.request_new_otp_verification(request.email, background_tasks)

    return BaseResponse(
        message="A new OTP code has been sent. Please check your inbox",
        data=None
    )


@router.post("/forgot-password", response_model=BaseResponse[None])
async def forgot_password(
    request: ForgotPasswordRequest,
    background_tasks: BackgroundTasks, 
    service: AuthService = Depends(get_auth_service)
):
    await service.process_forgot_password(request.email, background_tasks)

    return BaseResponse(
        message="If this email address is already registered, you will receive an OTP code shortly",
        data=None
    )


@router.post("/verify-otp", response_model=BaseResponse[dict])
async def verify_otp(
    request: VerifyOtpRequest, 
    service: AuthService = Depends(get_auth_service)
):
    reset_token = await service.verify_otp_for_password_reset(request.email, request.otp)

    return BaseResponse(
        message="OTP verification successful",
        data={"reset_token": reset_token}
    )


@router.post("/reset-password", response_model=BaseResponse[None])
async def reset_password(
    payload: ResetPasswordRequest, 
    service: AuthService = Depends(get_auth_service)
):
    await service.reset_password_with_token(payload)

    return BaseResponse(
        message="Password update successful. You can log in with your new password",
        data=None
    )
