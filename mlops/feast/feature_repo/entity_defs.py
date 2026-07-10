"""
Reusable entity definitions shared across feature views.
"""

from feast import Entity
from feast.types import Int64, String

customer = Entity(
    name="customer_id",
    join_keys=["customer_id"],
    description="Unique customer identifier",
    value_type=Int64,
)

product = Entity(
    name="product_id",
    join_keys=["product_id"],
    description="Unique product identifier",
    value_type=Int64,
)

region = Entity(
    name="region",
    join_keys=["region"],
    description="Geographic region code",
    value_type=String,
)
