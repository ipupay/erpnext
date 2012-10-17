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


from __future__ import unicode_literals
import unittest
import webnotes
import webnotes.model
from webnotes.utils import nowdate
from accounts.utils import get_fiscal_year

from stock.doctype.purchase_receipt import test_purchase_receipt

company = webnotes.conn.get_default("company")
abbr = webnotes.conn.get_value("Company", company, "abbr")

def load_data():
	test_purchase_receipt.load_data()
	
	webnotes.model.insert({"doctype": "Account", "account_name": "Excise Duty",
		"parent_account": "Tax Assets - %s" % abbr, "company": company,
		"group_or_ledger": "Ledger"})
	
	webnotes.model.insert({"doctype": "Account", "account_name": "Education Cess",
		"parent_account": "Tax Assets - %s" % abbr, "company": company,
		"group_or_ledger": "Ledger"})
	
	webnotes.model.insert({"doctype": "Account", "account_name": "S&H Education Cess",
		"parent_account": "Tax Assets - %s" % abbr, "company": company,
		"group_or_ledger": "Ledger"})
		
	webnotes.model.insert({"doctype": "Account", "account_name": "CST",
		"parent_account": "Direct Expenses - %s" % abbr, "company": company,
		"group_or_ledger": "Ledger"})
		
	webnotes.model.insert({"doctype": "Account", "account_name": "Discount",
		"parent_account": "Direct Expenses - %s" % abbr, "company": company,
		"group_or_ledger": "Ledger"})
		
	from webnotes.model.doc import Document
	item = Document("Item", "Home Desktop 100")
	
	# excise duty
	item_tax = item.addchild("item_tax", "Item Tax")
	item_tax.tax_type = "Excise Duty - %s" % abbr
	item_tax.tax_rate = 10
	item_tax.save()

import json	
purchase_invoice_doclist = [
	# parent
	{
		"doctype": "Purchase Invoice", 
		"credit_to": "East Wind Inc. - %s" % abbr,
		"supplier_name": "East Wind Inc.",
		"naming_series": "BILL", "posting_date": nowdate(),
		"company": company, "fiscal_year": webnotes.conn.get_default("fiscal_year"), 
		"currency": webnotes.conn.get_default("currency"), "conversion_rate": 1,
		"grand_total_import": 0
	},
	# items
	{
		"doctype": "Purchase Invoice Item", 
		"item_code": "Home Desktop 100", "qty": 10, "rate": 50,
		"amount": 500, "parentfield": "entries", "conversion_factor": 1, 
		"uom": "Nos", "item_tax_rate": json.dumps({"Excise Duty - %s" % abbr: 10})
	},
	{
		"doctype": "Purchase Invoice Item", 
		"item_code": "Home Desktop 200", "qty": 5, "rate": 150,
		"amount": 750, "parentfield": "entries", "conversion_factor": 1, 
		"uom": "Nos"
	},
	# taxes
	{
		"doctype": "Purchase Taxes and Charges", "charge_type": "Actual",
		"account_head": "Shipping Charges - %s" % abbr, "rate": 100, 
		"category": "Valuation and Total", "parentfield": "purchase_tax_details",
		"cost_center": "Default Cost Center - %s" % abbr
	},
	{
		"doctype": "Purchase Taxes and Charges", "charge_type": "On Net Total",
		"account_head": "Customs Duty - %s" % abbr, "rate": 10,
		"category": "Valuation", "parentfield": "purchase_tax_details",
		"cost_center": "Default Cost Center - %s" % abbr
	},
	{
		"doctype": "Purchase Taxes and Charges", "charge_type": "On Net Total",
		"account_head": "Excise Duty - %s" % abbr, "rate": 12,
		"category": "Total", "parentfield": "purchase_tax_details"
	},
	{
		"doctype": "Purchase Taxes and Charges", "charge_type": "On Previous Row Amount",
		"account_head": "Education Cess - %s" % abbr, "rate": 2, "row_id": 3,
		"category": "Total", "parentfield": "purchase_tax_details"
	},
	{
		"doctype": "Purchase Taxes and Charges", "charge_type": "On Previous Row Amount",
		"account_head": "S&H Education Cess - %s" % abbr, "rate": 1, "row_id": 3,
		"category": "Total", "parentfield": "purchase_tax_details"
	},
	{
		"doctype": "Purchase Taxes and Charges", "charge_type": "On Previous Row Total",
		"account_head": "CST - %s" % abbr, "rate": 2, "row_id": 5,
		"category": "Total", "parentfield": "purchase_tax_details",
		"cost_center": "Default Cost Center - %s" % abbr
	},
	{
		"doctype": "Purchase Taxes and Charges", "charge_type": "On Net Total",
		"account_head": "VAT - Test - %s" % abbr, "rate": 12.5,
		"category": "Total", "parentfield": "purchase_tax_details"
	},
	{
		"doctype": "Purchase Taxes and Charges", "charge_type": "On Previous Row Total",
		"account_head": "Discount - %s" % abbr, "rate": -10, "row_id": 7,
		"category": "Total", "parentfield": "purchase_tax_details",
		"cost_center": "Default Cost Center - %s" % abbr
	},
]

class TestPurchaseReceipt(unittest.TestCase):
	def setUp(self):
		webnotes.conn.begin()
		load_data()
		
	def test_purchase_invoice(self):
		from webnotes.model.doclist import DocList
		controller = webnotes.model.insert(DocList(purchase_invoice_doclist))
		controller.load_from_db()
		dl = controller.doclist
		
		# test net total
		self.assertEqual(dl[0].net_total, 1250)
		
		# test tax amounts and totals
		expected_values = [
			["Shipping Charges - %s" % abbr, 100, 1350],
			["Customs Duty - %s" % abbr, 125, 1350],
			["Excise Duty - %s" % abbr, 140, 1490],
			["Education Cess - %s" % abbr, 2.8, 1492.8],
			["S&H Education Cess - %s" % abbr, 1.4, 1494.2],
			["CST - %s" % abbr, 29.884, 1524.084],
			["VAT - Test - %s" % abbr, 156.25, 1680.334],
			["Discount - %s" % abbr, -168.0334, 1512.3006],
		]		
		for i, tax in enumerate(dl.get({"parentfield": "purchase_tax_details"})):
			# print tax.account_head, tax.tax_amount, tax.total
			self.assertEqual(tax.account_head, expected_values[i][0])
			self.assertEqual(tax.tax_amount, expected_values[i][1])
			self.assertEqual(tax.total, expected_values[i][2])
		
		# test item tax amount
		expected_values = [
			["Home Desktop 100", 90],
			["Home Desktop 200", 135]
		]
		for i, item in enumerate(dl.get({"parentfield": "entries"})):
			self.assertEqual(item.item_code, expected_values[i][0])
			self.assertEqual(item.item_tax_amount, expected_values[i][1])
			
	def test_purchase_invoice_having_zero_amount_items(self):
		from webnotes.model.doclist import DocList
		sample_purchase_invoice_doclist = [] + purchase_invoice_doclist
		
		# set rate and amount as 0
		sample_purchase_invoice_doclist[1]["rate"] = 0
		sample_purchase_invoice_doclist[1]["amount"] = 0
		sample_purchase_invoice_doclist[2]["rate"] = 0
		sample_purchase_invoice_doclist[2]["amount"] = 0
		
		
		controller = webnotes.model.insert(DocList(sample_purchase_invoice_doclist))
		controller.load_from_db()
		dl = controller.doclist
		
		# test net total
		self.assertEqual(dl[0].net_total, 0)
		
		# test tax amounts and totals
		expected_values = [
			["Shipping Charges - %s" % abbr, 100, 100],
			["Customs Duty - %s" % abbr, 0, 100],
			["Excise Duty - %s" % abbr, 0, 100],
			["Education Cess - %s" % abbr, 0, 100],
			["S&H Education Cess - %s" % abbr, 0, 100],
			["CST - %s" % abbr, 2, 102],
			["VAT - Test - %s" % abbr, 0, 102],
			["Discount - %s" % abbr, -10.2, 91.8],
		]
		for i, tax in enumerate(dl.get({"parentfield": "purchase_tax_details"})):
			# print tax.account_head, tax.tax_amount, tax.total
			self.assertEqual(tax.account_head, expected_values[i][0])
			self.assertEqual(tax.tax_amount, expected_values[i][1])
			self.assertEqual(tax.total, expected_values[i][2])
		
		# test item tax amount
		expected_values = [
			["Home Desktop 100", 0],
			["Home Desktop 200", 0]
		]
		for i, item in enumerate(dl.get({"parentfield": "entries"})):
			self.assertEqual(item.item_code, expected_values[i][0])
			self.assertEqual(item.item_tax_amount, expected_values[i][1])
		
	def tearDown(self):
		webnotes.conn.rollback()