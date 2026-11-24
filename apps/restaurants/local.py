import re

from apps.auth.models import Account
from apps.extensions import db
from apps.restaurants.models import RestaurantLocation


def local_place_id(account_id):
    return f"local-store-{account_id}"


def local_restaurant(place_id):
    match = re.fullmatch(r"local-store-([1-9][0-9]{0,18})", place_id)
    if not match:
        return None
    restaurant_id = int(match.group(1))
    if restaurant_id > 2**63 - 1:
        return None
    account = db.session.get(Account, restaurant_id)
    location = db.session.get(RestaurantLocation, restaurant_id)
    if account is None or account.account_type != "restaurant" or location is None:
        return None
    return account
