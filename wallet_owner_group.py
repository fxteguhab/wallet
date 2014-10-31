from openerp.osv import osv, fields
from datetime import date

class wallet_owner_group(osv.osv):
	
	_name = 'wallet.owner.group'
	_description = 'Wallet - Owner Group'
	
	_columns = {
		'name': fields.char('Name', required=True),
		'balance_min': fields.float('Balance Min.'),
		'balance_overdraft' : fields.float('Balance Overdraft'),
	}
	