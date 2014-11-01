from openerp.osv import osv, fields
from datetime import date

_TRX_STATE = [
	('approved','Approved'),
	('pending','Pending'),
	('rejected','Rejected'),
]

_INC_DEC = [
	('increase','Increase'),
	('decrease','Decrease')
]

# ===============================================================================================================================

class wallet_owner_group(osv.osv):
	
	_name = 'wallet.owner.group'
	_description = 'Wallet - Owner Group'
	
# COLUMNS -----------------------------------------------------------------------------------------------------------------------

	_columns = {
		'name': fields.char('Name', required=True),
		'balance_min': fields.float('Minumum Balance'),
		'balance_overdraft': fields.float('Overdraft'),
	}
	
# ===============================================================================================================================

class wallet_owner(osv.osv):
	
	_name = 'wallet.owner'
	_description = 'Wallet - Owner'
	
# COLUMNS -----------------------------------------------------------------------------------------------------------------------

	_columns = {
		'name': fields.char('Name', required=True),
		'ref_model': fields.char('Ref. Model'),
		'ref_id': fields.integer('Ref. ID'),
		'balance_amount': fields.float('Balance', readonly=True), 
		'owner_group_id': fields.many2one('wallet.owner.group', 'Group'), 
	}
	
# CUSTOM METHODS ----------------------------------------------------------------------------------------------------------------

	"""
	Recalculates balance and update its value into balance_amount field.
	
	@param owner_id: owner of the wallet
	@param amount: amount to be updated
	@param inc_dec: increase (True) or decrease (False) balance
	
	@return True/False
	""" 
	def update_balance(self, cr, uid, owner_id, amount, inc_dec):
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
	Finds wallet owner id based on referred model and id. This is necessary because owner's internal id is most likely 
	not equal to referred id.
	
	@param owner_id: id of the referred model from which the owner is based
	@param owner_model: name of the model
	
	@return integer owner id on success, False otherwise
	""" 
	def get_owner(self, cr, uid, owner_id, owner_model):
		if not owner_id or not owner_model: return False
	# cari di model owner, apakah ada owner dengan ref id dan ref model tersebut
		owner_obj = self.pool.get('wallet.owner')
		owner_data = owner_obj.search(cr, uid, [('ref_model','=',owner_model),('ref_id','=',owner_id)])
		return owner_data and owner_data[0] or False
	
# ===============================================================================================================================

class wallet_master_trx(osv.osv):
	
	_name = 'wallet.master.trx'
	_description = 'Wallet - Master Transaction'
	
# COLUMNS -----------------------------------------------------------------------------------------------------------------------

	_columns = {
		'name': fields.char('Name', required=True),
		'mnemonic': fields.char('Mnemonic', required=True),
		'need_approve': fields.boolean('Need approval?'),
		'inc_dec': fields.selection(_INC_DEC, 'Increase/Decrease?'), 
		'journal_debit_acc_id': fields.many2one('account.account', 'Journal Debit'),
		'journal_credit_acc_id': fields.many2one('account.account', 'Journal Credit'),
		'journal_debit_flag': fields.boolean('Positive Debit?'), # True = positif, False = negatif
		'journal_credit_flag': fields.boolean('Positive Credit?'),
	}
	
# DEFAULTS ----------------------------------------------------------------------------------------------------------------------
	
	_defaults = {
		'journal_debit_flag': True,
		'journal_credit_flag': True,
	}
	
# ===============================================================================================================================

class wallet_transaction(osv.osv):
	
	_name = 'wallet.transaction'
	_description = 'Wallet - Master Transaction'
	
# COLUMNS -----------------------------------------------------------------------------------------------------------------------

	_columns = {
		'name': fields.char('Name', size=50, required=True),
		'trx_type_id': fields.many2one('wallet.master.trx', 'Master Trx'),
		'wallet_owner_id': fields.many2one('wallet.owner', 'Wallet Owner'),
		'trx_date': fields.date('Date'),
		'increase_amount': fields.float('Increase amount'), 
		'decrease_amount': fields.float('Decrease amount'), 
		'state': fields.selection(_TRX_STATE, 'State', select=True, readonly=True),
		'is_overdraft': fields.boolean('Overdraft?',
			help="Transaction is flagged as overdraft if it is performed with balance under minimum balance but still bigger \
			than overdraft."),
	}
	
# DEFAULTS ----------------------------------------------------------------------------------------------------------------------
	
	_defaults = {
		'is_overdraft': False,
		'state': 'pending',
		'increase_amount': 0,
		'decrease_amount': 0,
	}
	
# CUSTOM METHODS ----------------------------------------------------------------------------------------------------------------

	"""
	Post a transaction based on master transaction. This is the API method. Use this from your own module.
	
	@param name: transaction number or reference. Optionally fill this according to your needs.
	@param trx_date: date and time of the transaction
	@param owner_ref_id: id of the referred model from which the owner is based
	@param owner_ref_model: the model name
	@param mnemonic: mnemonic of the master transaction to be posted
	@param amount: transaction amount
	@param owner_id: id of the wallet owner. This can be used as alternative to owner_ref_id+owner_ref_model combination. 
	
	@return integer id of the new transaction (wallet_transaction.id, to be precise) on success, False otherwise
	""" 
	def post_transaction(self, cr, uid, name, trx_date=None, owner_ref_id, owner_ref_model, mnemonic, amount, owner_id=False, 
	context=None):
		if not name or not mnemonic or not amount or ((not owner_ref_id or not owner_ref_model) or not owner_id): return False
	# ambil id owner
		if not owner_id:
			owner_obj = self.pool.get('wallet.owner')
			owner_id = owner_obj.get_owner(cr, uid, owner_ref_id, owner_ref_model)
		if not owner_id: return False
	# cari master trx berdasarkan mnemonicnya
		master_trx_obj = self.pool.get('wallet.master.trx')
		master_trx_id = master_trx_obj.search(cr, uid, [('mnemonic','=',mnemonic)])
		if len(master_trx_id) == 0:
			raise osv.except_osv(_('Wallet Transaction Error'), _('Invalid transaction mnemonic.')) 
			return False
		master_trx_id = master_trx_id[0]
	# kalau ada, insert datanya
		master_trx = master_trx_obj.read(cr, uid, master_trx_id)
		vals = {
			'name': name, 
			'trx_type_id': master_trx_id,
			'wallet_owner_id': owner_id, 
			'trx_date': trx_date or date.today(),
			'state': ''
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
		owner_obj.update_balance(cr, uid, owner_id, amount, master_trx['inc_dec'])
	# masukin ke modul accounting
		if master_trx['journal_debit_acc_id'] and master_trx['journal_credit_acc_id']:
		# later
			print "masuk accounting"
		return result
	
	"""
	Post manual transaction, those which do not refer to any master transaction. Even if it does, all aspects of the master 
	transaction (e.g increase/decrease, journaling account, approval) can be changed.
	
	@param vals: see all column names of wallet_manual_trx_memory class below  
	
	@return True on success, False otherwise
	""" 
	def post_manual_transaction(self, cr, uid, vals, context=None):
		if not vals: return False
	# cek butuh approve ga?
		approve = ('need_approve' in vals and vals['need_approve']) and 'pending' or 'approved'
	# ada master trx nya ga?
		if 'trx_type_id' not in vals: vals['trx_type_id'] = None
	# cek ini increase/decrease balance?
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
	
	def increase_balance(self, cr, uid, name, trx_date, amount, trx_type_id=None, approve='approved', owner_ref_id=False, 
	owner_ref_model=False, owner_id=False, context=None):
		owner_obj = self.pool.get('wallet.owner')
		if ((not owner_ref_id or not owner_ref_model) and not owner_id) or not amount: return False
	# cek owner dari owner_ref ini id nya apa
		if not owner_id:
			owner_id = owner_obj.get_owner(cr, uid, owner_ref_id, owner_ref_model)
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
		if approve == "approved": owner_obj.update_balance(cr, uid, owner_id, amount, 1)
		return result
	
	def decrease_balance(self, cr, uid, name, trx_date, amount, trx_type_id=None, approve='approved', owner_ref_id=False, 
	owner_ref_model=False, owner_id=False, context=None):
		if ((not owner_ref_id or not owner_ref_model) and not owner_id) or not amount: return False
	# cek owner dari owner_ref ini id nya apa
		owner_obj = self.pool.get('wallet.owner')
		if not owner_id:
			owner_id = owner_obj.get_owner(cr, uid, owner_ref_id, owner_ref_model)
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
		if approve == "approved": owner_obj.update_balance(cr, uid, owner_id, amount, 2)
		return result
	
# ACTION ------------------------------------------------------------------------------------------------------------------------
	
	def action_approve_trx(self, cr, uid, ids, context=None):
		trx_obj = self.pool.get('wallet.transaction')
		owner_obj = self.pool.get('wallet.owner')
		for trx_data in trx_obj.browse(cr, uid, ids):
		# cek transaksinya increase/decrease?
			if trx_data.increase_amount:
				amount = trx_data.increase_amount
				inc_dec = 1
			elif trx_data.decrease_amount:
				amount = trx_data.decrease_amount
				inc_dec = 2
		# itung ulang balancenya
			owner_obj.update_balance(cr, uid, trx_data.wallet_owner_id.id, amount, inc_dec)
		return trx_obj.write(cr, uid, ids, { 
			'state': 'approved'
		})
	
	def action_reject_trx(self, cr, uid, ids, context=None):
		trx_obj = self.pool.get('wallet.transaction')
		return trx_obj.write(cr, uid, ids, { 
			'state': 'rejected'
		})
		return True
	
# OVERRIDES ---------------------------------------------------------------------------------------------------------------------

	def write(self, cr, uid, ids, vals, context=None):
	# cegah user dari mengupdate transaksi kecuali mengganti state atau nomor transaksi
		if all (k in vals for k in ('state','name')):
			return super(wallet_transaction, self).write(cr, uid, ids, vals, context=context)
		else:
			raise osv.except_osv(_('Wallet Transaction Error'), _('Cannot update transaction(s). Please instead post a new \
				transaction to reverse/correct the amount debited/credited.')) 
			return False
			
		
	def unlink(self, cr, uid, ids, context=None):
	# cegah user dari menghapus transaksi
		raise osv.except_osv(_('Wallet Transaction Error'), _('Cannot delete transaction(s). Please instead post a new \
			transaction to reverse the amount debited/credited.')) 
		return False

# ===============================================================================================================================

class wallet_manual_trx_memory(osv.osv_memory):
	
	_name = 'wallet.manual.trx.memory'
	_description = 'Wallet-Manual Transaction'
	
# COLUMNS -----------------------------------------------------------------------------------------------------------------------

	_columns = {
		'trx_date': fields.date('Date', required=True),
		'name': fields.char('Name', required=True),
		'wallet_owner_id': fields.many2one('wallet.owner', 'Wallet Owner', required=True),
		'trx_type_id': fields.many2one('wallet.master.trx', 'Master Trx'),
		'need_approve': fields.boolean('Need approve?'),
		'inc_dec': fields.selection(_INC_DEC, 'Increase/Decrease?', required=True),
		'journal_debit_acc_id': fields.many2one('account.account', 'Journal Debit'),
		'journal_credit_acc_id': fields.many2one('account.account', 'Journal Credit'),
		'journal_debit_flag': fields.boolean('Positive Debit?'), # True = positif, False = negatif
		'journal_credit_flag': fields.boolean('Positive Credit?'),
		'amount': fields.float('Amount', required=True), 
	}
	
# ONCHANGE ----------------------------------------------------------------------------------------------------------------------

	def onchange_master_trx(self, cr, uid, ids, trx_type_id):
		if not trx_type_id: return {}
	# kalau master trx na diisi, ambil data2nya 
		master_trx_obj = self.pool.get('wallet.master.trx')
		master_trx = master_trx_obj.browse(cr, uid, trx_type_id)
		if not master_trx: return {}
		return {
			'value': {
				'need_approve': master_trx.need_approve or "",
				'inc_dec': master_trx.inc_dec or "",
				'journal_debit_acc_id': master_trx.journal_debit_acc_id or "",
				'journal_credit_acc_id': master_trx.journal_credit_acc_id or "",
				'journal_debit_flag': master_trx.journal_debit_flag or "",
				'journal_credit_flag': master_trx.journal_credit_flag or "",
			}
		}
	
# OVERRIDES ---------------------------------------------------------------------------------------------------------------------

	def create(self, cr, uid, vals, context=None):
		trx_obj = self.pool.get('wallet.transaction')
	# post transaksinya 
		return trx_obj.post_manual_transaction(cr, uid, vals)
				
	
	