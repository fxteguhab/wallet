from openerp.osv import osv, fields
from datetime import date

class wallet_owner(osv.osv):
	
	_name = 'wallet.owner'
	_description = 'Wallet - Owner'
	
	_columns = {
		'name': fields.char('Name', required=True),
		'ref_model': fields.char('Ref. Model'),
		'ref_id' : fields.integer('Ref. ID'),
		'balance_amount': fields.float('Balance'), 
		'owner_group_id': fields.many2one('wallet.owner.group','Group'), 
	}
	
# ============ METHOD PUBLIC =============== 

	"""
		Method untuk menghitung ulang balance setelah ada transaksi
	"""
	def calculate_balance(self, cr, uid, owner_id, amount, inc_dec):
		if not owner_id or not amount or not inc_dec: return False
		balance_amount = self.read(cr, uid, owner_id, ['balance_amount'])['balance_amount']
	# 1 = increase, 2 = decrease
		if inc_dec == 1: 
			balance_amount += float(amount)
		elif inc_dec == 2:
			balance_amount -= float(amount)
	# write lagi ke datanya
		result = self.write(cr, uid, owner_id, {
				'balance_amount': balance_amount
			})
		return result
	
	"""
		Method untuk mengambil id ownernya
	"""
	def get_owner(self, cr, uid, account_id, account_model):
		if not account_id or not account_model: return False
	# cari di model owner, apakah ada owner dengan ref id dan ref model tersebut
		owner_obj = self.pool.get('wallet.owner')
		owner_data = owner_obj.search(cr, uid, [('ref_model','=',account_model),('ref_id','=',account_id)])
		if len(owner_data) == 0: return False
		return owner_data[0]
	
	
wallet_owner()