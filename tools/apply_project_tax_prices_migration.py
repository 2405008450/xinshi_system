"""仅新增税口径附表，不修改旧表或历史金额。"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tools.apply_translation_requirement_migration import verify_target

TABLES = ('annotation_project_price_item_tax', 'recruitment_project_tax',
          'customer_annotation_rate_tax', 'customer_translation_rate_tax')


def apply_migration(connection):
    from annotation_models import AnnotationProjectPriceItemTax
    from recruitment_models import RecruitmentProjectTax
    from customer_annotation_rates import CustomerAnnotationRateTax
    from customer_translation_rates import CustomerTranslationRateTax
    for model in (AnnotationProjectPriceItemTax, RecruitmentProjectTax, CustomerAnnotationRateTax, CustomerTranslationRateTax):
        model.__table__.create(connection, checkfirst=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--confirm-target', required=True)
    parser.add_argument('--expected-commit', required=True)
    parser.add_argument('--check-only', action='store_true')
    args = parser.parse_args()
    engine = verify_target(args)
    from sqlalchemy import inspect, text
    with engine.begin() as connection:
        print('tax_tables_before=' + repr({name: inspect(connection).has_table(name) for name in TABLES}))
        if not args.check_only:
            connection.execute(text("SET LOCAL lock_timeout='5s'"))
            connection.execute(text("SET LOCAL statement_timeout='30s'"))
            apply_migration(connection)
            print('tax_tables_ready=' + repr({name: inspect(connection).has_table(name) for name in TABLES}))
