import logging
from cryptoadvance.specter.managers.service_manager import ExtensionManager

logger = logging.getLogger(__name__)

# Collecting template and static files from the different services in src/cryptoadvance/specter/services
service_template_datas = [
    (service_dir, "templates")
    for service_dir in ExtensionManager.get_service_x_dirs("templates")
]
service_static_datas = [
    (service_dir, "static")
    for service_dir in ExtensionManager.get_service_x_dirs("static")
]

# Collect Packages from the services, including service- and controller-classes
service_packages = ExtensionManager.get_service_packages()


datas = [*service_template_datas, *service_static_datas]

hiddenimports = [*service_packages]

logger.info(f"specter-hook datas: {datas}")
logger.info(f"specter-hook hiddenimports: {hiddenimports}")
