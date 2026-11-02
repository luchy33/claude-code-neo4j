class FoodItemInUseError(Exception):
    """Raised when deleting a food item that existing orders refer to."""


class ImageError(Exception):
    """An image was rejected or could not be generated. The message is safe to show to the admin."""


class CartError(Exception):
    """A cart change was refused (e.g. below the minimum order). The message is safe to show to the customer."""
