# ERPNext - web based ERP (http://erpnext.com)
# Copyright (C) 2012 Web Notes Technologies Pvt Ltd
# 
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
# 
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Please edit this list and import only required elements
import webnotes

from webnotes.utils import add_days, add_months, add_years, cint, cstr, date_diff, default_fields, flt, fmt_money, formatdate, generate_hash, getTraceback, get_defaults, get_first_day, get_last_day, getdate, has_common, month_name, now, nowdate, replace_newlines, sendmail, set_default, str_esc_quote, user_format, validate_email_add

from webnotes.model.doc import Document, addchild, getchildren, make_autoname
from webnotes.model.doclist import getlist
from webnotes.model.code import get_obj, get_server_obj, run_server_obj, updatedb, check_syntax
from webnotes import session, form, is_testing, msgprint, errprint

in_transaction = webnotes.conn.in_transaction
convert_to_lists = webnotes.conn.convert_to_lists

# -----------------------------------------------------------------------------------------

class DocType:
	def __init__(self, doc, doclist=[]):
		self.doc = doc
		self.doclist = doclist

	def autoname(self):
		#get default naming conventional from control panel
		supp_master_name = get_defaults()['supp_master_name']

		if supp_master_name == 'Supplier Name':
		
			# filter out bad characters in name
			#supp = self.doc.supplier_name.replace('&','and').replace('.','').replace("'",'').replace('"','').replace(',','').replace('`','')
			supp = self.doc.supplier_name
			
			cust = webnotes.conn.sql("select name from `tabCustomer` where name = '%s'" % (supp))
			cust = cust and cust[0][0] or ''
		
			if cust:
				msgprint("You already have a Customer with same name")
				raise Exception
			self.doc.name = supp
			
		else:
			self.doc.name = make_autoname(self.doc.naming_series+'.#####')

	# ----------------------------------------
	# update credit days and limit in account
	# ----------------------------------------
	def update_credit_days_limit(self):
		webnotes.conn.sql("update tabAccount set credit_days = '%s' where name = '%s'" % (self.doc.credit_days, self.doc.name + " - " + self.get_company_abbr()))


	def on_update(self):
		if not self.doc.naming_series:
			self.doc.naming_series = ''

		# create account head
		self.create_account_head()

		# update credit days and limit in account
		self.update_credit_days_limit()


	def check_state(self):
		return "\n" + "\n".join([i[0] for i in webnotes.conn.sql("select state_name from `tabState` where `tabState`.country='%s' " % self.doc.country)])
	
	# ACCOUNTS
	# -------------------------------------------
	def get_payables_group(self):
		g = webnotes.conn.sql("select payables_group from tabCompany where name=%s", self.doc.company)
		g = g and g[0][0] or ''
		if not g:
			msgprint("Update Company master, assign a default group for Payables")
			raise Exception
		return g

	def add_account(self, ac, par, abbr):
		arg = {'account_name':ac,'parent_account':par, 'group_or_ledger':'Group', 'company':self.doc.company,'account_type':'','tax_rate':'0'}
		t = get_obj('GL Control').add_ac(cstr(arg))
		msgprint("Created Group " + t)
	
	def get_company_abbr(self):
		return webnotes.conn.sql("select abbr from tabCompany where name=%s", self.doc.company)[0][0]
	
	def get_parent_account(self, abbr):
		if (not self.doc.supplier_type):
			msgprint("Supplier Type is mandatory")
			raise Exception
		
		if not webnotes.conn.sql("select name from tabAccount where name=%s and debit_or_credit = 'Credit' and ifnull(is_pl_account, 'No') = 'No'", (self.doc.supplier_type + " - " + abbr)):

			# if not group created , create it
			self.add_account(self.doc.supplier_type, self.get_payables_group(), abbr)
		
		return self.doc.supplier_type + " - " + abbr


	def validate(self):
		#validation for Naming Series mandatory field...
		if get_defaults()['supp_master_name'] == 'Naming Series':
			if not self.doc.naming_series:
				msgprint("Series is Mandatory.")
				raise Exception
	
	
	# create accont head - in tree under zone + territory
	# -------------------------------------------------------
	def create_account_head(self):
		if self.doc.company :
			abbr = self.get_company_abbr() 
						
			if not webnotes.conn.sql("select name from tabAccount where name=%s", (self.doc.name + " - " + abbr)):
				parent_account = self.get_parent_account(abbr)
				
				arg = {'account_name':self.doc.name,'parent_account': parent_account, 'group_or_ledger':'Ledger', 'company':self.doc.company,'account_type':'','tax_rate':'0','master_type':'Supplier','master_name':self.doc.name}
				# create
				ac = get_obj('GL Control').add_ac(cstr(arg))
				msgprint("Created Account Head: "+ac)
				
		else : 
			msgprint("Please select Company under which you want to create account head")
			
			
	def get_contacts(self,nm):
		if nm:
			contact_details =convert_to_lists(webnotes.conn.sql("select name, CONCAT(IFNULL(first_name,''),' ',IFNULL(last_name,'')),contact_no,email_id from `tabContact` where supplier = '%s'"%nm))
	 
			return contact_details
		else:
			return ''
			
	def delete_supplier_address(self):
		for rec in webnotes.conn.sql("select * from `tabAddress` where supplier='%s'" %(self.doc.name), as_dict=1):
			webnotes.conn.sql("delete from `tabAddress` where name=%s",(rec['name']))
	
	def delete_supplier_contact(self):
		for rec in webnotes.conn.sql("select * from `tabContact` where supplier='%s'" %(self.doc.name), as_dict=1):
			webnotes.conn.sql("delete from `tabContact` where name=%s",(rec['name']))
			
	def delete_supplier_communication(self):
		webnotes.conn.sql("""\
			delete from `tabCommunication`
			where supplier = %s and customer is null""", self.doc.name)
			
	def delete_supplier_account(self):
		"""delete supplier's ledger if exist and check balance before deletion"""
		acc = sql("select name from `tabAccount` where master_type = 'Supplier' \
			and master_name = %s and docstatus < 2", self.doc.name)
		if acc:
			from webnotes.model import delete_doc
			delete_doc('Account', acc[0][0])
			
			
	def on_trash(self):
		self.delete_supplier_address()
		self.delete_supplier_contact()
		self.delete_supplier_communication()
		self.delete_supplier_account()
		
		
	# on rename
	# ---------
	def on_rename(self,newdn,olddn):
		#update supplier_name if not naming series
		if get_defaults().get('supp_master_name') == 'Supplier Name':
			update_fields = [
			('Supplier', 'name'),
			('Address', 'supplier'),
			('Contact', 'supplier'),
			('Purchase Invoice', 'supplier'),
			('Purchase Order', 'supplier'),
			('Purchase Receipt', 'supplier'),
			('Serial No', 'supplier')]
			for rec in update_fields:
				webnotes.conn.sql("update `tab%s` set supplier_name = '%s' where %s = '%s'" %(rec[0],newdn,rec[1],olddn))
				
		#update master_name in doctype account
		webnotes.conn.sql("update `tabAccount` set master_name = '%s', master_type = 'Supplier' where master_name = '%s'" %(newdn,olddn))
