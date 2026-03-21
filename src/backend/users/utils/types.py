from typing import Annotated
from pydantic import AfterValidator, SecretStr
import re


def validate_password_strength(v: SecretStr) -> SecretStr:
    pw = v.get_secret_value()
    regex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
    if not re.match(regex, pw):
        raise ValueError('Weak password: Must contain at least 1 uppercase, 1 lowercase, 1 number, and 1 special character')
    return v


StrongPassword = Annotated[SecretStr, AfterValidator(validate_password_strength)]
