from cryptoadvance.specter.managers.service_manager import ServiceManager


# Collecting template and static files from the different services in src/cryptoadvance/specter/services
service_template_datas = [
    (service_dir, "templates")
    for service_dir in ServiceManager.get_service_x_dirs("templates")
]
service_static_datas = [
    (service_dir, "static")
    for service_dir in ServiceManager.get_service_x_dirs("static")
]

# Collect Packages from the services, including service- and controller-classes
service_packages = ServiceManager.get_service_packages()


datas = [*service_template_datas, *service_static_datas]

hiddenimports = [*service_packages]
