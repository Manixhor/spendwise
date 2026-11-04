from datetime import date
from decimal import Decimal
from io import BytesIO

from django.contrib.auth.models import User
from django.test import TestCase
from openpyxl import Workbook

from .importers.dedupe import filter_new
from .importers.parsers import ParsedTransaction, parse_xlsx


class ImportRegressionTests(TestCase):
    def test_xlsx_credit_in_first_column_is_income(self):
        workbook = Workbook()
        sheet = workbook.active
        sheet.append(['Credit', 'Date', 'Description'])
        sheet.append([250, '2026-11-01', 'Salary'])
        content = BytesIO()
        workbook.save(content)

        transactions = parse_xlsx(content.getvalue())

        self.assertEqual(len(transactions), 1)
        self.assertEqual(transactions[0].txn_type, 'income')
        self.assertEqual(transactions[0].amount, Decimal('250'))

    def test_duplicate_rows_in_one_file_are_skipped(self):
        user = User.objects.create_user(username='import@example.com')
        transaction = ParsedTransaction(
            date=date(2026, 11, 1), amount=Decimal('25.00'),
            txn_type='expense', title='Coffee',
        )

        self.assertEqual(filter_new(user, [transaction, transaction]), [transaction])
