# Standard libraries
import os
from datetime import datetime, timezone
from bson import ObjectId
import asyncio


# Third party libraries
from fastapi import APIRouter, HTTPException, Depends, status, Response, BackgroundTasks
from pymongo.asynchronous.database import AsyncDatabase
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordBearer
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
from fastapi.responses import RedirectResponse
from pydantic import EmailStr


# Local modules
from users.utils.authentication import jwt_service
from users.utils.security import HashHelper
from users.utils.email_service import email_service
from users.schema import UserLoginRequest, UserRegisterRequest, UserResponse, Token, RefreshRequest, ResendEmailRequest, VerifyEmailRequest, ResetPasswordRequest, VerifyOtp
from database.database import get_db
from users.engine import handle_send_otp


# Load .env file
load_dotenv()


router = APIRouter(tags=["Authentication"])


@router.post("/signup", response_model=UserResponse)
async def register(user_data: UserRegisterRequest, background_tasks: BackgroundTasks, db: AsyncDatabase = Depends(get_db)) -> UserResponse:
    # Check email và username
    if await db.tbl_User.find_one({
        "$or": [
            {"email": user_data.email},
            {"username": user_data.username}
        ]
    }):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Username or Email already registed")
    
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
        "created_at": datetime.now(timezone.utc).timestamp()
    }

    user_insert_result = await db.tbl_User.insert_one(new_user_doc)
    user_id = user_insert_result.inserted_id

    linked_account_doc = {
        "user_id": user_id,
        "provider": "local",
        "provider_id": user_data.email,
        "password": user_data.password, # HashHelper.get_password_hash(user_data.password)
        "created_at": datetime.now(timezone.utc).timestamp()
    }

    await db.linked_accounts.insert_one(linked_account_doc)

    verification_token = jwt_service.create_verification_token({
        'sub': str(user_id),
        'email': user_data.email
    })

    # QR code
    verify_link = email_service.get_verify_link(verification_token)
    qr_base64 = email_service.generate_qr_base64(verify_link)

    # Offload email sending to a background worker
    background_tasks.add_task(
        email_service.send_verification_email,
        user_data.email,
        verification_token,
        qr_base64
    )

    created_user = await db.tbl_User.find_one({'_id': user_id})
    created_user['_id'] = str(created_user['_id'])

    return created_user


@router.post("/login", response_model=Token)
async def login(user_login: UserLoginRequest, response: Response, db: AsyncDatabase = Depends(get_db)) -> Token:
    user = await db.tbl_User.find_one({
        "$or": [
            {"email": user_login.username},
            {"username": user_login.username}
        ]
    })

    invalid_credentials_exception = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid username or password",
        headers={"WWW-Authenticate": "Bearer"}
    )

    if not user:
        raise invalid_credentials_exception

    if not user.get('is_verified', True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not verified. Please check your email to verify your account."
        )

    if user.get('password') and user_login.password != user['password']:
        raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect login information",
                headers={"WWW-Authenticate": "Bearer"}
            )
    elif not user.get('password'):
        account = await db.linked_accounts.find_one({
            'user_id': user['_id'],
            'provider': 'local'
        })

        if not account or not (user_login.password == account['password']): # HashHelper.verify_password(user_login.password, account['password'])
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Incorrect login information",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
    access_token = jwt_service.create_access_token({
        'sub': str(user['_id']),
        'role': user.get('role', 'user'),
        'email': user['email']
    })

    refresh_token = jwt_service.create_refresh_token({
        'sub': str(user['_id'])
    })

    return Token(access_token=access_token, refresh_token=refresh_token, token_type='bearer')


@router.post('/refresh', response_model=Token)
async def refresh_token(response: Response, refresh_request: RefreshRequest, db: AsyncDatabase = Depends(get_db)) -> Token:
    refresh_token = refresh_request.refresh_token

    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing",
            headers={"WWW-Authenticate": "Bearer"}
        )

    payload = jwt_service.verify_token(refresh_token)
    if not payload or payload.get('type') != 'refresh':
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    
    user = await db.tbl_User.find_one({'_id': ObjectId(payload.get('sub'))})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User no longer exists",
        )
    
    new_access_token = jwt_service.create_access_token({
        'sub': str(user['_id']),
        'role': user.get('role', 'user'),
        'email': user['email']
    })

    new_refresh_token = jwt_service.create_refresh_token({
        'sub': str(user['_id'])
    })

    refresh_expire_days = int(os.getenv('REFRESH_EXPIRE', 1))
    response.set_cookie(
        key='refresh_token',
        value=new_refresh_token,
        httponly=True,
        max_age=refresh_expire_days * 24 * 60 * 60,
        samesite='lax',
        secure=False
    )

    return Token(access_token=new_access_token, refresh_token=new_refresh_token, token_type='bearer')


oauth2_scheme = OAuth2PasswordBearer(tokenUrl='/login')

async def get_current_user(token: str = Depends(oauth2_scheme), db: AsyncDatabase = Depends(get_db)):
    payload = jwt_service.verify_token(token)

    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )
    
    user = await db.tbl_User.find_one({'_id': ObjectId(payload['sub'])})
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    
    user['_id'] = str(user['_id'])
    return user


@router.get('/me', response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)) -> UserResponse:
    return current_user


@router.post('/logout')
async def logout(response: Response, current_user: dict = Depends(get_current_user)):
    response.delete_cookie(
        key='refresh_token',
        httponly=True,
        samesite='lax',
        secure=False
    )

    return {'message': 'Logged out successfully'}


oauth = OAuth()

oauth.register(
    name = 'google',
    client_id = os.getenv('GOOGLE_CLIENT_ID'),
    client_secret = os.getenv('GOOGLE_CLIENT_SECRET'),
    server_metadata_url = 'https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs = {
        'scope': 'openid email profile'
    }
)

@router.get('/google/login')
async def google_login(request: Request):
    redirect_uri = f"{os.getenv('REDIRECT_URI')}/google/callback"
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get('/google/callback')
async def google_callback(request: Request, response: Response, db: AsyncDatabase = Depends(get_db)):
    token = await oauth.google.authorize_access_token(request)

    user_info = token.get('userinfo')
    if not user_info:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Failed to get user info from Google",
        )
    
    google_email = user_info.get('email')
    google_sub = user_info.get('sub')
    google_name = user_info.get('name')
    google_picture = user_info.get('picture')

    existing_user = await db.tbl_User.find_one({'email': google_email})

    user_id = None
    role = 'user'

    if existing_user:
        user_id = existing_user['_id']
        role = existing_user.get('role', 'user')

        linked_acc = await db.linked_accounts.find_one({
            'user_id': user_id,
            'provider': 'google'
        })

        if not linked_acc:
            await db.linked_accounts.insert_one({
                'user_id': user_id,
                'provider': 'google',
                'provider_id': google_sub,
                'created_at': datetime.now(timezone.utc).timestamp()
            })

            if not existing_user.get('avatar'):
                await db.tbl_User.update_one(
                    {'_id': user_id},
                    {'$set': {'avatar': google_picture}}
                )
            
            if not existing_user.get('is_verified'):
                await db.tbl_User.update_one(
                    {'_id': user_id},
                    {'$set': {'is_verified': True}}
                )
    else:
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
            "created_at": datetime.now(timezone.utc).timestamp()
        }
        insert_result = await db.tbl_User.insert_one(new_user_doc)
        user_id = insert_result.inserted_id

        await db.linked_accounts.insert_one({
            'user_id': user_id,
            'provider': 'google',
            'provider_id': google_sub,
            'created_at': datetime.now(timezone.utc).timestamp()
        })
    
    access_token = jwt_service.create_access_token({
        'sub': str(user_id),
        'role': role,
        'email': google_email
    })

    refresh_token = jwt_service.create_refresh_token({
        'sub': str(user_id)
    })

    frontend_url = os.getenv('FRONTEND_URL', 'http://localhost:8000/login')
    redirect_response = RedirectResponse(url=f"{frontend_url}/google?access_token={access_token}&refresh_token={refresh_token}&login_success=true")

    return redirect_response


@router.post('/auth/verifications', response_model=Token)
async def verify_user_email(request: VerifyEmailRequest, db: AsyncDatabase = Depends(get_db)) -> Token:
    payload = jwt_service.verify_token(request.token)
    if not payload or payload.get('type') != 'verification':
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="Invalid or expired verification code"
        )

    user_id = payload.get('sub')

    user = await db.tbl_User.find_one({'_id': ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    if user.get('is_verified'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail="This account has already been verified. Please log in with your password"
        )

    await db.tbl_User.update_one(
        {'_id': ObjectId(user_id)},
        {'$set': {'is_verified': True}}
    )

    access_token = jwt_service.create_access_token({
        'sub': str(user['_id']),
        'role': user.get('role', 'user'),
        'email': user['email']
    })

    refresh_token = jwt_service.create_refresh_token({
        'sub': str(user['_id'])
    })

    return Token(access_token=access_token, refresh_token=refresh_token, token_type='bearer')


@router.post("/auth/token/verifications")
async def request_new_verification(
    request: ResendEmailRequest,
    background_tasks: BackgroundTasks,
    db: AsyncDatabase = Depends(get_db)
):
    user = await db.tbl_User.find_one({"email": request.email})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email"
        )

    if user.get('is_verified', True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account has already been verified"
        )

    verification_token = jwt_service.create_verification_token({
        'sub': str(user['_id']),
        'email': user['email']
    })
    background_tasks.add_task(email_service.send_verification_email, user['email'], verification_token)

    return {"detail": "A new verification link has been sent. Please check your email"}


@router.post("/auth/otp/verifications")
async def request_new_verification(
    request: ResendEmailRequest,
    background_tasks: BackgroundTasks,
    db: AsyncDatabase = Depends(get_db)
):
    user = await db.tbl_User.find_one({"email": request.email})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No account found with this email"
        )

    if user.get('is_verified', True):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account has already been verified"
        )
    
    await db.tbl_User.update_one(
        {"_id": user["_id"]},
        {"$unset": {"otp": "", "createAtOTP": ""}}
    )

    background_tasks.add_task(handle_send_otp, user['email'])

    return {"detail": "A new otp has been sent. Please check your email"}


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
async def forgot_password(
    email: EmailStr,
    background_tasks: BackgroundTasks, 
    db: AsyncDatabase = Depends(get_db)
):
    user = await db.tbl_User.find_one({"email": email})

    if not user:
        return {
            "status": "success",
            "message": "If this email is registered, you will receive an OTP shortly."
        }

    if not user.get('is_verified', True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, 
            detail="Account is not verified. Please verify your email first."
        )

    background_tasks.add_task(handle_send_otp, email, db)

    return {
        "status": "success",
        "message": "A password reset OTP has been sent to your email address."
    }


@router.post("/auth/verify-otp", status_code=status.HTTP_200_OK)
async def reset_password(
    payload: VerifyOtp, 
    db: AsyncDatabase = Depends(get_db)
):
    user = await db.tbl_User.find_one({"email": payload.email})
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match. Please try again."
        )

    stored_otp = user.get("otp")
    otp_expiry = user.get("createAtOTP")

    if not stored_otp or stored_otp != payload.otp:
        raise HTTPException(status_code=400, detail="Invalid OTP code.")
    
    now = datetime.now(timezone.utc).timestamp()
    if now - otp_expiry > 60:
        raise HTTPException(status_code=400, detail="OTP code has expired.")

    await db.tbl_User.update_one(
        {"_id": user["_id"]},
        {"$unset": {"otp": "", "createAtOTP": ""}}
    )

    password = None

    if user.get('password'):
        password = user['password']
    else:
        account = await db.linked_accounts.find_one({
            'user_id': user['_id'],
            'provider': 'local'
        })
        password = account['password']

    return {
        "password": password
    }


@router.post("/reset-password", status_code=status.HTTP_200_OK)
async def reset_password(
    payload: ResetPasswordRequest, 
    db: AsyncDatabase = Depends(get_db)
):
    if payload.new_password != payload.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Passwords do not match. Please try again"
        )

    user = await db.tbl_User.find_one({"email": payload.email})

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Not found account"
        )
    
    is_authenticated = False
    
    if user.get('password'):
        if payload.password == user['password']:
            is_authenticated = True

    if not is_authenticated:
        account = await db.linked_accounts.find_one({
            'user_id': user['_id'],
            'provider': 'local'
        })
        if account and payload.password == account.get('password'):
            is_authenticated = True

    if not is_authenticated:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Password not correct"
        )
    
    update_user_task = db.tbl_User.update_one(
        {"_id": user["_id"]},
        {"$set": {"password": payload.new_password}}
    )

    update_account_task = db.linked_accounts.update_one(
        {
            "user_id": user["_id"], 
            "provider": "local"
        },
        {"$set": {"password": payload.new_password}},
        upsert=True 
    )

    await asyncio.gather(update_user_task, update_account_task)

    return {
        "status": "success",
        "message": "Password updated successfully. You can now login with your new password."
    }
