from openerp.osv import osv, fields
from openerp.tools.translate import _
from openerp.osv.orm import browse_record
from lxml import etree

from datetime import date, datetime, timedelta
from dateutil.relativedelta import *
import calendar

_TRX_STATE = [
	('approved','Approved'),
	('pending','Pending'),
	('rejected','Rejected'),
]

_INC_DEC = [
	('increase','Increase'),
	('decrease','Decrease')
]

_DATE_RANGE = [
	(1, 'This month'),
	(2, 'Last month'),
	(3, 'Last three months'),
	(4, 'This year'),
]

# ===============================================================================================================================

class wallet_owner_group(osv.osv):
	
	_name = 'wallet.owner.group'
	_description = 'Wallet - Owner Group'
	
# COLUMNS -----------------------------------------------------------------------------------------------------------------------

	_columns = {
		'name': fields.char('Name', required=True),
		'balance_min': fields.float('Minimum Balance'),
		'balance_overdraft': fields.float('Overdraft'),
	}
	
# ===============================================================================================================================

class wallet_owner(osv.osv):
	
	_name = 'wallet.owner'
	_description = 'Wallet - Owner'
	
# COLUMNS -----------------------------------------------------------------------------------------------------------------------

	_columns = {
		'name': fields.char('Name', required=True),
		'balance_amount': fields.float('Balance', readonly=True), 
		'owner_group_id': fields.many2one('wallet.owner.group', 'Group'), 
	}
	
# CUSTOM METHODS ----------------------------------------------------------------------------------------------------------------

	"""
	Increase or decrease balance and update its current value into balance_amount field.
	
	@param owner_id: owner of the wallet
	@param amount: amount to be updated
	@param inc_dec: increase (True) or decrease (False) balance
	
	@return True/False
	""" 
	def update_balance(self, cr, uid, owner_id, amount, inc_dec):
		if not owner_id or not amount or not inc_dec: return False
		balance_amount = self.read(cr, uid, owner_id, ['balance_amount'])['balance_amount']
	# 1 = increase, 2 = decrease
		if inc_dec == "increase": 
			balance_amount += float(amount)
		elif inc_dec == "decrease":
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
		'inc_dec': fields.selection(_INC_DEC, 'Increase/Decrease?', required=True), 
		'journal_id': fields.many2one('account.journal', 'Journal'),
	}
	
# CONSTRAINTS -------------------------------------------------------------------------------------------------------------------
	
	_sql_constraints = [
		('unique_mnemonic', 'unique(mnemonic)', _('There cannot be identical mnemonic for transaction types.')),
	]
	
# ===============================================================================================================================

class wallet_transaction(osv.osv):
	
	_name = 'wallet.transaction'
	_description = 'Wallet - Master Transaction'
	
# COLUMNS -----------------------------------------------------------------------------------------------------------------------

	_columns = {
		'name': fields.char('Transaction Ref.', size=50, required=True),
		'trx_type_id': fields.many2one('wallet.master.trx', 'Type'),
		'wallet_owner_id': fields.many2one('wallet.owner', 'Wallet Owner'),
		'trx_date': fields.datetime('Date'),
		'increase_amount': fields.float('Increase'), 
		'decrease_amount': fields.float('Decrease'),
		'running_balance': fields.float('Balance'), 
		'state': fields.selection(_TRX_STATE, 'Approval', select=True, readonly=True),
		'approved_by': fields.many2one('res.users', 'By'),
		'approved_at': fields.datetime('At'),
		#'account_move_id': fields.many2one('account.move', 'Account Move Ref.'),
		'is_overdraft': fields.boolean('Overdraft?',
			help="Transaction is flagged as overdraft if it is performed with balance under minimum balance but still bigger than overdraft."),
	}
	
# DEFAULTS ----------------------------------------------------------------------------------------------------------------------
	
	_defaults = {
		'is_overdraft': False,
		'state': 'pending',
		'increase_amount': 0,
		'decrease_amount': 0,
	}
	
	_order = 'trx_date'

# CUSTOM METHODS ----------------------------------------------------------------------------------------------------------------

	"""
	Post a transaction based on a master transaction. This is the API method. Use this from your own module.
	
	@param name: transaction number or reference. Optionally fill this according to your needs.
	@param trx_date: date and time of the transaction
	@param owner_ref_id: id of the referred model from which the owner is based
	@param owner_ref_model: the model name
	@param mnemonic: mnemonic of the master transaction to be posted
	@param amount: transaction amount
	@param owner_id: id of the wallet owner. This can be used as alternative to owner_ref_id+owner_ref_model combination. 
	
	@return integer id of the new transaction (wallet_transaction.id, to be precise) on success, False otherwise
	""" 
	def post_transaction(self, cr, uid, name, mnemonic, amount, trx_date=None, owner_ref_id=0, owner_ref_model="",  
	owner_id=0, context=None):
		if not name or not mnemonic or not amount: return False
	# cari master trx berdasarkan mnemonicnya
		master_trx_obj = self.pool.get('wallet.master.trx')
		master_trx_id = master_trx_obj.search(cr, uid, [('mnemonic','=',mnemonic)])
		if len(master_trx_id) == 0:
			raise osv.except_osv(_('Wallet Transaction Error'), _('Invalid transaction mnemonic.')) 
			return False
		master_trx_id = master_trx_id[0]
	# yuu post
		return self._post_transaction(cr, uid, {
			'name': name,
			'trx_date': trx_date or datetime.now(),
			'amount': amount,
			'owner_ref_id': owner_ref_id,
			'owner_ref_model': owner_ref_model,
			'owner_id': owner_id,
			'trx_type_id': master_trx_id
		}, context=context)
	
	"""
	Post a transaction, regardless of presence or absence of master transaction. This is backbone method for wallet module.
	
	@param vals:   
		other than name, trx_date, and amount, vals must have these according to transaction type:
		- post by mnemonic:
			- owner_ref_id and owner_ref_model, or owner_id
			- trx_type_id (obtained by search by mnemonic)	
		- manual transaction:
			- trx_type_id
			- owner_id 
			- is_approval (must be False)
			- inc_dec (either "increase" or "decrease")
			- journal_debit_acc_id, 
			- journal_credit_acc_id,
		- increase/decrease balance:
			- owner_ref_id and owner_ref_model, or owner_id
			- is_approval (must be False)
			- inc_dec ("increase" for increase balance or "decrease" for decrease balance)
	
	@return True on success, False otherwise
	""" 
	def _post_transaction(self, cr, uid, vals, context=None):
		if not vals: return False
	# ambil master transaksi bila diinginkan
		if vals.get('trx_type_id', False):
			trx_obj = self.pool.get('wallet.master.trx')	
			trx_data = trx_obj.read(cr, uid, vals['trx_type_id'])
		else:
			trx_data = {}
	# ambil id owner. bisa langsung id ownernya atau ref_id dan ref_model 
	# cek juga supaya owner_id nya valid
		owner_obj = self.pool.get('wallet.owner')
		owner_id = vals.get('owner_id', 0)
		if not owner_id:
			owner_ref_id = vals.get('owner_ref_id', None)
			owner_ref_model = vals.get('owner_ref_model', None)
			owner_id = owner_obj.get_owner(cr, uid, owner_ref_id, owner_ref_model)
			if not owner_id: 
				raise osv.except_osv(_('Wallet Transaction Error'), _('Please specify valid owner.')) 
		owner_data = owner_obj.browse(cr, uid, owner_id)
		if not owner_data: 
			raise osv.except_osv(_('Wallet Transaction Error'), _('Please specify valid owner.')) 
	# tentukan approval atau tidak
		is_approval = vals.get('is_approval') or trx_data.get('need_approve') or False
	# tentukan amount increase atau decrease
		if not 'amount' in vals:
			raise osv.except_osv(_('Wallet Transaction Error'), _('Please specify valid transaction amount.')) 
		amount = vals['amount']
		inc_dec = vals.get('inc_dec') or trx_data.get('inc_dec') or ""
		increase_amount = inc_dec == 'increase' and amount or 0
		decrease_amount = inc_dec == 'decrease' and amount or 0
		if increase_amount == 0 and decrease_amount == 0: 
			raise osv.except_osv(_('Wallet Transaction Error'), _('Please specify amount of this transaction.')) 
	# cek minimum balance dan overdraft
		is_overdraft = False
		if inc_dec == 'decrease':
			next_balance = owner_data.balance_amount - amount
			if next_balance < owner_data.owner_group_id.balance_min:
				is_overdraft = True
			if next_balance < owner_data.owner_group_id.balance_min - owner_data.owner_group_id.balance_overdraft:
				raise osv.except_osv(_('Wallet Transaction Error'), _('Cannot perform the transaction. Not enough balance.')) 
	# mainkan!
		result = self.create(cr, uid, {
			'name': vals['name'],
			'trx_type_id': 'trx_type_id' in vals and vals['trx_type_id'] or None,
			'wallet_owner_id': owner_id,
			'trx_date': 'trx_date' in vals and vals['trx_date'] or datetime.now(),
			'increase_amount': increase_amount, 
			'decrease_amount': decrease_amount, 
			'is_overdraft': is_overdraft,
		})
		if not result: return result
	# kalau harus di-approve, ya sudah
		if is_approval: return result
	# kalau langsung posting, ya langsung posting :D
		self.approve_transaction(cr, uid, [result], vals, context=context)
		return result
	
	def approve_transaction(self, cr, uid, ids, vals={}, context=None):
	# ambil data transaksi. ids bisa berupa browse_record, list of id, atau single id
		if isinstance(ids, browse_record):
			trx_data = [ids]
		else:
			if isinstance(ids, int): ids = [ids]
			trx_data = self.browse(cr, uid, ids)
	# ubah state nya jadi approved
		self.write(cr, uid, ids, { 
			'state': 'approved',
			'approved_by': uid,
			'approved_at': datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
		})
		owner_obj = self.pool.get('wallet.owner')
		account_move_obj = self.pool.get('account.move')
		journal_obj = self.pool.get('account.journal')
		for row in trx_data:
		# update balance
			owner_obj.update_balance(cr, uid, row.wallet_owner_id.id, row.increase_amount or row.decrease_amount, 
				row.increase_amount and 'increase' or 'decrease')
		# posting ke accounting, bila diharuskan
		# install modul accounting ga di sini? kalo ngga, ya udah ga usah posting
			if not account_move_obj: continue
		# tentukan journal nya. kalau ada di trx type nya, pake yang itu, kalo ngga pake yang kodenya MISC
		# (bawaan modul accounting)
			if row.trx_type_id.journal_id:
				is_misc = not (row.trx_type_id.journal_id.default_debit_account_id and \
					row.trx_type_id.journal_id.default_credit_account_id)
				journal_id = row.trx_type_id.journal_id.id
			else:
				is_misc = True
				journal_id = journal_obj.search(cr, uid, [('code','=','MISC')])
				if not journal_id:
					raise osv.except_osv(_('Wallet Transaction Error'), _("No miscellanous journal detected. Please add new \
					journal with code 'MISC'."))
				journal_id = journal_id[0]
		# ambil dulu journal account untuk debit dan credit transaksi ini
		# sekalian ambil flag negatif untuk posting journal
		# flag bisa berasal dari vals dan diambil dari settingan master trx
			if vals.get('journal_debit_acc_id', False) and vals.get('journal_credit_acc_id', False):
				debit_account_id = vals['journal_debit_acc_id']
				credit_account_id = vals['journal_credit_acc_id']
			elif row.trx_type_id.journal_id and row.trx_type_id.journal_id.default_debit_account_id and \
			row.trx_type_id.journal_id.default_credit_account_id:
				debit_account_id = row.trx_type_id.journal_id.default_debit_account_id.id
				credit_account_id = row.trx_type_id.journal_id.default_credit_account_id.id
			elif is_misc:
			# note: bila jurnalnya miscellanous, maka account harus ditentukan secara manual dengan mengoverride method
			# _prepare_account_move_lines 
				debit_account_id = None
				credit_account_id = None
			else:
				continue # kalo ngga ada account dua2nya, lanjut aja ke id berikutnya
		# tentukan amount
			amount = max(row.increase_amount,row.decrease_amount)
		# kalo ada jurnalnya, cek bahwa sequence jurnalnya udah diset sama user nya
			if row.trx_type_id.journal_id:
				if not row.trx_type_id.journal_id.sequence_id.prefix and not row.trx_type_id.journal_id.sequence_id.suffix:
					raise osv.except_osv(_('Wallet Transaction Error'), _('Journal sequence is not yet set. Please contact your administrator.')) 
		# dor! posting deh
		# siapin account move header, lalu bikin deh
			account_move_data = account_move_obj.account_move_prepare(cr, uid, journal_id)
			account_move_data.update({
				'ref': row.wallet_owner_id.name + ' - ' + row.name,
			})
			move_id = account_move_obj.create(cr, uid, account_move_data, context=context)
		# siapin move lines nya
			if is_misc:
				lines = []
			else:
				lines = [
					{
						'name': (row.wallet_owner_id.name + ' - ' + row.name)[:64],
						'debit': amount, 
						'account_id': debit_account_id,
					},
					{
						'name': (row.wallet_owner_id.name + ' - ' + row.name)[:64],
						'credit': amount,
						'account_id': credit_account_id,
					}
				]
			move_lines = self._prepare_account_move_lines(cr, uid, row, move_id, lines, context=context)
		# tulis account move line menjadi anak si account move tadi
			account_move_obj.write(cr, uid, [move_id], {'line_id': move_lines}, context=context)
		# link kan transaksi ini dengan si account move, untuk kepentingan selanjutnya
			self.write(cr, uid, [row.id], {'account_move_id': move_id}, context=context) 
		return True
	
	"""
	Prepares account move lines of this wallet transaction
	
	@param trx_data: either integer (transaction id) or browse_record of said wallet transaction.
	@param move_id: integer move id created before. It has to be created prior to calling if this method
	@param lines: list of dictionary, each must contain at least name, debit/credit, and account_id 
	
	@return account move lines, ready to be write()-ed to account.move object 
	"""
	def _prepare_account_move_lines(self, cr, uid, trx_data, move_id, lines, context=None):
		move_lines = []
		for move_line in lines:
			move_line.update({
				'move_id': move_id,
				'debit': move_line.get('debit', 0),
				'credit': move_line.get('credit', 0),
			})
			move_lines.append([0,False,move_line])
		return move_lines
		
		
	def increase_balance(self, cr, uid, trx_date, amount, name="", owner_ref_id=0, owner_ref_model="", owner_id=0, 
	context=None):
		return self._post_transaction(cr, uid, {
			'name': name or 'BALINC',
			'trx_date': trx_date or datetime.now(),
			'amount': amount,
			'owner_ref_id': owner_ref_id,
			'owner_ref_model': owner_ref_model,
			'owner_id': owner_id,
			'is_approval': False,
			'inc_dec': 'increase',
		})
	
	def decrease_balance(self, cr, uid, trx_date, amount, name="", owner_ref_id=0, owner_ref_model="", owner_id=0, 
	context=None):
		return self._post_transaction(cr, uid, {
			'name': name or 'BALDEC',
			'trx_date': trx_date or datetime.now(),
			'amount': amount,
			'owner_ref_id': owner_ref_id,
			'owner_ref_model': owner_ref_model,
			'owner_id': owner_id,
			'is_approval': False,
			'inc_dec': 'decrease',
		})
	
# ACTION ------------------------------------------------------------------------------------------------------------------------
	
	def action_approve_trx(self, cr, uid, ids, context=None):
		return self.approve_transaction(cr, uid, ids, context=context)
	
	def action_reject_trx(self, cr, uid, ids, context=None):
		return self.write(cr, uid, ids, { 
			'state': 'rejected',
			'approved_by': uid,
			'approved_at': datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
		})
	
# OVERRIDES ---------------------------------------------------------------------------------------------------------------------

	def write(self, cr, uid, ids, vals, context=None):
	# cegah user dari mengupdate transaksi kecuali mengganti state atau nomor transaksi
		if 'state' in vals or 'name' in vals or 'account_move_id' in vals:
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
	
	def search(self, cr, uid, args, offset=0, limit=None, order=None, context=None, count=False):
		result = super(wallet_transaction, self).search(cr, uid, args, offset, limit, order, context, count)
		return result and [0] + result + [1000000000] or [] 
		
	def read(self, cr, uid, ids, fields=None, context=None, load='_classic_read'):
	# kalo read dipanggil buat list, yang mana adalah hasil dari search, maka di elemen pertamanya ada angka 0
	# (lihat def search di atas). kalau ids di-pass bulat2 ke parent read, di odoo 8 jadi ngaco
	# maka dari itu elemen pertama (0) dan terakhir (1000000000) dibuang dulu dari ids 
		orig_ids = ids[0] == 0 and ids[1:-1] or ids
		rows = super(wallet_transaction, self).read(cr, uid, orig_ids, fields=fields, context=context, load=load)
	# kasih baris2 buat beginning balance dan end balance, lalu hitung juga running balance per baris
		result = rows 
		if context and not context.get('hide_balance') and rows:
		# ambil tanggal pertama baris pertama, pakai untuk mengambil saldo per tanggal sebelumnya
			first_date = datetime.strptime(rows[0]['trx_date'].split(' ')[0], '%Y-%m-%d')
			previous_date = first_date - timedelta(seconds=1)
		# cari dulu di hasil read ini ada owner siapa aja. saldonya adalah gabungan saldo2 para owner
			owners = []
			for row in rows: owners.append(row['wallet_owner_id'][0])
			owners = list(set(owners))
		# ambil saldo per tanggal itu, alias total debet-credit utnuk seluruh transaksi sebelum tanggal itu
		# lalu update ke baris pertama (beginning balance)
		# harus di sini karena by now kita udah tau baris2 transaksi ini melibatkan owner mana saja
			cr.execute("""
				SELECT (SUM(increase_amount) - SUM(decrease_amount)) AS balance 
				FROM wallet_transaction 
				WHERE 
					trx_date <= '%s' AND 
					wallet_owner_id IN (%s)
			""" % (previous_date.strftime('%Y-%m-%d %H:%M:%S'), ', '.join(str(s) for s in owners)))
			balance = cr.dictfetchone()['balance'] or 0
		# masukin ke baris pertama result sebagai Beginning Balance 
			result = [{
				'id': 0,
				'trx_date': first_date.strftime('%Y-%m-%d'),
				'wallet_owner_id': False,
				'name': 'Beginning Balance',
				'increase_amount': 0,
				'decrease_amount': 0,
				'running_balance': balance,
				'is_overdraft': False,
			}]
		# pindahin rows ke result, sambil mengupdate running balance nya
			for row in rows:
				last_date = row['trx_date']
				balance += row['increase_amount'] - row['decrease_amount']
				row.update({
					'running_balance': balance
				})
				result.append(row)
		# tambahin end balance
			result.append({
				'id': 1000000000,
				'trx_date': last_date,
				'wallet_owner_id': False,
				'name': 'Ending Balance',
				'increase_amount': 0,
				'decrease_amount': 0,
				'running_balance': balance,
				'is_overdraft': False,
			})
		else:
			result = rows
		return result
	
# ===============================================================================================================================

class wallet_manual_trx_memory(osv.osv_memory):
	
	_name = 'wallet.manual.trx.memory'
	_description = 'Wallet-Manual Transaction'
	
# COLUMNS -----------------------------------------------------------------------------------------------------------------------

	_columns = {
		'trx_date': fields.datetime('Date', required=True),
		'name': fields.char('Transaction Ref.', required=True),
		'owner_id': fields.many2one('wallet.owner', 'Wallet Owner', required=True),
		'trx_type_id': fields.many2one('wallet.master.trx', 'Transaction Type'),
		'is_approval': fields.boolean('Need approval?'),
		'inc_dec': fields.selection(_INC_DEC, 'Increase/Decrease?', required=True),
		'amount': fields.float('Amount', required=True), 
	}
	
# DEFAULTS ----------------------------------------------------------------------------------------------------------------------
	
	_defaults = {
		'trx_date': lambda *a: datetime.today().strftime('%Y-%m-%d %H:%M:%S'),
		'is_approval': False,
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
				'is_approval': master_trx.need_approve or "",
				'inc_dec': master_trx.inc_dec or "",
			}
		}
	
# OVERRIDES ---------------------------------------------------------------------------------------------------------------------

	def create(self, cr, uid, vals, context=None):
	# kalau di context ada mnemonic transaction master, maka isi field2 transaction dengan data2 dari master itu
		if context and context.get('trx_type'):
			trx_type_obj = self.pool.get('wallet.master.trx')
			trx_type_id = trx_type_obj.search(cr, uid, [('mnemonic','=',context.get('trx_type'))])
			if not trx_type_id:
				raise osv.except_osv(_('Wallet Transaction Error'), _('Invalid transaction type.'))
			trx_type_data = trx_type_obj.read(cr, uid, trx_type_id[0])
			trx_type_data['is_approval'] = trx_type_data['need_approve']
			vals.update(trx_type_data)
			vals.update({'trx_type_id': trx_type_id[0], 'name': 'DPST'}) 
		trx_obj = self.pool.get('wallet.transaction')
		return trx_obj._post_transaction(cr, uid, vals)
				
# ===============================================================================================================================

class wallet_transaction_filter(osv.osv_memory):
	
	_name = 'wallet.transaction.filter'
	_description = 'Wallet - Transaction Filter'
	
# COLUMNS -----------------------------------------------------------------------------------------------------------------------

	_columns = {
		'date_from': fields.date('From Date', required=True),
		'date_to': fields.date('To', required=True),
		'date_range': fields.selection(_DATE_RANGE, 'Date Range'),
		'owner_id': fields.many2one('wallet.owner', 'Owner'),
		'include_pending': fields.boolean('Include Pending?'),
	}
	
# DEFAULTS ----------------------------------------------------------------------------------------------------------------------
	
	_defaults = {
		'date_range': 1
	}
	
# ONCHANGE ----------------------------------------------------------------------------------------------------------------------

	def onchange_date_range(self, cr, uid, ids, date_range):
		today = date.today()
		if date_range == 1: # this month
			return {
				'value': {
					'date_from': date(today.year, today.month, 1).strftime('%Y-%m-%d'),
					'date_to': (today).strftime('%Y-%m-%d'),
				}
			}
		elif date_range == 2: # last month
			last_month = (today - relativedelta(months=1))
			return {
				'value': {
					'date_from': date(last_month.year, last_month.month, 1).strftime('%Y-%m-%d'),
					'date_to': date(last_month.year, last_month.month, calendar.monthrange(last_month.year, last_month.month)[1]).
						strftime('%Y-%m-%d'),
				}
			}
		elif date_range == 3: # last 3 months
			last_month = (today - relativedelta(months=1))
			last_3 = (today - relativedelta(months=3))
			return {
				'value': {
					'date_from': date(last_3.year, last_3.month, 1).strftime('%Y-%m-%d'),
					'date_to': date(last_month.year, last_month.month, calendar.monthrange(last_month.year, last_month.month)[1]).
						strftime('%Y-%m-%d'),
				}
			}
		elif date_range == 4: # this year
			return {
				'value': {
					'date_from': date(today.year, 1, 1).strftime('%Y-%m-%d'),
					'date_to': (today).strftime('%Y-%m-%d'),
				}
			}
		return {}
	
# ACTION ------------------------------------------------------------------------------------------------------------------------
	
	def action_view_history(self, cr, uid, ids, context=None):
		context = context or {}
		model_obj = self.pool.get('ir.model.data')
		action_obj = self.pool.get('ir.actions.act_window')
	# ambil inputan user barusan
		data = self.read(cr, uid, ids, context=context)[0]
		domain = [('trx_date','>=',data['date_from']+' 00:00:00'),('trx_date','<=',data['date_to']+' 23:59:59')]
		if data['include_pending']:
			domain.append(('state','not in',['rejected']))
		else:
			domain.append(('state','=','approved'))
		if data['owner_id']:
			domain.append(('wallet_owner_id','=',data['owner_id'][0]))
	# load action terakhir di mana perubahan tingkat aktif dilakukan
	# id dari action tersebut di-pass via context['latest_action']
	# lihat sis,js bagian SISListView  
		model, action_id = model_obj.get_object_reference(cr, uid, 'wallet', 'wallet_action_transaction2')
	# ambil action data nya
		result = action_obj.read(cr, uid, [action_id], context=context)[0]
	# clear breadcrumbs (pura2nya kayak user klik menunya lagi)
		result.update({
			'clear_breadcrumbs': True,
			'domain': domain
		})
		return result
