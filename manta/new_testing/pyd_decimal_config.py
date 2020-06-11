from decimal import Decimal
from typing import Dict, Any, Type, get_type_hints


class DecimalConfig:
    json_encoders = {Decimal: str}

    @staticmethod
    def schema_extra(schema: Dict[str, Any], model: Type["OrderRequest"]) -> None:
        decimals = {k: v for (k, v) in get_type_hints(model).items() if v is Decimal}
        for (k, v) in decimals.items():
            schema["properties"][k]["type"] = "string"
