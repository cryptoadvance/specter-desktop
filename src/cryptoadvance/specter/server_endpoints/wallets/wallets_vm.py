from dataclasses import dataclass


@dataclass
class WalletsOverviewVm:
    """An object to control what is being displayed at the wallet_overview endpoint
    If you set the different attributes, you can modify the behaviour.
    e.g. setting the about_redirect to url_for(...) will cause a redirect

    Check the wallets_overview.jinja template to understand exact usage
    """

    wallets_overview_redirect: str = None
    header_and_summary_include: str = "wallet/overview/header_and_summary.jinja"
    balance_overview_include: str = "wallet/overview/balance_overview.jinja"
    tx_table_include: str = "wallet/overview/tx_table.jinja"
