from openerp.osv import osv, fields
from datetime import date

class wallet_master_trx(osv.osv):
	
	_name = 'wallet.master.trx'
	_description = 'Wallet - Master Transaction'
	
	_columns = {
		'name': fields.char('Name', required=True),
		'mnemonic': fields.char('Mnemonic', required=True),
		'need_approve' : fields.boolean('Need approve?'),
		'inc_dec': fields.selection([
			('increase','Increase'),
			('decrease','Decrease')
		], 'Increase/Decrease?'), 
		'journal_debit_acc_id' : fields.many2one('account.account','Journal Debit'),
		'journal_credit_acc_id' : fields.many2one('account.account','Journal Credit'),
		'journal_debit_flag' : fields.boolean('Positive Debit?'), # True = positif, False = negatif
		'journal_credit_flag' : fields.boolean('Positive Credit?'),
	}
	
	
wallet_master_trx()