'use client'

import { useSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useEffect } from 'react'
import LoginForm from '@/app/(auth)/login/LoginForm'

const LoginPage = () => {
  const { data: session, status } = useSession()
  const router = useRouter()

  useEffect(() => {
    if (status === 'authenticated') {
      router.replace('/') 
    }
  }, [status])

  if (status === 'loading') {
    return null
  }

  return (
    <div>
      <LoginForm />
    </div>
  )
}

export default LoginPage
