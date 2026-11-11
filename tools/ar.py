"""Arabic strings of ledgerx_sales. SALES holds strings written for this app; FALLBACK is Fleet's
dictionary, used only for generic words (Customer, Company...) that are identical."""
from ar_fleet_base import AR as FALLBACK  # noqa: E402

SALES = {}
try:
	from ar_sales import SALES as _S  # noqa: E402

	SALES.update(_S)
except ImportError:
	pass

AR = dict(SALES)
