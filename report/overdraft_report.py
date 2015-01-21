from openerp.osv import osv, fields
from openerp import tools
from openerp.tools.translate import _

class wallet_overdraft_report(osv.osv):
	
	_name = 'wallet.overdraft.report'
	_description = 'Wallet Overdraft Report'
	_auto = False
	_rec_name = 'trx_date'
	
	_columns = {
		'trx_date': fields.date('Date', readonly=True),
		'wallet_owner_id': fields.many2one('wallet.owner', 'Wallet Owner'),
		'overdraft_qty': fields.integer('Overdraft'),
	}
	
	def init(self, cr):
		tools.drop_view_if_exists(cr, 'wallet_overdraft_report')
		cr.execute("""
			CREATE OR REPLACE VIEW wallet_overdraft_report AS (
				SELECT 
					trx.id,
					wallet_owner_id,
					trx_date::date AS trx_date,
					1 AS overdraft_qty 
				FROM 
					wallet_transaction trx, wallet_master_trx master_trx 
				WHERE 
					trx.trx_type_id = master_trx.id AND 
					master_trx.mnemonic = 'ASL' AND 
					state = 'approved' AND 
					is_overdraft = True 
			)
		""")
