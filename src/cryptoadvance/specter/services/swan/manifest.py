import datetime
import pytz
from ..service import Service, devstatus_beta


class SwanService(Service):
    id = "swan"
    name = "Swan"
    icon = "img/swan_icon.svg"
    logo = "img/swan_logo.svg"
    desc = "Auto-withdraw to your Specter wallet"
    has_blueprint = True
    devstatus = devstatus_beta

    # TODO: As more Services are integrated, we'll want more robust categorization and sorting logic
    sort_priority = 1


    @property
    def is_access_token_valid(self):
        api_data = self.get_current_user_api_data()
        if not api_data or not api_data.get("expires"):
            return False
        
        return datetime.fromtimestamp(api_data["expires"]) > datetime.datetime.now(tz=pytz.utc)
