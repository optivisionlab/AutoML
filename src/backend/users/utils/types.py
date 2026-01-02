from typing import Annotated
from pydantic import AfterValidator, SecretStr
import re


def validate_password_strength(v: SecretStr) -> SecretStr:
    pw = v.get_secret_value()
    regex = r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&])[A-Za-z\d@$!%*?&]{8,}$'
    if not re.match(regex, pw):
        raise ValueError('Password weak: Cần 1 hoa, 1 thường, 1 số, 1 ký tự đặc biệt')
    return v


StrongPassword = Annotated[SecretStr, AfterValidator(validate_password_strength)]
