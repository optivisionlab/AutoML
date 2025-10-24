from typing import List, Dict, Union

from pydantic import BaseModel


class Item(BaseModel):
    data: List[Dict[str, Union[float, int, str]]]
    config: Dict[str, Union[str, List[str], Dict[str, Dict[str, Union[str, Dict[str, List[Union[None, int, float, str]]]]]]]]