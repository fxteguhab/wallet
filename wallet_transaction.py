from openerp.osv import osv, fields
from datetime import date

_TRX_STATE = [
	('approved','Approved'),
	('pending','Pending'),
	('rejected','Rejected'),
]

class wallet_transaction(osv.osv):
	
	_name = 'wallet.transaction'
	_description = 'Wallet - Master Transaction'
	
	_columns = {
		'name': fields.char('Name', required=True),
		'trx_type_id': fields.many2one('wallet.master.trx','Master Trx'),
		'wallet_owner_id': fields.many2one('wallet.owner','Wallet Owner'),
		'trx_date' : fields.date('Date'),
		'increase_amount': fields.float('Increase amount'), 
		'decrease_amount': fields.float('Decrease amount'), 
		'state': fields.selection(_TRX_STATE, 'State', select=True, readonly=True),
	}
	
# ============ METHOD PUBLIC =============== 
	
	"""
		Method untuk mencatat transaksi baru berdasarkan master transaksi. 
		
		Param: 
		- account_id : id account di model aslinya
		- account_model : nama model account
		- mnemonic : kode dari master transaksi
		- amount : jumlah yang akan dicatat
		
		Return: True bila berhasil, False bila gagal
	"""
	def post_transaction(self, cr, uid, name, trx_date, account_id, account_model, mnemonic, amount, owner_id=False):
		if not name or not mnemonic or not amount or ((not account_id or not account_model) or not owner_id): return False
	# cek owner dari account ini id nya apa
		if not owner_id:
			owner_obj = self.pool.get('wallet.owner')
			owner_id = owner_obj.get_owner(cr, uid, account_id, account_model)
		if not owner_id: return False
	# cari master trx berdasarkan mnemonicnya
		master_trx_obj = self.pool.get('wallet.master.trx')
		master_trx_ids = master_trx_obj.search(cr, uid, [('mnemonic','=',mnemonic)])
		if len(master_trx_ids) == 0: return False
	# kalau ada, insert datanya
		master_trx = master_trx_obj.browse(cr, uid, master_trx_ids[0])
		vals = {
			'name': name, 
			'trx_type_id': master_trx_ids[0],
			'wallet_owner_id': owner_id, 
			'trx_date': trx_date or date.today()
		}
	# kalau perlu diapprove dulu, statenya pending
		if master_trx['need_approve']: vals['state'] = 'pending'
		else: vals['state'] = 'approved'
	# ini increase/decrease?
		if master_trx['inc_dec'] == 1: vals['increase_amount'] = amount
		elif master_trx['inc_dec'] == 2: vals['decrease_amount'] = amount
	# create deh
		result = self.create(cr, uid, vals)
	# update balancenya
		owner_obj.calculate_balance(cr, uid, owner_id, amount, master_trx['inc_dec'])
		return result
	
	"""
		Method untuk mencatat transaksi baru secara manual, dengan data pada master transaksi bisa
		dikostumisasi. 
		
		Param: 
		- vals : semua data yang akan diolah
		
		Return: True bila berhasil, False bila gagal
	"""
	def post_manual_trx(self, cr, uid, vals):
		if not vals: return False
		approve = 2
	# cek butuh approve ga?
		if 'need_approve' in vals and vals['need_approve'] == True: approve = 'pending'
	# ada master trx nya ga?
		if 'trx_type_id' not in vals: vals['trx_type_id'] = False
	# cek ini increase/decrease account?
		if vals['inc_dec'] == 'increase': 
			result = self.increase_balance(cr, uid, 
				vals['name'], 
				vals['trx_date'], 
				vals['amount'], 
				vals['trx_type_id'],
				approve, 
				owner_id=vals['wallet_owner_id'])
		elif vals['inc_dec'] == 'decrease':
			result = self.decrease_balance(cr, uid, 
				vals['name'], 
				vals['trx_date'], 
				vals['amount'], 
				vals['trx_type_id'],
				approve, 
				owner_id=vals['wallet_owner_id'])
		return result
	
	def increase_balance(self, cr, uid, name, trx_date, amount, trx_type_id=False, approve='approved', 
											account_id=False, account_model=False, owner_id=False):
		owner_obj = self.pool.get('wallet.owner')
		if ((not account_id or not account_model) and not owner_id) or not amount: return False
	# cek owner dari account ini id nya apa
		if not owner_id:
			owner_id = owner_obj.get_owner(cr, uid, account_id, account_model)
		if not owner_id: return False
	# isi deh transaksinya
		result = self.create(cr, uid, {
			'name': name,
			'trx_type_id': trx_type_id,
			'wallet_owner_id': owner_id,
			'trx_date': trx_date or date.today(),
			'state': approve,
			'increase_amount': amount,
		})
	# update balance nya
		if approve == 2: owner_obj.calculate_balance(cr, uid, owner_id, amount, 1)
		return result
	
	def decrease_balance(self, cr, uid, name, trx_date, amount, trx_type_id=False, approve='approved', 
											account_id=False, account_model=False, owner_id=False):
		if ((not account_id or not account_model) and not owner_id) or not amount: return False
	# cek owner dari account ini id nya apa
		owner_obj = self.pool.get('wallet.owner')
		if not owner_id:
			owner_id = owner_obj.get_owner(cr, uid, account_id, account_model)
		if not owner_id: return False
	# isi deh transaksinya
		result = self.create(cr, uid, {
			'name': name,
			'trx_type_id': trx_type_id,
			'wallet_owner_id': owner_id,
			'trx_date': trx_date or date.today(),
			'state': approve,
			'decrease_amount': amount,
		})
	# update balance nya
		if approve == 2: owner_obj.calculate_balance(cr, uid, owner_id, amount, 2)
		return result
	
# =============== ACTION METHOD ========================
	def act_approve_trx(self, cr, uid, ids, context=None):
		trx_obj = self.pool.get('wallet.transaction')
		owner_obj = self.pool.get('wallet.owner')
	# update balance nya
		trx_data = trx_obj.browse(cr, uid, ids[0])
	# cek transaksinya increase/decrease?
		if trx_data.increase_amount:
			amount = trx_data.increase_amount
			inc_dec = 1
		elif trx_data.decrease_amount:
			amount = trx_data.decrease_amount
			inc_dec = 2
	# itung ulang balancenya
		owner_obj.calculate_balance(cr, uid, trx_data.wallet_owner_id.id, amount, inc_dec)
		return trx_obj.write(cr, uid, ids[0], { 
			'state': 'approved'
		})
	
	def act_reject_trx(self, cr, uid, ids, context=None):
		trx_obj = self.pool.get('wallet.transaction')
		return trx_obj.write(cr, uid, ids[0], { 
			'state': 'rejected'
		})
		return True
	
class wallet_manual_trx_memory(osv.osv_memory):
	
	_name = 'wallet.manual.trx.memory'
	_description = 'Wallet-Manual Transaction'
	
	_columns = {
		'trx_date' : fields.date('Date', required=True),
		'name' : fields.char('Name', required=True),
		'wallet_owner_id': fields.many2one('wallet.owner','Wallet Owner', required=True),
		'trx_type_id': fields.many2one('wallet.master.trx','Master Trx'),
		'need_approve' : fields.boolean('Need approve?'),
		'inc_dec': fields.selection([
			('increase','Increase'),
			('decrease','Decrease')
		], 'Increase/Decrease?', required=True),
		'journal_debit_acc_id' : fields.many2one('account.account','Journal Debit'),
		'journal_credit_acc_id' : fields.many2one('account.account','Journal Credit'),
		'journal_debit_flag' : fields.boolean('Positive Debit?'), # True = positif, False = negatif
		'journal_credit_flag' : fields.boolean('Positive Credit?'),
		'amount': fields.float('Amount', required=True), 
	}
	
# ====== PARENT METHOD ========================================

	def create(self, cr, uid, vals, context=None):
		trx_obj = self.pool.get('wallet.transaction')
	# post transaksinya 
		return trx_obj.post_manual_trx(cr, uid, vals)
				
	
# ====== EVENT HANDLER ===============================================================================================
	
	def onchange_master_trx(self, cr, uid, ids, trx_type_id):
		v={}
		if not trx_type_id: return {}
	# kalau master trx na diisi, ambil data2nya 
		master_trx_obj = self.pool.get('wallet.master.trx')
		master_trx = master_trx_obj.browse(cr, uid, trx_type_id)
		if not master_trx: return {}
		v['value'] = {
			'need_approve': master_trx.need_approve or "",
			'inc_dec': master_trx.inc_dec or "",
			'journal_debit_acc_id': master_trx.journal_debit_acc_id or "",
			'journal_credit_acc_id' : master_trx.journal_credit_acc_id or "",
			'journal_debit_flag' : master_trx.journal_debit_flag or "",
			'journal_credit_flag' : master_trx.journal_credit_flag or "",
		}
	
		return v
	
	
	