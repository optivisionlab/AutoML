# Standard Libraries
import secrets


def generate_otp(length: int = 6) -> str:
    """
    Create a OTP
    """
    return "".join(
        secrets.choice("0123456789") for _ in range(length)
    )
