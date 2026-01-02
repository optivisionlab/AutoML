# Standard libraries
import os
from datetime import datetime, timezone
from bson import ObjectId


# Third party libraries
from fastapi import APIRouter, HTTPException, Depends, status, Response, Cookie
from pymongo.asynchronous.database import AsyncDatabase
from dotenv import load_dotenv
from fastapi.security import OAuth2PasswordBearer
from authlib.integrations.starlette_client import OAuth
from starlette.requests import Request
from fastapi.responses import RedirectResponse


# Local modules
from users.utils.authentication import jwt_service
from users.utils.security import HashHelper
from users.schema import UserLoginRequest, UserRegisterRequest, UserResponse, Token
from database.database import get_db


# Load .env file
load_dotenv()


router = APIRouter(tags=["Authentication"])


@router.post("/signup", response_model=UserResponse)
async def register(user_data: UserRegisterRequest, db: AsyncDatabase = Depends(get_db)) -> UserResponse:
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
        "password": user_data.password.get_secret_value(), # HashHelper.get_password_hash(user_data.password)
        "created_at": datetime.now(timezone.utc).timestamp()
    }

    await db.linked_accounts.insert_one(linked_account_doc)

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

    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Wrong login information",
            headers={"WWW-Authenticate": "Bearer"}
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

    refresh_expire_days = int(os.getenv('REFRESH_EXPIRE', 1))
    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        httponly=True,
        max_age=refresh_expire_days * 24 * 60 * 60,
        samesite='lax',
        secure=False
    )

    return Token(access_token=access_token, token_type='bearer')


@router.post('/refresh', response_model=Token)
async def refresh_token(response: Response, refresh_token: str | None = Cookie(None), db: AsyncDatabase = Depends(get_db)) -> Token:
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
    
    user = await db.tbl_user.find_one({'_id': ObjectId(payload.get('sub'))})
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

    return Token(access_token=new_access_token, token_type='bearer')


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
    redirect_response = RedirectResponse(url=f"{frontend_url}?access_token={access_token}&login_success=true")

    refresh_expire_days = int(os.getenv('REFRESH_EXPIRE', 1))
    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        httponly=True,
        max_age=refresh_expire_days * 24 * 60 * 60,
        samesite='lax',
        secure=False
    )

    return redirect_response