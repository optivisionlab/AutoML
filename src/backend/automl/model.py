from typing import List, Dict, Union, Any

from pydantic import BaseModel


class Item(BaseModel):
    data: List[Dict[str, Union[float, int, str]]]
    config: Dict[str, Any]